"""
End-to-end pipeline integration test using the seeded diff.
No LLM is required — the pipeline uses deterministic pass-1 impact detection
and falls back to NEEDS_EVIDENCE when the LLM is unavailable.
Demonstrates the full run_pipeline() call and report structure.
"""
import sys, json
sys.path.insert(0, '.')

from orchestrator.orchestrator import run_pipeline

SEEDED_DIFF = r"""diff --git a/src/shipments.js b/src/shipments.js
index a1b2c3d..e4f5g6h 100644
--- a/src/shipments.js
+++ b/src/shipments.js
@@ -30,7 +30,7 @@ async function shipmentJob(order) {
  * @returns {Promise<Object|null>} shipment record
  */
 async function shipmentJob(order) {
-  if (order.status === "PAID") {
+  if (order.status !== "CANCELLED") {
     return await warehouseApi.createShipment(order);
   }
   console.log(`[shipmentJob] Skipped — order has status not PAID.`);
   return null;
 }
"""

FIXED_DIFF = r"""diff --git a/src/README.md b/src/README.md
index 0000001..0000002 100644
--- a/src/README.md
+++ b/src/README.md
@@ -1,3 +1,4 @@
 # Demo repo
+Added a comment.
"""

print("=" * 60)
print("TEST 1: Seeded buggy diff (expect BLOCK or NEEDS_EVIDENCE with RULE-001)")
print("=" * 60)
report = run_pipeline(SEEDED_DIFF)
print(f"analysis_id:     {report.analysis_id}")
print(f"final_verdict:   {report.final_verdict}")
print(f"final_label:     {report.final_verdict_label}")
print(f"impacted_rules:  {[r.rule_id for r in report.impacted_rules]}")
print(f"validation:      {[(v.rule_id, v.verdict) for v in report.validation_results]}")
print(f"test_gaps:       {[(t.rule_id, t.has_coverage) for t in report.test_gaps]}")
print()
print("Summary markdown:")
print(report.summary_markdown[:800].encode('ascii', errors='replace').decode('ascii'))
print()

assert 'RULE-001' in [r.rule_id for r in report.impacted_rules], "FAIL: RULE-001 not in impacted rules"
assert report.final_verdict in ('BLOCK', 'NEEDS_EVIDENCE'), f"FAIL: expected BLOCK or NEEDS_EVIDENCE, got {report.final_verdict}"
print(f"PASS: seeded diff produced {report.final_verdict} and identified RULE-001")

print()
print("=" * 60)
print("TEST 2: Fixed diff (unrelated change — expect SAFE)")
print("=" * 60)
report2 = run_pipeline(FIXED_DIFF)
print(f"final_verdict:   {report2.final_verdict}")
print(f"impacted_rules:  {[r.rule_id for r in report2.impacted_rules]}")
assert report2.final_verdict == 'SAFE', f"FAIL: expected SAFE for fixed diff, got {report2.final_verdict}"
print("PASS: fixed diff produced SAFE")

print()
print("ALL END-TO-END TESTS PASSED")
