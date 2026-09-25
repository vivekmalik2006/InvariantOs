"""
Shared Pydantic data contracts for InvariantOS.
This is the SINGLE SOURCE OF TRUTH for all shapes that cross module boundaries.
Every agent imports from here — nobody redefines their own version.
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Rule — output of the Rule Miner Agent (Member 1)
# ---------------------------------------------------------------------------

class SourceRef(BaseModel):
    file: str
    lines: str  # e.g. "12-14"


class Rule(BaseModel):
    id: str
    statement: str
    category: str
    severity: Literal["critical", "high", "medium", "low"]
    source_refs: list[SourceRef] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    related_functions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ImpactedRule — output of the Change Impact Agent (Member 2)
# ---------------------------------------------------------------------------

class ImpactedRule(BaseModel):
    rule_id: str
    reason: str
    confidence: Literal["high", "medium", "low"]
    affected_call_chain: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ValidationResult — output of the Contract Validation Agent (Member 2)
# ---------------------------------------------------------------------------

class ValidationResult(BaseModel):
    rule_id: str
    verdict: Literal["OK", "VIOLATION", "NEEDS_EVIDENCE"]
    explanation: str
    evidence: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# SecurityFinding — output of the Security & Access Agent (Member 3)
# ---------------------------------------------------------------------------

class SecurityFinding(BaseModel):
    rule_id: str
    risk_type: Optional[str] = None  # e.g. "cross-tenant-exposure", "permission-bypass"
    verdict: Literal["OK", "VIOLATION", "NEEDS_EVIDENCE"] = "OK"
    explanation: str


# ---------------------------------------------------------------------------
# TestGap — output of the Test Gap Agent (Member 3)
# ---------------------------------------------------------------------------

class TestGap(BaseModel):
    rule_id: str
    has_coverage: bool
    generated_test_path: Optional[str] = None
    generated_test_code: Optional[str] = None


# ---------------------------------------------------------------------------
# AnalysisReport — final output of the whole pipeline (Evidence Report Agent)
# ---------------------------------------------------------------------------

class AnalysisReport(BaseModel):
    analysis_id: str
    pr_diff_summary: str
    impacted_rules: list[ImpactedRule] = Field(default_factory=list)
    validation_results: list[ValidationResult] = Field(default_factory=list)
    security_findings: list[SecurityFinding] = Field(default_factory=list)
    test_gaps: list[TestGap] = Field(default_factory=list)
    final_verdict: Literal["SAFE", "BLOCK", "NEEDS_EVIDENCE"]
    final_verdict_label: str
    summary_markdown: str


# ---------------------------------------------------------------------------
# Request / Response helpers for the FastAPI endpoints
# ---------------------------------------------------------------------------

class ExtractRulesRequest(BaseModel):
    repo_path: str = "demo-repo"


class ExtractRulesResponse(BaseModel):
    rules: list[Rule]


class AnalyzeRequest(BaseModel):
    diff: str = Field(..., min_length=1, description="Raw unified-diff text of the PR")
    branch: Optional[str] = None


class RulesResponse(BaseModel):
    rules: list[Rule]


class HealthResponse(BaseModel):
    status: str = "ok"
