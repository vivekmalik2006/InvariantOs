# Ticket TICK-2024-091 — Optimistic Payment Marking Caused 12 Ghost Shipments (Q1 2024)

**Type:** Bug  
**Priority:** Critical  
**Status:** Closed — Fixed  
**Reporter:** Platform Engineering  
**Assignee:** Backend Team  

---

## Description

During Q1 2024, `processOrder()` was changed to mark orders PAID immediately after the payment gateway responded, without waiting for the asynchronous confirmation webhook. The intent was to reduce perceived checkout latency.

This caused 12 orders to be marked PAID and subsequently shipped before the payment gateway confirmed the charge. When gateway confirmation finally arrived (or failed), 12 orders had already been shipped but payment had not cleared.

---

## Steps to Reproduce

1. Call `processOrder()` with a payment that has `status: 'PENDING_GATEWAY'`.
2. Observe: `updateOrderStatus(order, 'PAID')` is called immediately.
3. `shipmentJob()` fires, sees `status === 'PAID'`, creates shipment.
4. Payment gateway later returns `status: 'FAILED'` — order is now PAID+SHIPPED with no revenue.

---

## Root Cause

The `confirmPayment()` call was moved from synchronous (blocking) to fire-and-forget in PR #1103:

```javascript
// Before (correct — RULE-007):
const confirmed = await confirmPayment(paymentInfo);
if (!confirmed) throw new Error('Payment not confirmed');
const paidOrder = updateOrderStatus(order, 'PAID');

// After (broken):
confirmPayment(paymentInfo);  // fire and forget — NOT awaited
const paidOrder = updateOrderStatus(order, 'PAID');  // always reaches here
```

---

## Fix

Reverted PR #1103. `confirmPayment()` must be awaited and the result checked before transitioning to PAID.

Added RULE-007 to `docs/order-lifecycle.md`: "Payment must be confirmed before an order is marked PAID."

---

## Acceptance Criteria

- [ ] `processOrder()` awaits `confirmPayment()` and throws if it returns false.
- [ ] Unit test: `processOrder()` with `confirmPayment` returning false must throw.
- [ ] Integration test: end-to-end order with failed payment never reaches SHIPPED.
