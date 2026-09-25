# InvariantOS — Demo Script (≤3 minutes)

> **Video target:** ≤3 minutes total.  
> **Required:** ≥90 seconds of the solution actually running (Sections 3–5 below).  
> **Audience:** hackathon judges and developers.

---

## Section 1 — Problem Setup (0:00 – 0:45)

**Narrator (voice-over or on-screen text):**

> "This is a real-looking PR. It changes one condition in an order processing service.
> It passes CI — all 35 unit tests pass. Static analysis gives it a green light.
> A code reviewer looks at it and says 'looks fine to me.'
>
> But it contains a silent semantic regression.
>
> The change widens the shipment guard from `status === 'PAID'`
> to `status !== 'CANCELLED'`.
>
> That means REFUNDED orders, PENDING orders, and DELIVERED orders will now also
> trigger shipment creation. The very next cancelled order that goes through this
> code will get shipped — a physical package dispatched with no valid sale behind it.
>
> Normal CI won't catch this. No existing test covers this case.
> And the rule that says 'a cancelled order must never be shipped' exists only in a
> postmortem doc that nobody reads before merging."

**Show on screen:** The PR diff side-by-side (two lines, minus/plus).

---

## Section 2 — InvariantOS Solution Overview (0:45 – 1:00)

**Narrator:**

> "InvariantOS automatically mines the hidden business rules from your repo —
> docs, postmortems, tickets, source comments — and creates a Behavioral Contract Graph.
> When a PR arrives, a pipeline of AI agents checks whether it violates any rule,
> generates a failing regression test as proof, and gives you an evidence-backed verdict."

**Show on screen:** The architecture diagram from `docs/architecture.md`.

---

## Section 3 — Live Demo Part 1: Buggy Diff → BLOCK (1:00 – 2:00)

**Screen recording instructions:**

1. Open the **InvariantOS Dashboard** at `http://localhost:8501`.
2. Navigate to **🗂️ Rule Graph** — show the 8 mined rules, zoom in on **RULE-001**.
   - *"These rules were automatically mined from demo-repo — docs, postmortems, tickets."*
3. Navigate to **🔍 Analyze a PR**.
4. Click **🐛 Load Buggy Diff** — the seeded diff loads automatically.
5. Click **🚀 Analyze**.
6. Watch the progress steps animate: *Mapping impact... → Validating contracts... → Checking security... → Checking test coverage... → Generating report...*
7. The verdict banner appears: **🛑 BLOCK: Business Rule Violated**
8. Navigate to **📊 Result**.
9. Show the rendered `summary_markdown`:
   - Headline verdict badge
   - **RULE-001** section: why it's impacted, the call chain (`cancelOrder → updateOrderStatus → shipmentJob → warehouseAPI.createShipment`), the validation explanation
   - Generated regression test path
10. Expand the RULE-001 details panel — show the generated test code.

**Narrate:**
> "InvariantOS found the violation: RULE-001 — 'A cancelled order must never be shipped.'
> It traced the call chain, explained why the diff violates the rule, and generated
> a failing regression test proving it. The PR is blocked."

---

## Section 4 — Live Demo Part 2: Fixed Diff → SAFE (2:00 – 2:40)

**Screen recording instructions:**

1. Stay on or navigate back to **🔍 Analyze a PR**.
2. Click **✅ Load Fixed Diff** — the reverted diff loads.
3. Click **🚀 Analyze** again.
4. The verdict banner appears: **✅ SAFE TO MERGE**
5. Navigate to **📊 Result** — show the clean result.

**Narrate:**
> "After applying the one-line fix — restoring `status === 'PAID'` — InvariantOS confirms
> the rule is upheld. Safe to merge."

---

## Section 5 — Closing (2:40 – 3:00)

**Narrator:**

> "InvariantOS turns scattered institutional knowledge — postmortems, tickets, comments —
> into a living, machine-checkable contract. Every PR is automatically verified against it.
>
> Semantic regressions that would normally reach production are caught at the gate,
> with evidence, every time."

**Show on screen:** The before/after verdict comparison (side-by-side screenshots or split screen: 🛑 BLOCK → ✅ SAFE).

---

## Shot Checklist

- [ ] Terminal showing `uvicorn orchestrator.main:app` running (shows system is live)
- [ ] Rule Graph page — all 8 rules visible, RULE-001 expanded
- [ ] Analyze page — buggy diff loaded
- [ ] Progress animation — all 5 steps visible
- [ ] Result page — BLOCK verdict with full summary_markdown rendered
- [ ] RULE-001 detail panel — call chain + generated test visible
- [ ] Fixed diff analysis — SAFE verdict
- [ ] Optional: split-screen comparison of both results

## Timing Notes

| Section | Duration | Key Visual |
|---|---|---|
| Problem setup | 0:45 | The 2-line diff + "all tests pass" CI green |
| Solution overview | 0:15 | Architecture diagram |
| Buggy diff → BLOCK | 1:00 | Progress animation + BLOCK verdict + call chain |
| Fixed diff → SAFE | 0:40 | SAFE verdict |
| Closing | 0:20 | Before/after split |
| **Total** | **3:00** | |
