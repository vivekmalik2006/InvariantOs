"""
Security & Access Agent — Member 3 (Real Implementation).

Two-pass approach:
  Pass 1 (heuristic, cheap): regex scan of the diff for cross-tenant, permission,
          authentication, and role-related patterns.
  Pass 2 (LLM confirmation): for any diff that touches security-relevant patterns,
          ask the LLM to confirm and characterise the risk.

Fail-closed: when uncertain, flags as NEEDS_EVIDENCE rather than OK.
Only emits findings for rules tagged with access-control/security, or for any
diff that touches security-sensitive code patterns.
"""
from __future__ import annotations

import json
import logging
import re

from orchestrator.schemas import ImpactedRule, SecurityFinding

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Security-relevant regex patterns (Pass 1 heuristic)
# ---------------------------------------------------------------------------

# Cross-tenant / multi-tenant exposure patterns
_CROSS_TENANT_PATTERNS = re.compile(
    r"\b(org_id|tenant_id|organisation_id|organization_id|tenantId|orgId|organisationId)\b",
    re.IGNORECASE,
)

# Authentication / permission bypass patterns
_AUTH_PATTERNS = re.compile(
    r"\b(auth|authenticate|authorization|permission|role|admin|isAdmin|"
    r"hasPermission|can_access|canAccess|access_token|bearer|jwt|token|"
    r"checkPermission|validateOrgAccess|getPaymentDetails|updatePaymentDetails)\b",
    re.IGNORECASE,
)

# Dangerous mutations — directly changing security-gating values
_MUTATION_PATTERNS = re.compile(
    r"(user_?id|org_?id|tenant_?id|role|permissions?)\s*[=!<>]=?\s*",
    re.IGNORECASE,
)

