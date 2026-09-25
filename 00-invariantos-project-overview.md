# InvariantOS — Master Build Specification
### IBM Bob 2.0 Hackathon (Sept 25–27, 2026) — Shared context file for the whole team

> **Every one of the 4 team members uploads THIS file plus their own `member-N-*.md` file into their IBM Bob 2.0 chat.** This file is the single source of truth for the product, architecture, and interfaces. The member file tells each person's Bob what to actually build. Read both fully before writing any code.

---

## 0. Instructions for IBM Bob

You are acting as an autonomous senior engineer inside a 4-person hackathon team. You have full repository context, agent mode, parallel subagents, and document understanding.

1. Read this entire file first, then read the accompanying `member-N-*.md` file for the specific person you're working with.
2. Do not stop to ask clarifying questions. Where something is ambiguous, make the most reasonable assumption, write a one-line `# ASSUMPTION:` comment next to it, and keep moving.
3. Build real, runnable files — not pseudocode — following the exact folder structure and data contracts in Section 4 and 5 below, so the four members' work merges without conflicts.
4. Work in the order given in the member file's timeline. Commit after each numbered step with a clear commit message (`git commit -m "step 2: ..."`).
5. Never hardcode or commit API keys/secrets. Read them from environment variables listed in Section 8 and reference `.env.example`. Respect `.gitignore` and `.bobignore` from the repo template.
6. Prefer working, minimal implementations over incomplete "ideal" ones — this is a 48-hour build. A stub that returns realistic mock data honoring the schema is acceptable for hour 0–6 so teammates are never blocked.
7. At the end of your session, save a screenshot of the Bob task session summary (required hackathon deliverable) into `docs/bob-screenshots/<your-name>/`.

---

## 1. Project

**Name:** InvariantOS — Hidden Business-Rule Guardian
**One-liner:** InvariantOS prevents semantic regressions by discovering the hidden business rules a system must preserve, then proving whether a pull request violates them.

**Hackathon:** IBM Bob 2.0 Hackathon, lablab.ai, Sept 25–27 2026. Team of 4. Prize pool $12,000.

## 2. The problem

Normal CI catches syntax errors and known test failures, but not **semantic regressions** — changes that are syntactically fine, pass all existing tests, and still silently break a business rule nobody wrote down anywhere central:

- A cancelled order still gets shipped.
- A user reads another organization's data.
- A discount applies to ineligible customers.
- A refund exceeds the original payment.

The real rules live scattered across code, tests, API specs, docs, tickets, postmortems, comments, and config — never in one place, and never mechanically checked.

## 3. The solution

InvariantOS builds a **Behavioral Contract Graph**: a structured, versioned set of plain-language business invariants mined from a repository's code + docs + tests + tickets. When a PR arrives, a pipeline of specialized agents:

1. Mines/loads the rule graph for the repo.
2. Maps the PR diff to the rules it could plausibly affect (**Change Impact**).
3. Judges, with evidence, whether the change violates each affected rule (**Contract Validation**).
4. Checks cross-tenant/permission-specific risk separately (**Security & Access**).
5. Determines whether existing tests actually cover the affected rules, and generates a regression test if not (**Test Gap**).
6. Produces a human-readable verdict + evidence report (**Evidence Report**): `SAFE TO MERGE`, `BLOCK: Business Rule Violated`, or `NEEDS EVIDENCE: Critical Rule Has No Regression Coverage`.

### Reference demo scenario (build the whole system to make this work end-to-end)

Seeded buggy PR diff on a sample e-commerce repo:

```diff
- if (order.status === "PAID") {
+ if (order.status !== "CANCELLED") {
    createShipment(order);
  }
```

All existing unit tests still pass. InvariantOS must:
1. Detect the affected rule: **"A cancelled order must never be shipped."**
2. Trace the call chain: `cancelOrder → updateOrderStatus → shipmentJob → warehouseAPI.createShipment`.
3. Generate a failing regression test proving a cancelled+paid order gets shipped.
4. Mark the PR **BLOCKED — semantic regression detected**, citing the rule and evidence.
5. After the fix is applied, re-running the pipeline must return **SAFE TO MERGE**.

This before/after moment is the centerpiece of the 3-minute demo video.

## 4. Architecture

