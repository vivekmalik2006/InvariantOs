"""
Contract Validation Agent — Member 2.

For each impacted rule, asks the LLM whether the PR diff violates the rule.
Returns a ValidationResult for each ImpactedRule.

Fail-closed: on any error/timeout, defaults to NEEDS_EVIDENCE — never silently
marks something OK.
"""
from __future__ import annotations
import json
import logging
import re

from orchestrator.schemas import ImpactedRule, Rule, ValidationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(
    diff: str,
    impacted_rules: list[ImpactedRule],
    rules: list[Rule],
) -> list[ValidationResult]:
    """
    For each rule in *impacted_rules*, validate whether *diff* violates the rule.

    Args:
        diff:           Raw unified-diff string of the PR.
        impacted_rules: Output of the Change Impact Agent.
        rules:          Full list of Rule objects (to look up statements/refs).

    Returns:
        A list of ValidationResult — one per impacted rule.
    """
    rule_map: dict[str, Rule] = {r.id: r for r in rules}
    results: list[ValidationResult] = []

    for impacted in impacted_rules:
        rule = rule_map.get(impacted.rule_id)
        if rule is None:
            logger.warning("No Rule found for rule_id %s; skipping.", impacted.rule_id)
            continue
        result = _validate_single(diff, impacted, rule)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# Per-rule validation
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a strict business-rule compliance auditor for a software system.
You will be given:
1. A business rule that the system must always satisfy.
2. A PR diff that changes the system.

Decide whether the diff VIOLATES the rule, is clearly OK, or lacks enough evidence to be sure.

Respond with a JSON object matching exactly this schema:
{
  "verdict": "<OK|VIOLATION|NEEDS_EVIDENCE>",
  "explanation": "<one to three sentences explaining your reasoning>",
  "evidence": ["<line ref or doc ref 1>", "<line ref or doc ref 2>"]
}

Be strict: if in doubt, return NEEDS_EVIDENCE rather than OK.
Return ONLY the JSON object — no markdown, no preamble."""


def _validate_single(
    diff: str,
    impacted: ImpactedRule,
    rule: Rule,
) -> ValidationResult:
    """Call the LLM to validate a single rule; fall back to NEEDS_EVIDENCE on error."""
    source_refs_text = "; ".join(
        f"{ref.file}:{ref.lines}" for ref in rule.source_refs
    ) if rule.source_refs else "none"

    user_prompt = (
        f"Business rule ({rule.id}): \"{rule.statement}\"\n"
        f"Rule source references: {source_refs_text}\n"
        f"Call chain that may be affected: {' → '.join(impacted.affected_call_chain)}\n\n"
        f"PR diff (truncated to 3000 chars):\n```\n{diff[:3000]}\n```"
    )

    try:
        from orchestrator.llm_client import complete, LLMClientError  # type: ignore
        raw = complete(_SYSTEM_PROMPT, user_prompt, json_mode=True)
        data = _parse_json(raw)

        verdict = data.get("verdict", "NEEDS_EVIDENCE")
        if verdict not in ("OK", "VIOLATION", "NEEDS_EVIDENCE"):
            verdict = "NEEDS_EVIDENCE"

        result = ValidationResult(
            rule_id=rule.id,
            verdict=verdict,
            explanation=data.get("explanation", "LLM provided no explanation."),
            evidence=data.get("evidence", []),
        )
        logger.info("Validation %s → %s", rule.id, verdict)
        return result

    except Exception as exc:
        logger.warning(
            "Contract validation LLM call failed for %s (%s); defaulting to NEEDS_EVIDENCE.",
            rule.id, exc,
        )
        return _needs_evidence_fallback(rule.id, str(exc))


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Could not parse JSON from LLM response: {raw[:200]}")


def _needs_evidence_fallback(rule_id: str, reason: str) -> ValidationResult:
    return ValidationResult(
        rule_id=rule_id,
        verdict="NEEDS_EVIDENCE",
        explanation=(
            f"Automated validation could not complete ({reason}). "
            "Manual review required — do not merge without confirming this rule is upheld."
        ),
        evidence=[],
    )