# Rules that are explicitly security/access-control-related (by ID or tags)
_SECURITY_RULE_IDS = {"RULE-004", "RULE-005"}
_SECURITY_TAGS = {"access-control", "security", "multi-tenant", "permission"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check(diff: str, impacted_rules: list[ImpactedRule]) -> list[SecurityFinding]:
    """
    Check impacted rules for security/access-control violations.

    Args:
        diff:            Raw unified-diff string of the PR.
        impacted_rules:  Output of the Change Impact Agent.

    Returns:
        A list of SecurityFinding — one per security-relevant impacted rule,
        plus one "global" finding if the diff itself touches security patterns
        but no security rule was impacted.
    """
    # Pass 1: heuristic scan
    has_cross_tenant_touch = bool(_CROSS_TENANT_PATTERNS.search(diff))
    has_auth_touch = bool(_AUTH_PATTERNS.search(diff))
    has_mutation_touch = bool(_MUTATION_PATTERNS.search(diff))

    diff_has_security = has_cross_tenant_touch or has_auth_touch or has_mutation_touch

    findings: list[SecurityFinding] = []
    security_rules_hit: set[str] = set()

    for impacted in impacted_rules:
        is_security_rule = (
            impacted.rule_id in _SECURITY_RULE_IDS
            or _has_security_tag(impacted)
        )

        if not (is_security_rule or diff_has_security):
            continue

        security_rules_hit.add(impacted.rule_id)

        risk_type = _classify_risk(diff, impacted, has_cross_tenant_touch, has_auth_touch)
        verdict, explanation = _pass2_llm_confirm(diff, impacted, risk_type)

        findings.append(SecurityFinding(
            rule_id=impacted.rule_id,
            risk_type=risk_type,
            verdict=verdict,
            explanation=explanation,
        ))

    # If diff touches security patterns but no security rules were in impacted_rules,
    # emit a NEEDS_EVIDENCE finding to prompt human review (fail-closed)
    if diff_has_security and not security_rules_hit and impacted_rules:
        logger.warning(
            "Diff touches security-sensitive patterns but no security rule was impacted. "
            "Emitting NEEDS_EVIDENCE finding."
        )
        # ASSUMPTION: attach to the first impacted rule as a proxy
        proxy_rule_id = impacted_rules[0].rule_id
        findings.append(SecurityFinding(
            rule_id=proxy_rule_id,
            risk_type=_detect_risk_type(diff),
            verdict="NEEDS_EVIDENCE",
            explanation=(
                "The diff modifies security-sensitive symbols "
                f"(cross-tenant={has_cross_tenant_touch}, auth={has_auth_touch}, "
                f"mutation={has_mutation_touch}), but no explicit security rule "
                "was identified as impacted. Manual security review required."
            ),
        ))

    return findings


# ---------------------------------------------------------------------------
# Risk classification (Pass 1)
# ---------------------------------------------------------------------------

def _has_security_tag(impacted: ImpactedRule) -> bool:
    """Check if any function in the call chain matches known security functions."""
    chain_lower = {fn.lower() for fn in impacted.affected_call_chain}
    security_fn_patterns = {
        "validateorgaccess", "getpaymentdetails", "updatepaymentdetails",
        "checkpermission", "haspermission", "getordersbyuser",
    }
    return bool(chain_lower & security_fn_patterns)


def _classify_risk(
    diff: str,
    impacted: ImpactedRule,
    has_cross_tenant: bool,
    has_auth: bool,
) -> str:
    """Return a risk_type string based on heuristic patterns."""
    chain_lower = {fn.lower() for fn in (impacted.affected_call_chain or [])}

    if has_cross_tenant or "validateorgaccess" in chain_lower or "getordersbyuser" in chain_lower:
        return "cross-tenant-exposure"
    if "updatepaymentdetails" in chain_lower or "getpaymentdetails" in chain_lower:
        return "permission-bypass"
    if has_auth:
        return "authentication-change"
    return "access-control-change"


def _detect_risk_type(diff: str) -> str:
    """Detect the most likely risk type from the diff text alone."""
    if _CROSS_TENANT_PATTERNS.search(diff):
        return "cross-tenant-exposure"
    if re.search(r"\b(payment|billing|refund)\b", diff, re.IGNORECASE):
        return "permission-bypass"
    return "access-control-change"


# ---------------------------------------------------------------------------
# Pass 2: LLM confirmation
# ---------------------------------------------------------------------------

_SECURITY_SYSTEM_PROMPT = """\
You are a security code reviewer specialised in access-control and multi-tenant isolation.
You will be given a PR diff and context about which business rule is potentially affected.

Decide whether the diff introduces a security risk:
- "OK"             — no security risk evident from the diff for this rule.
- "VIOLATION"      — the diff clearly introduces a privilege escalation, cross-tenant data leak,
                     or authentication bypass.
- "NEEDS_EVIDENCE" — the diff touches security-sensitive code but it is ambiguous; manual
                     security review is required before merge.

Respond with ONLY a JSON object:
{
  "verdict": "<OK|VIOLATION|NEEDS_EVIDENCE>",
  "explanation": "<one to two sentences>"
}

Fail-closed: when in doubt, return NEEDS_EVIDENCE rather than OK."""


def _pass2_llm_confirm(
    diff: str,
    impacted: ImpactedRule,
    risk_type: str,
) -> tuple[str, str]:
    """
    Ask the LLM to confirm whether the diff poses the identified security risk.
    Falls back to NEEDS_EVIDENCE if the LLM call fails (fail-closed).
    """
    try:
        from orchestrator.llm_client import complete, LLMClientError  # type: ignore

        call_chain = " → ".join(impacted.affected_call_chain) if impacted.affected_call_chain else "unknown"
        user_prompt = (
            f"Rule: {impacted.rule_id} — {impacted.reason}\n"
            f"Risk type identified by heuristic: {risk_type}\n"
            f"Call chain: {call_chain}\n\n"
            f"PR diff (first 2500 chars):\n```\n{diff[:2500]}\n```"
        )

        raw = complete(_SECURITY_SYSTEM_PROMPT, user_prompt, json_mode=True)
        data = _parse_json(raw)

        verdict = data.get("verdict", "NEEDS_EVIDENCE")
        if verdict not in ("OK", "VIOLATION", "NEEDS_EVIDENCE"):
            verdict = "NEEDS_EVIDENCE"

        explanation = data.get(
            "explanation",
            f"LLM security analysis for risk type '{risk_type}'.",
        )
        logger.info("Security check %s → %s", impacted.rule_id, verdict)
        return verdict, explanation

    except Exception as exc:
        logger.warning(
            "Security LLM call failed for %s (%s); defaulting to NEEDS_EVIDENCE (fail-closed).",
            impacted.rule_id, exc,
        )
        return "NEEDS_EVIDENCE", (
            f"Security analysis could not complete ({exc}). "
            f"Risk type '{risk_type}' detected by heuristic. Manual review required."
        )


# ---------------------------------------------------------------------------
# JSON helper
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Could not parse JSON from LLM response: {raw[:200]}")
