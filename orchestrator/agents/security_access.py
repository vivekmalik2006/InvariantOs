"""
Security & Access Agent — STUB (Member 3 owns the real implementation).

This stub satisfies the function signature agreed with Member 2 so that
orchestrator.py can call it without modification when Member 3 swaps in the
real implementation.
"""
from __future__ import annotations
import logging
import re

from orchestrator.schemas import ImpactedRule, SecurityFinding

logger = logging.getLogger(__name__)

# Tags that indicate a rule is security/access-control related
_SECURITY_TAGS = {"access-control", "security", "multi-tenant", "permission"}


def check(diff: str, impacted_rules: list[ImpactedRule]) -> list[SecurityFinding]:
    """
    Check impacted rules for security/access-control violations.

    Args:
        diff:            Raw unified-diff string of the PR.
        impacted_rules:  Output of the Change Impact Agent.

    Returns:
        A list of SecurityFinding — one per security-relevant impacted rule.

    NOTE: This is a stub implementation. The real implementation (Member 3)
    will add LLM-assisted analysis and richer heuristics.
    """
    # ASSUMPTION: "security-relevant" means the rule_id maps to a rule tagged
    # with access-control or security. Since the stub doesn't have the full
    # rule list, we apply a simple heuristic on the diff text instead.
    findings: list[SecurityFinding] = []

    # Quick heuristic: look for tenant/org/role/permission patterns in diff
    security_pattern = re.compile(
        r"\b(org_id|tenant_id|user_id|role|permission|auth|admin|access)\b",
        re.IGNORECASE,
    )
    diff_has_security_touch = bool(security_pattern.search(diff))

    for impacted in impacted_rules:
        # Only emit a finding for rules whose IDs suggest security context
        # OR if the diff touches security-relevant symbols
        # ASSUMPTION: RULE-004 and RULE-005 are the security rules
        is_security_rule = impacted.rule_id in ("RULE-004", "RULE-005")

        if not (is_security_rule or diff_has_security_touch):
            continue

        # Stub: return OK for all cases (Member 3 will add real analysis)
        findings.append(SecurityFinding(
            rule_id=impacted.rule_id,
            risk_type=None,
            verdict="OK",
            explanation=(
                "Security stub: no tenant/org_id field is touched by this diff. "
                "Full analysis pending Member 3 implementation."
            ),
        ))

    return findings
