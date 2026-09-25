# Postmortem: PM-2024-03 — 47 Ghost Shipments Dispatched for Cancelled Orders

**Date:** 2024-03-14  
**Severity:** P0 — Production Incident  
**Reported by:** Ops Team  
**Resolution time:** 6 hours  

---

## Summary

A background batch job that re-processes orders in certain edge states was inadvertently triggered on a set of CANCELLED orders. Because the shipment guard condition had recently been widened from `status === 'PAID'` to `status !== 'PROCESSING_ERROR'`, cancelled orders were no longer blocked from passing through `shipmentJob()`. The warehouse API received 47 valid `createShipment` calls for orders that customers had explicitly cancelled.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 03:12 | Batch job triggered as part of overnight "retry-pending-orders" cron. |
| 03:13 | Shipment API begins receiving requests for orders with status=CANCELLED. |
| 04:45 | On-call engineer notices spike in `createShipment` calls; investigates. |
| 05:00 | Root cause identified: guard condition in `shipmentJob` changed in PR #847. |
| 05:15 | Hot patch deployed: guard reverted to `order.status === 'PAID'`. |
| 09:00 | Warehouse team contacted; 31 of 47 shipments physically recalled. 16 already picked up. |

---

## Root Cause

PR #847 changed the guard in `shipmentJob` from:

```javascript
if (order.status === 'PAID') {
  createShipment(order);
}
```

to:

```javascript
if (order.status !== 'PROCESSING_ERROR') {
  createShipment(order);
}
```

The intent was to allow PENDING orders in a specific retry queue to pass through. The change was made without recognising that CANCELLED orders would now also match `!== 'PROCESSING_ERROR'`.

---

## Impact

- 47 shipments dispatched for cancelled orders.
- 16 could not be recalled — physical goods dispatched, no revenue.
- Estimated loss: $3,200.
- Customer support tickets: 31 (all cancelled-order customers receiving unexpected deliveries).

---

## Corrective Actions

1. **Immediate:** Guard reverted to `order.status === 'PAID'` — the only status that should ever proceed to shipment.
2. **Rule formalised:** Added RULE-001 to `docs/order-lifecycle.md` — "A cancelled order must never be shipped."
3. **Regression test added:** `tests/shipments.test.js` now explicitly tests that CANCELLED status does not call `warehouseApi.createShipment`.
4. **PR gate added:** Any PR touching `shipmentJob` or `createShipment` now requires a second review specifically checking RULE-001.

---

## Lessons Learned

- Negative guards (`!== X`) are dangerous for state machine transitions. Always use positive allowlisting (`=== 'PAID'`).
- Business invariants must be written down in a canonical location (not just in tests) so that reviewers can check PRs against them.
- The absence of a regression test for the CANCELLED→shipment path was the primary control failure.
