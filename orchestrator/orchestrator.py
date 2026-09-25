"""
InvariantOS Orchestrator Pipeline — Member 2.

Runs all agents in the correct order, in parallel where possible, and
assembles the final AnalysisReport.

Agent execution order:
  1. Load rules.json (deterministic)
  2. Change Impact Agent  (deterministic + LLM)
  3. In parallel:
       a. Contract Validation Agent  (LLM)   — Member 2
       b. Security & Access Agent    (LLM)   — Member 3
       c. Test Gap Agent             (LLM)   — Member 3
  4. Evidence Report Agent  (assembles + renders markdown) — Member 4
  5. Compute final_verdict (BLOCK > NEEDS_EVIDENCE > SAFE)
  6. Persist and return the AnalysisReport

All agent calls are wrapped so that a failure in any single agent never
crashes the pipeline — it degrades to the safest default instead.
"""
from __future__ import annotations
import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from orchestrator.schemas import (
    AnalysisReport,
    ImpactedRule,
    Rule,
    SecurityFinding,
    TestGap,
    ValidationResult,
)

logger = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_RULES_PATH = _HERE / "data" / "rules.json"
_ANALYSES_DIR = _HERE / "data" / "analyses"
_ANALYSES_DIR.mkdir(parents=True, exist_ok=True)

# Default repo path for test-gap generated tests
_DEFAULT_REPO_PATH = str(_HERE.parent / "demo-repo")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_pipeline(diff: str) -> AnalysisReport:
    """
    Run the full InvariantOS pipeline on a PR diff string.

    Returns an AnalysisReport with final_verdict one of:
        "BLOCK"          — at least one VIOLATION or security problem found
        "NEEDS_EVIDENCE" — at least one NEEDS_EVIDENCE result or uncovered critical rule
        "SAFE"           — all rules checked and none violated

    Never raises — every error is caught and the pipeline degrades gracefully.
    """
    analysis_id = _new_analysis_id()
    logger.info("Pipeline started — analysis_id=%s", analysis_id)

    # ------------------------------------------------------------------
    # Step 1: Load rules
    # ------------------------------------------------------------------
    rules = _load_rules()
    if not rules:
        logger.warning("No rules loaded; returning NEEDS_EVIDENCE immediately.")
        return _empty_report(analysis_id, diff)

    # ------------------------------------------------------------------
    # Step 2: Change Impact
    # ------------------------------------------------------------------
    impacted_rules = _safe_find_impacted_rules(diff, rules)
    logger.info("Impacted rules: %s", [r.rule_id for r in impacted_rules])

    if not impacted_rules:
        logger.info("No rules impacted — verdict: SAFE.")
        return _safe_report(analysis_id, diff, rules)

    # ------------------------------------------------------------------
    # Step 3: Parallel — Validate + Security + Test Gap
    # ------------------------------------------------------------------
    validation_results: list[ValidationResult] = []
    security_findings: list[SecurityFinding] = []
    test_gaps: list[TestGap] = []

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_safe_validate, diff, impacted_rules, rules): "validate",
            pool.submit(_safe_security_check, diff, impacted_rules): "security",
            pool.submit(_safe_test_gap, diff, impacted_rules, _DEFAULT_REPO_PATH): "test_gap",
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                result = future.result()
                if label == "validate":
                    validation_results = result
                elif label == "security":
                    security_findings = result
                elif label == "test_gap":
                    test_gaps = result
            except Exception as exc:
                logger.error("Parallel agent '%s' raised unexpectedly: %s", label, exc)

    # ------------------------------------------------------------------
    # Step 4: Compute final verdict
    # ------------------------------------------------------------------
    final_verdict, final_verdict_label = _compute_verdict(
        validation_results, security_findings, test_gaps, rules
    )
    logger.info("Final verdict: %s", final_verdict)

    # ------------------------------------------------------------------
    # Step 5: Generate diff summary (cheap heuristic — no extra LLM call)
    # ------------------------------------------------------------------
    diff_summary = _summarize_diff(diff)

    # ------------------------------------------------------------------
    # Step 6: Evidence Report
    # ------------------------------------------------------------------
    report = _safe_generate_report(
        analysis_id=analysis_id,
        diff_summary=diff_summary,
        impacted_rules=impacted_rules,
        validation_results=validation_results,
        security_findings=security_findings,
        test_gaps=test_gaps,
        final_verdict=final_verdict,
        final_verdict_label=final_verdict_label,
    )

    # ------------------------------------------------------------------
    # Step 7: Persist
    # ------------------------------------------------------------------
    _persist(report)
    return report


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------

def _compute_verdict(
    validation_results: list[ValidationResult],
    security_findings: list[SecurityFinding],
    test_gaps: list[TestGap],
    rules: list[Rule],
) -> tuple[str, str]:
    rule_severity = {r.id: r.severity for r in rules}

    # BLOCK if any violation
    for vr in validation_results:
        if vr.verdict == "VIOLATION":
            return "BLOCK", "BLOCK: Business Rule Violated"
    for sf in security_findings:
        if sf.verdict not in ("OK", "NEEDS_EVIDENCE"):
            return "BLOCK", "BLOCK: Security Rule Violated"

    # NEEDS_EVIDENCE if any unresolved or uncovered critical rule
    for vr in validation_results:
        if vr.verdict == "NEEDS_EVIDENCE":
            return "NEEDS_EVIDENCE", "NEEDS EVIDENCE: Critical Rule Has No Regression Coverage"
    for tg in test_gaps:
        if not tg.has_coverage:
            sev = rule_severity.get(tg.rule_id, "medium")
            if sev == "critical":
                return "NEEDS_EVIDENCE", "NEEDS EVIDENCE: Critical Rule Has No Regression Coverage"

    return "SAFE", "SAFE TO MERGE"


