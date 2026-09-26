import urllib.request, json

FIXED_DIFF = """diff --git a/src/shipments.js b/src/shipments.js
index 9e29379..b48634b 100644
--- a/src/shipments.js
+++ b/src/shipments.js
@@ -22,9 +22,7 @@ const { decrementInventory } = require('./inventory');
  */
 async function shipmentJob(order) {
   // RULE-001: guard - only PAID orders may be shipped
-  // BUG: this condition was changed from === 'PAID' to !== 'CANCELLED'
-  // which allows REFUNDED, PENDING, and other non-paid statuses to trigger shipment
-  if (order.status !== 'CANCELLED') {
+  if (order.status === 'PAID') {
     return await createShipment(order);
   }
"""

payload = json.dumps({'diff': FIXED_DIFF, 'branch': 'main'}).encode()
req = urllib.request.Request(
    'http://127.0.0.1:8000/api/analyze',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
r = urllib.request.urlopen(req, timeout=90)
result = json.loads(r.read().decode())

print("=== FIXED DIFF RESULT ===")
print("final_verdict      :", result['final_verdict'])
print("final_verdict_label:", result['final_verdict_label'])
print("impacted_rules     :", [x['rule_id'] for x in result['impacted_rules']])
print()
print("validation_results:")
for v in result['validation_results']:
    print(" ", v['rule_id'], "->", v['verdict'])
    print("   ", v['explanation'][:100])
