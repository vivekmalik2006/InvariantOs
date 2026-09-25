"""
InvariantOS FastAPI application.
Exposes 5 endpoints as specified in overview Section 6.
CORS is open to all origins (hackathon speed, not production).
"""
from __future__ import annotations
import json
import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.schemas import (
    AnalysisReport,
    AnalyzeRequest,
    ExtractRulesRequest,
    ExtractRulesResponse,
    HealthResponse,
    ImpactedRule,
    Rule,
    RulesResponse,
    SecurityFinding,
    TestGap,
    ValidationResult,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="InvariantOS Orchestrator",
    description="Hidden Business-Rule Guardian — prevents semantic regressions in PRs.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Resolve data paths relative to this file so the app can be run from anywhere
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_DATA_DIR = _HERE / "data"
_RULES_PATH = _DATA_DIR / "rules.json"
_ANALYSES_DIR = _DATA_DIR / "analyses"
_ANALYSES_DIR.mkdir(parents=True, exist_ok=True)


def _load_rules() -> list[Rule]:
    """Load rules from data/rules.json; return empty list if file is missing."""
    if not _RULES_PATH.exists():
        return []
    with open(_RULES_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return [Rule(**r) for r in raw]


def _save_analysis(report: AnalysisReport) -> None:
    path = _ANALYSES_DIR / f"{report.analysis_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))


def _load_analysis(analysis_id: str) -> AnalysisReport | None:
    path = _ANALYSES_DIR / f"{analysis_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return AnalysisReport(**json.load(f))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Health-check endpoint."""
    return HealthResponse(status="ok")


@app.get("/api/rules", response_model=RulesResponse, tags=["rules"])
async def get_rules() -> RulesResponse:
    """Return the current Behavioral Contract Graph."""
    rules = _load_rules()
    return RulesResponse(rules=rules)


@app.post("/api/rules/extract", response_model=ExtractRulesResponse, tags=["rules"])
async def extract_rules(body: ExtractRulesRequest) -> ExtractRulesResponse:
    """
    Run the Rule Miner Agent on the given repo path and overwrite data/rules.json.
    """
    try:
        from orchestrator.agents.rule_miner import mine_rules  # type: ignore
        rules = mine_rules(body.repo_path)
    except Exception as exc:
        logger.error("Rule miner failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Rule mining failed: {exc}") from exc

    # Persist to disk
    with open(_RULES_PATH, "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in rules], f, indent=2)

    return ExtractRulesResponse(rules=rules)


@app.post("/api/analyze", response_model=AnalysisReport, tags=["analysis"])
async def analyze_pr(body: AnalyzeRequest) -> AnalysisReport:
    """
    Run the full InvariantOS pipeline on a PR diff and return an AnalysisReport.
    Returns HTTP 200 even on BLOCK/VIOLATION — those are valid analyses, not errors.
    """
    if not body.diff.strip():
        raise HTTPException(status_code=400, detail="diff must not be empty.")

    try:
        from orchestrator.orchestrator import run_pipeline  # type: ignore
        report = run_pipeline(body.diff)
    except Exception as exc:
        logger.exception("Pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc

    _save_analysis(report)
    return report


@app.get("/api/report/{analysis_id}", response_model=AnalysisReport, tags=["analysis"])
async def get_report(analysis_id: str) -> AnalysisReport:
    """Retrieve a previously computed AnalysisReport by its ID."""
    report = _load_analysis(analysis_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{analysis_id}' not found.")
    return report


# ---------------------------------------------------------------------------
# Dev entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("orchestrator.main:app", host="0.0.0.0", port=8000, reload=True)
