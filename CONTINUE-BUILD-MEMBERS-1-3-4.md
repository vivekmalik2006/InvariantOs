# InvariantOS — Continue Build (Members 1, 3, 4)
### Upload this together with: `00-invariantos-project-overview.md`, `member-1-rule-intelligence.md`,
### `member-3-test-gap-security-demo-repo.md`, and `member-4-reporting-dashboard-submission.md`.
### You do NOT need to upload `member-2-impact-validation-engine.md` — that work is already done and
### already sitting in this repo. Read this file FIRST, before any of the member files.

---

## 0. Instructions for IBM Bob — read this before touching any file

You are continuing a hackathon project that is **partially built already**. This is not a fresh scaffold.
A teammate (Member 2) already built and pushed real, working code into this exact repo. Your job in this
session is to complete the remaining three members' scope (1, 3, and 4) **without breaking or duplicating
what Member 2 already built.**

Rules for this session:
1. **Do not ask clarifying questions.** Where something is ambiguous, make the most reasonable assumption,
   write a one-line `# ASSUMPTION:` comment next to it, and keep moving. Work start-to-finish in one
   continuous run.
2. **Before writing any code, run a full inventory of the repo** (list every file under `orchestrator/`,
   `demo-repo/`, `docs/`) and report back what you find, matching it against Section 1 below. Confirm your
   understanding of what's real vs. placeholder before proceeding to Section 2's build order.
3. **Never modify the "already real" files list in Section 1** unless they fail to import or are
   objectively broken. If you must touch one of them to fix a genuine bug, make the smallest possible
   change and clearly comment why.
4. Commit after each numbered step in Section 2, with a clear commit message, exactly as the original
   overview's Section 0 instructs.
5. Never hardcode or commit API keys/secrets. `.env` is gitignored — if it's missing, create it from
   `.env.example` and leave the key values blank for the human to fill in; do not invent fake keys.
6. At the end of the session, save a Bob task-session screenshot to
   `docs/bob-screenshots/<member-name>/` for each role you completed in this session (e.g. if you do all
   three, create all three folders).

---

## 1. Current repo state — what already exists and must NOT be rebuilt

Member 2 already built and pushed these as **real, working, tested code**. Treat them as correct
foundations to build on top of, not things to regenerate:

- `orchestrator/main.py` — FastAPI app, all 5 endpoints from overview Section 6
- `orchestrator/orchestrator.py` — the pipeline (`run_pipeline()`), including parallel agent execution
- `orchestrator/diff_utils.py` — diff parsing utility
- `orchestrator/agents/change_impact.py` — real `find_impacted_rules()`
- `orchestrator/agents/contract_validator.py` — real `validate()`, fail-closed to `NEEDS_EVIDENCE`

These two also already exist from Member 2's session — **verify** they match the overview's Section 5 /
Section 4 spec exactly; only patch them if they're genuinely broken or don't match the schema, don't
rewrite them wholesale:

- `orchestrator/schemas.py`
- `orchestrator/llm_client.py`

These exist in the repo right now but are **stubs, placeholders, or duplicated content that must be
replaced with the real thing** — this is most of the actual work left to do:

- `orchestrator/agents/rule_miner.py` — currently a stub → needs the real `mine_rules()` (Member 1)
- `orchestrator/data/rules.json` — currently a hand-written placeholder → needs real LLM-mined output
  (Member 1)
- `demo-repo/` — currently a minimal placeholder version → needs to be replaced with the full real version
  described in `member-3-test-gap-security-demo-repo.md` (Member 3)
- `orchestrator/agents/security_access.py` — currently a stub → needs the real `check()` (Member 3)
- `orchestrator/agents/test_gap.py` — currently a stub → needs the real `analyze()` (Member 3)
- `orchestrator/agents/evidence_report.py` — currently a stub → needs the real `generate()` (Member 4)

These have not been started at all:

- `dashboard/app.py` (Member 4)
- `docs/demo-script.md` (Member 4)
- `docs/architecture.md` (co-owned Member 2/4 — check if it exists; if not, write it)
- Submission text: Long Description, Bob Usage Statement, tags (Member 4)

---

## 2. Build order for this session — do all of this in one continuous run

1. **Inventory the repo** as instructed in Section 0, rule 2. Confirm the lists in Section 1 above are
   accurate before writing code.

