import sys
sys.path.insert(0, '.')

# ── Test diff_utils against the seeded diff ──
from orchestrator.diff_utils import parse_diff

SEEDED_DIFF = r"""
diff --git a/src/shipments.js b/src/shipments.js
index a1b2c3d..e4f5g6h 100644
--- a/src/shipments.js
+++ b/src/shipments.js
@@ -30,7 +30,7 @@ async function shipmentJob(order) {
  */
 async function shipmentJob(order) {
-  if (order.status === "PAID") {
+  if (order.status !== "CANCELLED") {
     return await warehouseApi.createShipment(order);
   }
"""

parsed = parse_diff(SEEDED_DIFF)
print('Changed files:', parsed.changed_files)
print('Changed symbols:', parsed.changed_symbols)
print('Added lines:', parsed.added_lines)
print('Removed lines:', parsed.removed_lines)

assert 'src/shipments.js' in parsed.changed_files, 'FAIL: changed file not detected'
# shipmentJob should be detected from @@ hunk header
assert any('shipmentJob' in s for s in parsed.changed_symbols), f'FAIL: shipmentJob not detected in {parsed.changed_symbols}'
print('diff_utils seeded diff test PASSED')

# ── Test Change Impact (deterministic pass only — no LLM) ──
import json
from pathlib import Path
from orchestrator.schemas import Rule
from orchestrator.agents.change_impact import _pass1_deterministic

rules_raw = json.loads(Path('orchestrator/data/rules.json').read_text())
rules = [Rule(**r) for r in rules_raw]

candidates = _pass1_deterministic(parsed, rules)
print('Pass-1 candidate rule IDs:', [r.id for r in candidates])
assert any(r.id == 'RULE-001' for r in candidates), 'FAIL: RULE-001 not found by pass-1'
print('Change Impact pass-1 test PASSED (RULE-001 detected)')

# ── Test full pipeline (LLM is skipped — falls back to pass-1 results) ──
from orchestrator.orchestrator import run_pipeline, _compute_verdict
from orchestrator.schemas import ValidationResult, SecurityFinding, TestGap

# Simulate VIOLATION verdict
vr_violation = [ValidationResult(rule_id='RULE-001', verdict='VIOLATION', explanation='test', evidence=[])]
verdict, label = _compute_verdict(vr_violation, [], [], rules)
assert verdict == 'BLOCK', f'FAIL: expected BLOCK, got {verdict}'
print('Verdict BLOCK test PASSED')

# Simulate SAFE verdict
vr_ok = [ValidationResult(rule_id='RULE-001', verdict='OK', explanation='fine', evidence=[])]
verdict, label = _compute_verdict(vr_ok, [], [], rules)
assert verdict == 'SAFE', f'FAIL: expected SAFE, got {verdict}'
print('Verdict SAFE test PASSED')

# Simulate NEEDS_EVIDENCE verdict
vr_ne = [ValidationResult(rule_id='RULE-001', verdict='NEEDS_EVIDENCE', explanation='unsure', evidence=[])]
verdict, label = _compute_verdict(vr_ne, [], [], rules)
assert verdict == 'NEEDS_EVIDENCE', f'FAIL: expected NEEDS_EVIDENCE, got {verdict}'
print('Verdict NEEDS_EVIDENCE test PASSED')

print()
print('ALL TESTS PASSED')
