# InvariantOS — Architecture & Pipeline Sequence Diagram

## Overview

InvariantOS is a multi-agent pipeline that prevents semantic regressions by mining business rules from a repository and then validating every PR diff against those rules.

```
┌──────────────────────────────────────────────────────────────────┐
│                    FastAPI Orchestrator (Member 2)                │
│                                                                    │
│  POST /api/analyze { diff, branch }                               │
│         │                                                          │
│         ▼                                                          │
│  ┌─────────────────┐                                               │
│  │  Load rules.json│ ◄─── data/rules.json (Member 1)             │
│  └────────┬────────┘                                               │
│           │                                                        │
│           ▼                                                        │
│  ┌──────────────────────────────┐                                  │
│  │   Change Impact Agent        │  (Member 2)                     │
│  │   find_impacted_rules()      │                                  │
│  │   Pass 1: keyword match      │                                  │
│  │   Pass 2: LLM confirm        │                                  │
│  └──────────────┬───────────────┘                                  │
│                 │ list[ImpactedRule]                               │
│         ┌───────┼────────────────────────┐                        │
│         │       │                        │                        │
│         ▼       ▼                        ▼                        │
│  ┌────────────┐ ┌──────────────┐ ┌──────────────┐  PARALLEL      │
│  │ Contract   │ │ Security &   │ │ Test Gap     │  asyncio /      │
│  │ Validation │ │ Access Agent │ │ Agent        │  ThreadPool    │
│  │ validate() │ │ check()      │ │ analyze()    │               │
│  │ (Member 2) │ │ (Member 3)   │ │ (Member 3)   │               │
│  └─────┬──────┘ └──────┬───────┘ └──────┬───────┘               │
│        │               │                 │                        │
│        ▼               ▼                 ▼                        │
│  [ValidationResult] [SecurityFinding] [TestGap]                  │
│        │               │                 │                        │
│        └───────────────┼─────────────────┘                       │
│                        ▼                                          │
│              ┌─────────────────────┐                              │
│              │  Compute Verdict    │  (Member 2, orchestrator.py) │
│              │  BLOCK > NEEDS_EV   │                              │
│              │  > SAFE             │                              │
│              └──────────┬──────────┘                              │
│                         │                                         │
│                         ▼                                         │
│              ┌─────────────────────┐                              │
│              │  Evidence Report    │  (Member 4)                  │
│              │  generate()         │                              │
│              │  summary_markdown   │                              │
│              └──────────┬──────────┘                              │
│                         │                                         │
│                         ▼                                         │
│              AnalysisReport (persisted to data/analyses/)         │
└──────────────────────────────────────────────────────────────────┘
```

## Verdict Logic

```
BLOCK          ← any ValidationResult.verdict == "VIOLATION"
               OR any SecurityFinding.verdict not in ("OK", "NEEDS_EVIDENCE")

NEEDS_EVIDENCE ← any ValidationResult.verdict == "NEEDS_EVIDENCE"
               OR any TestGap.has_coverage == False for a critical rule

SAFE           ← all rules checked and none violated or uncovered
```

## Agent Contracts (function signatures — must not change)

```python
# Change Impact (Member 2) — orchestrator/agents/change_impact.py
def find_impacted_rules(diff: str, rules: list[Rule]) -> list[ImpactedRule]: ...

# Contract Validation (Member 2) — orchestrator/agents/contract_validator.py
def validate(diff: str, impacted_rules: list[ImpactedRule], rules: list[Rule]) -> list[ValidationResult]: ...

# Security & Access (Member 3) — orchestrator/agents/security_access.py
def check(diff: str, impacted_rules: list[ImpactedRule]) -> list[SecurityFinding]: ...

# Test Gap (Member 3) — orchestrator/agents/test_gap.py
def analyze(diff: str, impacted_rules: list[ImpactedRule], repo_path: str) -> list[TestGap]: ...

# Evidence Report (Member 4) — orchestrator/agents/evidence_report.py
def generate(diff_summary, impacted_rules, validation_results, security_findings, test_gaps,
             final_verdict, final_verdict_label, analysis_id) -> AnalysisReport: ...

# Rule Miner (Member 1) — orchestrator/agents/rule_miner.py
def mine_rules(repo_path: str) -> list[Rule]: ...
```

## Data Flow

```
demo-repo/ ──► Rule Miner ──► data/rules.json
                                    │
         PR diff (raw text) ────────►│
                                    ▼
                            Change Impact Agent
                                    │
                              list[ImpactedRule]
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             Contract          Security &       Test Gap
             Validator         Access Agent     Agent
                    └───────────────┼───────────────┘
                                    ▼
                            Evidence Report
                                    │
                            AnalysisReport (JSON)
                                    │
                        ┌───────────┴───────────┐
                        ▼                       ▼
                  Streamlit Dashboard      data/analyses/
                  (Member 4)               <analysis_id>.json
```

## API Endpoints

| Method | Path                    | Description                              |
|--------|-------------------------|------------------------------------------|
| GET    | `/api/health`           | Health check                             |
| GET    | `/api/rules`            | Get current Behavioral Contract Graph    |
| POST   | `/api/rules/extract`    | Run Rule Miner, overwrite rules.json     |
| POST   | `/api/analyze`          | Run full pipeline on a PR diff           |
| GET    | `/api/report/{id}`      | Retrieve a previously saved report       |

## Technology Stack

- **Orchestrator:** Python 3.11+, FastAPI, Pydantic v2, uvicorn
- **LLM:** IBM watsonx.ai (granite-13b-chat-v2) with OpenAI fallback
- **Demo Repo:** Node.js, Jest
- **Dashboard:** Streamlit (Member 4)
- **Parallelism:** Python `concurrent.futures.ThreadPoolExecutor` (genuine parallel agent execution)