2. **Member 1's scope — Rule Intelligence.**
   - Verify/finish `orchestrator/schemas.py` against overview Section 5.
   - Verify/finish `orchestrator/llm_client.py`'s `complete()` function.
   - Build the real `orchestrator/agents/rule_miner.py`: `mine_rules(repo_path)` per
     `member-1-rule-intelligence.md` step 5 — walk `docs/**/*.md`, `postmortems/**/*.md`,
     `tickets/**/*.md`, source comments, test names; chunk text; call `llm_client.complete()`; validate
     against `Rule`; dedupe; write to `data/rules.json`. **Do not run this against demo-repo yet** — wait
     until step 3 replaces it with the real one, or your mined rules will be based on placeholder content.

3. **Member 3's scope — Demo Repo, Security, Test Gap.**
   - Replace the placeholder `demo-repo/` entirely with the full version described in
     `member-3-test-gap-security-demo-repo.md`: `src/orders.js`, `shipments.js`, `warehouseApi.js`,
     realistic Jest tests, `docs/order-lifecycle.md`, postmortems, tickets, ≥8 rules' worth of surface
     area across the repo, the `feature/cancel-status-bug` branch with the exact seeded bug from overview
     Section 3, and `demo-repo/seeded-diff.patch` matching that branch's diff exactly.
   - Build the real `orchestrator/agents/security_access.py`: `check()` — heuristic regex scan + LLM
     confirmation, fail-closed to flagging when uncertain.
   - Build the real `orchestrator/agents/test_gap.py`: `analyze()` — coverage detection, LLM-generated
     regression test written to `demo-repo/tests/generated/rule_001_regression.test.js`. **Actually run
     `npx jest`** on both `main` and `feature/cancel-status-bug` to confirm the generated test fails on
     the buggy branch and passes on the fix — this is required, not optional.

4. **Re-run the Rule Miner against the now-real demo-repo.** Run `mine_rules("demo-repo")` again now that
   step 3 has replaced the placeholder. Confirm ≥8 valid rules come out, including `RULE-001` with
   accurate `source_refs` pointing at the real `docs/order-lifecycle.md`. Overwrite `data/rules.json` with
   this real output.

5. **Member 4's scope — Reporting & Dashboard.**
   - Build the real `orchestrator/agents/evidence_report.py`: `generate()` — PR-comment-style
     `summary_markdown` with headline verdict, bulleted impacted rules with explanations, call chain, and
     generated test paths/links, per `member-4-reporting-dashboard-submission.md` step 2.
   - Build `dashboard/app.py` (Streamlit): Rule Graph page, Analyze-a-PR page with one-click buggy/fixed
     diff buttons and `st.status()` progress steps, and a Result page rendering `summary_markdown` with a
     verdict badge.
   - Write `docs/demo-script.md` and `docs/architecture.md` if not already present.

6. **Confirm `orchestrator.py` calls the real agents, not the old stubs.** Since Member 2 built
   `orchestrator.py` to call function signatures, not hardcoded stub logic, it should already work once the
   real functions above exist at those same import paths — verify this rather than rewriting
   `orchestrator.py`.

7. **Run the full end-to-end pipeline twice:**
   - Seeded buggy diff → confirm `final_verdict: "BLOCK"`, citing `RULE-001`, the correct call chain
     (`cancelOrder → updateOrderStatus → shipmentJob → warehouseAPI.createShipment`), and a non-empty
     explanation.
   - Fixed diff (on `main`) → confirm `final_verdict: "SAFE"`.
   - If either returns `NEEDS_EVIDENCE` instead, check that a real `WATSONX_API_KEY` or `OPENAI_API_KEY`
     is set in `.env` — this is the fail-closed default when no LLM is reachable, not a bug in your code.

8. **Report final status** at the end of the session: what's fully done, what (if anything) still needs a
   human (e.g. filling in `.env`, recording the video, writing submission text that needs real team
   details).

## Definition of done for this session

- `data/rules.json` has ≥8 real, LLM-mined rules including `RULE-001`.
- `demo-repo/` has both branches, matches the seeded bug exactly, and `seeded-diff.patch` matches it.
- `security_access.check()` and `test_gap.analyze()` are real, not stubs, and the generated regression
  test is verified to fail on the buggy branch and pass on `main`.
- `evidence_report.generate()` produces readable `summary_markdown`, not a raw JSON dump.
- `dashboard/app.py` runs and calls the real `/api/analyze` endpoint end-to-end.
- The buggy-diff → `BLOCK` and fixed-diff → `SAFE` demo scenario runs correctly through the whole merged
  pipeline, not just in isolation.
