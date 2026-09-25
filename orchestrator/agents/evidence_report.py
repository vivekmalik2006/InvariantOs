"""
Evidence Report Agent — Member 4 (Real Implementation).

Assembles the final AnalysisReport and renders a PR-comment-style
summary_markdown that reads like a human wrote it — not a raw JSON dump.

The summary_markdown is designed to be:
  - Posted directly as a PR comment in GitHub/GitLab.
  - Understood by a developer in < 30 seconds.
  - Specific: names the rule, the call chain, the changed lines, and the fix.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from orchestrator.schemas import (
    AnalysisReport,
    ImpactedRule,
    SecurityFinding,
    TestGap,
    ValidationResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(
    diff_summary: str,
    impacted_rules: list[ImpactedRule],
    validation_results: list[ValidationResult],
    security_findings: list[SecurityFinding],
    test_gaps: list[TestGap],
    final_verdict: str,
    final_verdict_label: str,
    analysis_id: str,
) -> AnalysisReport:
    """
    Assemble the final AnalysisReport with a human-readable summary_markdown.

    Args:
        diff_summary:       One-line summary of what the diff does.
        impacted_rules:     Output of the Change Impact Agent.
        validation_results: Output of the Contract Validation Agent.
        security_findings:  Output of the Security & Access Agent.
        test_gaps:          Output of the Test Gap Agent.
        final_verdict:      "SAFE" | "BLOCK" | "NEEDS_EVIDENCE".
        final_verdict_label: Human-readable verdict label.
        analysis_id:        Unique run identifier.

    Returns:
        A fully populated AnalysisReport.
    """
    summary_markdown = _render_summary(
        diff_summary=diff_summary,
        impacted_rules=impacted_rules,
        validation_results=validation_results,
        security_findings=security_findings,
        test_gaps=test_gaps,
        final_verdict=final_verdict,
        final_verdict_label=final_verdict_label,
        analysis_id=analysis_id,
    )

    return AnalysisReport(
        analysis_id=analysis_id,
        pr_diff_summary=diff_summary,
        impacted_rules=impacted_rules,
        validation_results=validation_results,
        security_findings=security_findings,
        test_gaps=test_gaps,
        final_verdict=final_verdict,
        final_verdict_label=final_verdict_label,
        summary_markdown=summary_markdown,
    )


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

_VERDICT_BANNER = {
    "SAFE":           "## ✅ SAFE TO MERGE",
    "BLOCK":          "## 🛑 BLOCK: Business Rule Violated",
    "NEEDS_EVIDENCE": "## ⚠️ NEEDS EVIDENCE: Critical Rule Has No Regression Coverage",
}

_VERDICT_BADGE = {
    "SAFE":           "> **InvariantOS verdict:** `SAFE TO MERGE` — No business rules are violated by this change.",
    "BLOCK":          "> **InvariantOS verdict:** `BLOCK` — This change violates one or more business invariants. Do not merge.",
    "NEEDS_EVIDENCE": "> **InvariantOS verdict:** `NEEDS EVIDENCE` — Coverage gaps or ambiguous validation. Manual review required.",
}


def _render_summary(
    diff_summary: str,
    impacted_rules: list[ImpactedRule],
    validation_results: list[ValidationResult],
    security_findings: list[SecurityFinding],
    test_gaps: list[TestGap],
    final_verdict: str,
    final_verdict_label: str,
    analysis_id: str,
) -> str:
    lines: list[str] = []

    # ---- Header ----
    banner = _VERDICT_BANNER.get(final_verdict, f"## ⚠️ {final_verdict_label}")
    badge  = _VERDICT_BADGE.get(final_verdict, f"> **Verdict:** {final_verdict_label}")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines += [
        banner,
        "",
        badge,
        "",
        f"**Analysis ID:** `{analysis_id}`  ",
        f"**Analysed at:** {ts}",
        "",
        "---",
        "",
        f"### 📋 What this PR does",
        "",
        f"{diff_summary}",
        "",
    ]

    # ---- Impacted Rules ----
    if impacted_rules:
        vr_map  = {vr.rule_id: vr  for vr in validation_results}
        tg_map  = {tg.rule_id: tg  for tg in test_gaps}

        lines += ["---", "", "### 📌 Impacted Business Rules", ""]

        for ir in impacted_rules:
            vr = vr_map.get(ir.rule_id)
            tg = tg_map.get(ir.rule_id)

            # Verdict badge for this rule
            if vr:
                if vr.verdict == "VIOLATION":
                    verdict_icon = "🛑 VIOLATION"
                elif vr.verdict == "OK":
                    verdict_icon = "✅ OK"
                else:
                    verdict_icon = "⚠️ NEEDS EVIDENCE"
            else:
                verdict_icon = "⬜ Not validated"

            lines.append(f"#### {ir.rule_id} — {verdict_icon}")
            lines.append("")

            # Why this rule is impacted
            lines.append(f"**Why impacted:** {ir.reason}")
            lines.append(f"**Confidence:** `{ir.confidence}`")

            # Call chain
            if ir.affected_call_chain:
                chain_str = " → ".join(f"`{fn}`" for fn in ir.affected_call_chain)
                lines.append(f"**Call chain:** {chain_str}")

            lines.append("")

            # Validation result
            if vr:
                lines.append(f"**Validation:** {vr.explanation}")
                if vr.evidence:
                    lines.append("")
                    lines.append("**Evidence:**")
                    for ev in vr.evidence:
                        lines.append(f"  - {ev}")

            lines.append("")

            # Test gap
            if tg:
                if tg.has_coverage:
                    lines.append("**Test coverage:** ✅ Existing tests cover this rule.")
                else:
                    lines.append("**Test coverage:** ⚠️ No existing regression test found for this rule.")
                    if tg.generated_test_path:
                        lines.append(f"**Generated test:** [`{tg.generated_test_path}`]({tg.generated_test_path})")
                        lines.append("")
                        lines.append("> Run this test to confirm the violation and verify the fix:")
                        lines.append(f"> ```bash")
                        lines.append(f"> npx jest {tg.generated_test_path}")
                        lines.append(f"> ```")

            lines.append("")

    # ---- Security Findings ----
    if security_findings:
        lines += ["---", "", "### 🔒 Security & Access Control", ""]
        for sf in security_findings:
            if sf.verdict == "OK":
                icon = "✅"
            elif sf.verdict == "VIOLATION":
                icon = "🛑"
            else:
                icon = "⚠️"
            risk = f" `[{sf.risk_type}]`" if sf.risk_type else ""
            lines.append(f"- {icon} **{sf.rule_id}**{risk}: {sf.explanation}")
        lines.append("")

    # ---- SAFE case: no rules impacted ----
    if not impacted_rules:
        lines += [
            "---",
            "",
            "### 📊 Result",
            "",
            "No business rules in the Behavioral Contract Graph are affected by this change.",
            "All checks passed.",
            "",
        ]

    # ---- What to do next ----
    if final_verdict == "BLOCK":
        lines += [
            "---",
            "",
            "### 🔧 Required Action",
            "",
            "**Do not merge this PR.** Review the violation(s) above and apply a corrective patch.",
            "",
            "The call chain shows exactly where the guard condition needs to be restored.",
            "Run the generated regression test to confirm the fix before re-analysis.",
            "",
        ]
    elif final_verdict == "NEEDS_EVIDENCE":
        lines += [
            "---",
            "",
            "### 🔧 Required Action",
            "",
            "**Do not merge without manual review.** One or more rules could not be definitively "
            "validated — either the LLM was uncertain, or a critical rule has no regression test.",
            "",
            "Add the generated regression test and set `WATSONX_API_KEY` or `OPENAI_API_KEY` "
            "if LLM analysis was skipped.",
            "",
        ]

    # ---- Footer ----
    lines += [
        "---",
        "",
        f"_🤖 Generated by [InvariantOS](https://github.com/invariantos) at {ts}_",
        f"_Analysis ID: `{analysis_id}`_",
    ]

    return "\n".join(lines)
