# Ticket TICK-2024-105 — SUMMER20 Discount Code Applied 4 Times to Same Customer

**Type:** Bug  
**Priority:** High  
**Status:** Closed — Fixed  
**Reporter:** Finance Team  
**Assignee:** Promotions Squad  

---

## Description

Customer `cust-88421` applied the promotional discount code `SUMMER20` (20% off) four times across four separate checkout sessions between August 22–23, 2024. Total discount applied: $200 against expected $50 (one application).

---

## Investigation

- Code shows `validateDiscountCode(customerId, discountCode)` reads from DB.
- `applyDiscount()` inserts usage record only after applying discount to cart.
- No atomicity or unique constraint — concurrent/sequential applications all pass validation.
- No server-side session lock prevents rapid reuse.

---

## Root Cause

The `validateDiscountCode` / `applyDiscount` sequence is non-atomic:

```javascript
// Check
if (!validateDiscountCode(customerId, discountCode)) throw error;

// Gap here — another request can pass the check before this insert runs
_usedDiscounts.add(`${customerId}:${discountCode}`);
```

---

## Fix Required

1. Enforce atomicity: treat the check+record as a single atomic operation.
2. Add RULE-003 to `docs/order-lifecycle.md`.
3. Add unit tests for `validateDiscountCode` and `applyDiscount` covering the double-use case.

---

## Acceptance Criteria

- [ ] Second call to `applyDiscount(order, customerId, sameCode)` throws.
- [ ] `validateDiscountCode` returns false on second call with same (customerId, code) pair.
- [ ] No race condition possible — atomic write.