```
invariantos/
  orchestrator/                 # Python/FastAPI — the pipeline + API
    main.py                     # FastAPI app, exposes the endpoints in Section 6
    schemas.py                  # Pydantic models = the data contracts in Section 5 (SINGLE SOURCE OF TRUTH)
    llm_client.py                # Shared LLM call wrapper (watsonx.ai primary, OpenAI-compatible fallback)
    orchestrator.py               # Agent-mode pipeline: runs agents in sequence/parallel, assembles final report
    agents/
      rule_miner.py               # Member 1
      change_impact.py             # Member 2
      contract_validator.py        # Member 2
      security_access.py            # Member 3
      test_gap.py                    # Member 3
      evidence_report.py              # Member 4
    data/
      rules.json                  # the mined Behavioral Contract Graph (list of Rule objects)
      analyses/                   # one JSON file per analysis run, named <analysis_id>.json
  demo-repo/                     # Member 3 — the sample e-commerce app InvariantOS analyzes
    src/                          # Node/Express: orders, payments, shipments
    tests/                        # Jest tests
    docs/order-lifecycle.md        # source material the Rule Miner mines
    postmortems/, tickets/          # more source material
    .git branches: main (fixed version) + feature/cancel-status-bug (seeded bug from Section 3)
  dashboard/                     # Member 4 — Streamlit UI on top of the orchestrator API
    app.py
  .github/workflows/invariantos-pr-check.yml   # optional — Member 3, only if time allows
  docs/
    architecture.md
    demo-script.md
    bob-screenshots/<member-name>/
  .env.example
  .gitignore
  .bobignore
  README.md
```

**Dependency order (so all 4 people can start at hour 0 without blocking each other):**
- Member 3 ships a minimal `demo-repo/` (the diff above + 2–3 docs describing the shipment rule) by hour ~4 — everyone else needs this as raw material.
- Member 1 ships a **stub `rules.json`** (hand-written, 6–8 rules including the shipment one) by hour ~2, then replaces it with real LLM-mined output by hour ~16.
- Member 2 and Member 4 build against the stub `rules.json` and the schemas in Section 5 immediately — they do not wait for the real rule miner.
- Integration checkpoints happen at hour ~16 and hour ~30 (see Section 7).

## 5. Shared data contracts

These are the ONLY shapes that cross module boundaries. Implement them as Pydantic models in `orchestrator/schemas.py`; every agent imports from there — nobody redefines their own version.

### Rule
```json
{
  "id": "RULE-001",
  "statement": "A cancelled order must never be shipped.",
  "category": "order-lifecycle",
  "severity": "critical",
  "source_refs": [{"file": "docs/order-lifecycle.md", "lines": "12-14"}],
  "related_entities": ["Order", "Shipment", "OrderStatus"],
  "related_functions": ["createShipment", "updateOrderStatus"],
  "tags": ["fulfillment", "order-status"]
}
```

### ImpactedRule (output of Change Impact Agent)
```json
{
  "rule_id": "RULE-001",
  "reason": "The diff changes the condition guarding createShipment(), which RULE-001 governs.",
  "confidence": "high",
  "affected_call_chain": ["cancelOrder", "updateOrderStatus", "shipmentJob", "warehouseAPI.createShipment"]
}
```

### ValidationResult (output of Contract Validation Agent)
```json
{
  "rule_id": "RULE-001",
  "verdict": "VIOLATION",
  "explanation": "The new condition allows REFUNDED and CANCELLED orders (anything not literally CANCELLED) to reach createShipment().",
  "evidence": ["diff line 2", "docs/order-lifecycle.md:12-14"]
}
```
`verdict` is one of: `"OK"`, `"VIOLATION"`, `"NEEDS_EVIDENCE"`.

### SecurityFinding (output of Security & Access Agent)
```json
{
  "rule_id": "RULE-004",
  "risk_type": "cross-tenant-exposure",
  "verdict": "OK",
  "explanation": "No tenant/org_id field is touched by this diff."
}
```

### TestGap (output of Test Gap Agent)
```json
{
  "rule_id": "RULE-001",
  "has_coverage": false,
  "generated_test_path": "demo-repo/tests/generated/rule_001_regression.test.js",
  "generated_test_code": "<the full test file contents as a string>"
}
```

### AnalysisReport (final output of the whole pipeline — Evidence Report Agent)
```json
{
  "analysis_id": "run-2026-09-26-01",
  "pr_diff_summary": "Loosens the shipment guard from status === PAID to status !== CANCELLED",
  "impacted_rules": [ "...ImpactedRule objects..." ],
  "validation_results": [ "...ValidationResult objects..." ],
  "security_findings": [ "...SecurityFinding objects..." ],
  "test_gaps": [ "...TestGap objects..." ],
  "final_verdict": "BLOCK",
  "final_verdict_label": "BLOCK: Business Rule Violated",
  "summary_markdown": "<the human-readable PR-comment-ready markdown report>"
}
```
`final_verdict` is one of: `"SAFE"`, `"BLOCK"`, `"NEEDS_EVIDENCE"`.