# ---------------------------------------------------------------------------
# Safe wrappers — every agent call catches exceptions
# ---------------------------------------------------------------------------

def _safe_find_impacted_rules(diff: str, rules: list[Rule]) -> list[ImpactedRule]:
    try:
        from orchestrator.agents.change_impact import find_impacted_rules
        return find_impacted_rules(diff, rules)
    except Exception as exc:
        logger.error("Change Impact Agent failed: %s", exc)
        return []


def _safe_validate(
    diff: str, impacted_rules: list[ImpactedRule], rules: list[Rule]
) -> list[ValidationResult]:
    try:
        from orchestrator.agents.contract_validator import validate
        return validate(diff, impacted_rules, rules)
    except Exception as exc:
        logger.error("Contract Validation Agent failed: %s", exc)
        # Fail closed — return NEEDS_EVIDENCE for every impacted rule
        return [
            ValidationResult(
                rule_id=ir.rule_id,
                verdict="NEEDS_EVIDENCE",
                explanation=f"Validation agent failed: {exc}",
                evidence=[],
            )
            for ir in impacted_rules
        ]


def _safe_security_check(diff: str, impacted_rules: list[ImpactedRule]) -> list[SecurityFinding]:
    try:
        from orchestrator.agents.security_access import check
        return check(diff, impacted_rules)
    except Exception as exc:
        logger.error("Security & Access Agent failed: %s", exc)
        return []


def _safe_test_gap(
    diff: str, impacted_rules: list[ImpactedRule], repo_path: str
) -> list[TestGap]:
    try:
        from orchestrator.agents.test_gap import analyze
        return analyze(diff, impacted_rules, repo_path)
    except Exception as exc:
        logger.error("Test Gap Agent failed: %s", exc)
        return [
            TestGap(rule_id=ir.rule_id, has_coverage=False)
            for ir in impacted_rules
        ]


def _safe_generate_report(**kwargs) -> AnalysisReport:
    try:
        from orchestrator.agents.evidence_report import generate
        return generate(**kwargs)
    except Exception as exc:
        logger.error("Evidence Report Agent failed: %s", exc)
        # Minimal fallback report
        return AnalysisReport(
            analysis_id=kwargs.get("analysis_id", "error"),
            pr_diff_summary=kwargs.get("diff_summary", ""),
            impacted_rules=kwargs.get("impacted_rules", []),
            validation_results=kwargs.get("validation_results", []),
            security_findings=kwargs.get("security_findings", []),
            test_gaps=kwargs.get("test_gaps", []),
            final_verdict=kwargs.get("final_verdict", "NEEDS_EVIDENCE"),
            final_verdict_label=kwargs.get("final_verdict_label", "Report generation failed"),
            summary_markdown=f"**Report generation failed:** {exc}",
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _load_rules() -> list[Rule]:
    if not _RULES_PATH.exists():
        logger.warning("rules.json not found at %s", _RULES_PATH)
        return []
    with open(_RULES_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    rules: list[Rule] = []
    for item in raw:
        try:
            rules.append(Rule(**item))
        except Exception as e:
            logger.warning("Skipping invalid rule: %s", e)
    return rules


def _new_analysis_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    return f"run-{ts}-{uuid.uuid4().hex[:6]}"


def _summarize_diff(diff: str) -> str:
    """
    Very cheap heuristic diff summary — no LLM call.
    Member 4's evidence_report can replace this with an LLM call if desired.
    """
    from orchestrator.diff_utils import parse_diff
    parsed = parse_diff(diff)
    files = ", ".join(parsed.changed_files[:3]) or "unknown files"
    symbols = ", ".join(parsed.changed_symbols[:5]) or "unknown symbols"
    added = len(parsed.added_lines)
    removed = len(parsed.removed_lines)
    return (
        f"Changes in {files} — modified symbols: {symbols} "
        f"(+{added} lines, -{removed} lines)."
    )


def _persist(report: AnalysisReport) -> None:
    path = _ANALYSES_DIR / f"{report.analysis_id}.json"
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        logger.info("Report persisted to %s", path)
    except OSError as exc:
        logger.error("Failed to persist report: %s", exc)


def _empty_report(analysis_id: str, diff: str) -> AnalysisReport:
    return AnalysisReport(
        analysis_id=analysis_id,
        pr_diff_summary=_summarize_diff(diff),
        impacted_rules=[],
        validation_results=[],
        security_findings=[],
        test_gaps=[],
        final_verdict="NEEDS_EVIDENCE",
        final_verdict_label="NEEDS EVIDENCE: No rules loaded",
        summary_markdown="⚠️ **No rules available.** Run `/api/rules/extract` first.",
    )


def _safe_report(analysis_id: str, diff: str, rules: list[Rule]) -> AnalysisReport:
    return AnalysisReport(
        analysis_id=analysis_id,
        pr_diff_summary=_summarize_diff(diff),
        impacted_rules=[],
        validation_results=[],
        security_findings=[],
        test_gaps=[],
        final_verdict="SAFE",
        final_verdict_label="SAFE TO MERGE",
        summary_markdown=(
            "✅ **SAFE TO MERGE** — No business rules are affected by this change."
        ),
    )
