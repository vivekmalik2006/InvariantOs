# InvariantOS — Hidden Business-Rule Guardian

> Prevents semantic regressions by discovering the hidden business rules a system must preserve, then proving whether a pull request violates them.

## Quick Start

```bash
# 1. Clone and set up Python env
cd invariantos
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment file and fill in credentials
cp .env.example .env
# Edit .env: set WATSONX_API_KEY (or OPENAI_API_KEY as fallback)

# 4. Start the API server
cd orchestrator
uvicorn main:app --reload --port 8000

# 5. (Optional) Install Node deps for the demo-repo tests
cd ../demo-repo && npm install
npx jest              # should all pass (no regression test gap yet)
npx jest tests/generated/  # regression test — should FAIL on buggy branch
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/rules` | Get the Behavioral Contract Graph |
| POST | `/api/rules/extract` | Mine rules from `demo-repo/` |
| POST | `/api/analyze` | Analyze a PR diff → AnalysisReport |
| GET | `/api/report/{id}` | Retrieve a saved report |

### Example: analyze the seeded buggy diff

```bash
curl -s -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"diff": "diff --git a/src/shipments.js b/src/shipments.js\n--- a/src/shipments.js\n+++ b/src/shipments.js\n@@ -30,7 +30,7 @@ async function shipmentJob(order) {\n-  if (order.status === \"PAID\") {\n+  if (order.status !== \"CANCELLED\") {", "branch": "feature/cancel-status-bug"}' \
  | python -m json.tool
```

Expected `final_verdict`: `"BLOCK"` (with LLM) or `"NEEDS_EVIDENCE"` (without LLM, fail-closed).

## Project Structure

```
invariantos/
  orchestrator/             # FastAPI app + agents (Member 2)
    main.py                 # 5 API endpoints
    orchestrator.py         # Pipeline runner
    schemas.py              # Shared Pydantic models
    llm_client.py           # watsonx.ai + OpenAI LLM wrapper
    diff_utils.py           # Diff parsing utilities
    agents/
      change_impact.py      # Member 2 — detects affected rules
      contract_validator.py # Member 2 — validates rule compliance
      security_access.py    # Member 3 stub
      test_gap.py           # Member 3 stub
      evidence_report.py    # Member 4 stub
      rule_miner.py         # Member 1 stub
    data/
      rules.json            # Behavioral Contract Graph
      analyses/             # Persisted AnalysisReport JSON files
  demo-repo/                # Member 3 — seeded e-commerce app
    src/                    # orders.js, shipments.js, payments.js, ...
    tests/                  # Jest tests (+ generated regression tests)
    docs/order-lifecycle.md # Source material for rule mining
  dashboard/                # Member 4 — Streamlit UI
  docs/
    architecture.md         # Pipeline sequence diagram
```

## Environment Variables

See `.env.example`. At least one of `WATSONX_API_KEY` or `OPENAI_API_KEY` is required for full LLM-assisted analysis. Without credentials, the pipeline runs in fail-closed mode (NEEDS_EVIDENCE).