## 6. Orchestrator API (FastAPI, built primarily by Member 2, called by Member 4's dashboard)

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/api/rules/extract` | `{ "repo_path": "demo-repo" }` | `{ "rules": [Rule, ...] }` — runs the Rule Miner and overwrites `data/rules.json` |
| GET | `/api/rules` | — | `{ "rules": [Rule, ...] }` — current contract graph |
| POST | `/api/analyze` | `{ "diff": "<raw git diff text>", "branch": "feature/cancel-status-bug" }` | `AnalysisReport` — runs the full pipeline |
| GET | `/api/report/{analysis_id}` | — | `AnalysisReport` |
| GET | `/api/health` | — | `{ "status": "ok" }` |

All request/response bodies must validate against the Pydantic models in Section 5. Return HTTP 200 with a body even on `BLOCK`/`VIOLATION` — those are valid successful analyses, not errors.

## 7. 48-hour timeline (shared checkpoints — each member's own file has the detailed hour-by-hour breakdown)

- **Hour 0–4:** Repo scaffolding, `.env.example`, stub `rules.json`, minimal `demo-repo/` with the seeded diff and 2–3 source docs. Everyone can start their own module against stubs.
- **Hour 4–16:** Each member builds their owned agent(s) independently against the schemas in Section 5.
- **Hour ~16 (Checkpoint 1):** Wire the real pipeline together end-to-end with whatever is real vs. stubbed; confirm the demo scenario at least runs, even if verdicts are rough.
- **Hour 16–30:** Replace stubs with real logic (real rule mining, real test generation, real security checks); dashboard shows live data.
- **Hour ~30 (Checkpoint 2):** Full before/after demo scenario works end-to-end and matches Section 3 exactly.
- **Hour 30–40:** Polish UI, write the 500-word Problem & Solution statement and 500-word Bob Usage statement, record the video, take Bob task-session screenshots from all 4 members.
- **Hour 40–48:** Buffer, bug fixes, final submission on lablab.ai.

## 8. Environment & config

`.env.example` (copy to `.env`, never commit `.env`):
```
WATSONX_API_KEY=
WATSONX_PROJECT_ID=
WATSONX_URL=
# Fallback if watsonx isn't available during the hackathon:
OPENAI_API_KEY=
GITHUB_TOKEN=
```
`llm_client.py` picks watsonx.ai if `WATSONX_API_KEY` is set, otherwise falls back to the OpenAI-compatible client, so no one is blocked if IBM watsonx access is delayed.

**Security note (from the hackathon rules):** never put real IBM Cloud credentials in a committed file. Use the provided GitHub IBM Hackathon repo template — it ships `.gitignore` and `.bobignore` specifically to prevent this.

## 9. Hackathon submission checklist (keep visible until submitted)

- [ ] Project Title, Short Description, Long Description (≤500 words), IBM Bob Usage Statement (≤500 words), Technology & Category tags
- [ ] Public code repository (GitHub/GitLab/Bitbucket), using the IBM hackathon template
- [ ] IBM Bob task session summary screenshots from **each of the 4 members**, committed to `docs/bob-screenshots/<name>/`
- [ ] Demo application platform + live Application URL
- [ ] Cover image
- [ ] Video demonstration, ≤3 minutes total, ≥90 seconds of the solution actually running (the before/after demo in Section 3)
- [ ] Slide presentation
- [ ] Repository is publicly accessible with no exposed credentials

**Judging criteria to keep in mind while building:** Application of Technology (how well Bob 2.0 features — full repo context, document understanding, agent mode, parallel subagents — are used), Presentation, Business Value, Originality.

## 10. Definition of done (MVP for the demo)

- Rule Miner produces at least 8 rules from `demo-repo/`, including the shipment rule verbatim or near-verbatim to Section 3.
- Given the seeded buggy diff, `/api/analyze` returns `final_verdict: "BLOCK"`, citing the correct rule, the call chain, and a generated failing test.
- After the diff is reverted to the fixed version, re-running `/api/analyze` returns `final_verdict: "SAFE"`.
- Dashboard visibly shows both runs (before/after) and the rule graph.
- All 4 members have their Bob screenshots committed.

## 11. Team

- **Member 1 — Rule Intelligence:** `member-1-rule-intelligence.md`
- **Member 2 — Impact & Validation Engine:** `member-2-impact-validation-engine.md`
- **Member 3 — Test Gap, Security & Demo Repo:** `member-3-test-gap-security-demo-repo.md`
- **Member 4 — Reporting, Dashboard & Submission:** `member-4-reporting-dashboard-submission.md`
