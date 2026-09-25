# Member 4 — Reporting, Dashboard & Submission
### Owns: Evidence Report Agent, the Streamlit dashboard, integration QA, and the hackathon submission package

> Upload this file together with `00-invariantos-project-overview.md`. Read the overview first — this file assumes you know the architecture, folder layout, and data contracts already defined there.

## Your mission

You build the piece the judges will actually watch: the Evidence Report that turns raw agent output into a clear verdict, and the dashboard that visualizes it live during the demo video. You also own pulling together everything the lablab.ai submission form requires.

## What you own

```
orchestrator/agents/evidence_report.py
dashboard/app.py                          # Streamlit dashboard
docs/demo-script.md                        # your shot list for the video
docs/architecture.md                        # (co-owned with Member 2)
Submission text: Long Description, IBM Bob Usage Statement, tags, cover image
```

## Step-by-step build

1. **Hour 0–2: build against mocks immediately.** Don't wait for real agents. Ask Member 1 for `schemas.py` as soon as it exists (~hour 2) and hand-write 2–3 realistic mock `AnalysisReport` JSON files (one `BLOCK` case using the seeded scenario from overview Section 3, one `SAFE` case, one `NEEDS_EVIDENCE` case). Build both `evidence_report.py` and `dashboard/app.py` against these mocks first, then swap to the real API once Member 2's endpoints are live (~hour 16).

2. **Hour 2–10: build the Evidence Report Agent.** `orchestrator/agents/evidence_report.py`:
   ```python
   def generate(diff_summary: str, impacted_rules, validation_results, security_findings, test_gaps) -> AnalysisReport:
       ...
   ```
   - Compute `final_verdict` is actually done in Member 2's `orchestrator.py` (per overview Section 6 step 5) — your job here is to render the **human-readable** `summary_markdown`: a PR-comment-style report with a headline verdict (`✅ SAFE TO MERGE` / `🛑 BLOCK: Business Rule Violated` / `⚠️ NEEDS EVIDENCE`), a bulleted list of impacted rules with their validation explanations, the call chain, and links/paths to any generated tests.
   - Model the tone directly on the idea doc's example: *"This PR changes the order-cancellation flow. It violates the rule 'cancelled orders must not be shipped.' Here is the affected call chain, the missing condition, a generated failing test, and the smallest corrective patch."*
   - Also generate a short (1–2 sentence) `pr_diff_summary` describing what the diff does in plain English (small LLM call via `llm_client.complete()`, or a simple heuristic off the diff_utils output if you want to avoid the extra call).
   - Assemble and return the full `AnalysisReport` object, validated against the schema.

3. **Hour 10–24: build the Streamlit dashboard.** `dashboard/app.py`, calling the FastAPI backend (`orchestrator/main.py`) over HTTP:
   - **Page 1 — Rule Graph:** fetch `GET /api/rules`, show the rules as a filterable table (category, severity, tags) and, if time allows, a simple graph view (e.g. `streamlit-agraph` or a Graphviz DOT rendered with `st.graphviz_chart`) connecting rules to their `related_functions`/`related_entities`.
   - **Page 2 — Analyze a PR:** a dropdown or text area to paste/select a diff (pre-load the seeded buggy diff and the fixed diff as one-click demo buttons), a big "Analyze" button that calls `POST /api/analyze`, and a live-feeling progress display while it runs (Streamlit `st.status()` blocks labeled "Mapping impact...", "Validating contracts...", "Checking security & access...", "Checking test coverage...", "Generating report..." — even if the backend runs them in under a second, keep the UI steps visible for ~1s each so the parallel-subagents story reads clearly on camera).
   - **Page 3 — Result:** render `summary_markdown`, a colored verdict badge, an expandable section per impacted rule showing the `ValidationResult` explanation and evidence, and a link/preview of any `generated_test_code`.
   - Make sure running the buggy diff and then the fixed diff side-by-side (or in quick succession) makes the before/after contrast obvious — this is the money shot for the video.

4. **Hour ~16 and ~30: Checkpoints.** At hour 16, swap the dashboard from mock data to the real `/api/analyze` endpoint. At hour 30, run through the full demo flow yourself exactly as it will appear in the video, timing it, and flag any rough edges to the relevant owner immediately (you are the de facto QA lead for the last third of the hackathon).

5. **Hour 30–40: submission assets.**
   - Write the **Long Description / Problem & Solution Statement** (≤500 words): problem, solution, target users (engineering teams shipping fast with thin test coverage of business logic), how they'd interact with it (PR bot comment + dashboard), why it's original (rules-as-code mined automatically instead of hand-written, evidence-based verdicts instead of vague "looks risky" comments).
   - Write the **IBM Bob Usage Statement** (≤500 words): be specific about what each of the 4 members actually used Bob for in their IDE (scaffolding files, writing agent logic, generating tests, debugging the FastAPI/Streamlit integration, understanding the sample repo) — pull real specifics from each member once their sections are done, don't write it generically.
   - Pick Technology & Category tags (e.g. AI agents, developer tools, code review automation, DevOps, watsonx.ai if used).
   - Write `docs/demo-script.md`: a shot-by-shot script for the ≤3-minute video — roughly 60–75s problem setup (show the harmless-looking PR passing CI), then ≥90s live demo (mine rules → analyze buggy diff → BLOCK verdict with evidence → apply fix → re-analyze → SAFE), narrated.
   - Collect a cover image (a clean screenshot of the dashboard's Result page showing a BLOCK verdict works well).
   - Collect all 4 members' Bob task-session screenshots into `docs/bob-screenshots/` and confirm they're committed.
   - Confirm the repo is public, has no exposed credentials (double-check `.env` is gitignored, not just `.env.example`), and follows the IBM hackathon repo template.

6. **Hour 40–48.** Final read-through of all submission fields against the checklist in overview Section 9, record the video, submit on lablab.ai with buffer time before the deadline.

## Definition of done

- `evidence_report.generate()` produces a `summary_markdown` that reads like a real PR review comment, not a raw JSON dump.
- The dashboard runs the full buggy→BLOCK and fixed→SAFE flow live, end to end, against the real backend.
- Long Description and Bob Usage Statement are both written, proofread, and under 500 words each.
- Every item in overview Section 9's submission checklist is checked off before the deadline.

## Handoffs

- Tell Member 2 immediately if any field in `AnalysisReport` doesn't render cleanly in the dashboard — you're the first person who will notice a schema gap in practice.
- Ask all 3 other members for their specific Bob usage details by hour ~36 so the Usage Statement is accurate, not generic.
