# Postmortem: PM-2024-08 — Duplicate Discount Code Application (RULE-003 Breach)

**Date:** 2024-08-22  
**Severity:** P1 — Revenue Impact  
**Reported by:** Finance Team  
**Resolution time:** 2 hours  

---

## Summary

A race condition in the discount validation pathway allowed the same customer to apply the `SUMMER20` promotional code multiple times within a short time window. The validation check was non-atomic — it read the "used codes" table and only inserted the record after applying the discount, meaning concurrent requests could both pass the read-check before either had written.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:03 | Customer `cust-88421` submits two checkout requests within 800ms. |
| 14:03 | Both requests pass `validateDiscountCode('cust-88421', 'SUMMER20')` — neither has inserted the usage record yet. |
| 14:03 | Both discounts applied. Customer receives 40% total discount instead of 20%. |
| 15:30 | Finance team flags anomaly in revenue report. |
| 16:00 | Root cause confirmed — race condition in `validateDiscountCode` / `applyDiscount`. |
| 16:20 | Fix deployed: discount usage tracked with a unique constraint + atomic insert. |

---

## Root Cause

`validateDiscountCode` checked whether a record existed in a read-only query, then `applyDiscount` inserted the usage record in a separate step. Under concurrent load these two steps are not atomic, allowing multiple requests to pass the check before any of them commits the usage record.

---

## Impact

- 4 customers exploited the race window during the SUMMER20 campaign.
- Total revenue loss: $847.
- No customer-facing errors — all requests appeared to succeed normally.

---

## Corrective Actions

1. Discount code usage now tracked via an atomic `INSERT ... ON CONFLICT DO NOTHING` query.
2. RULE-003 added to `docs/order-lifecycle.md`.
3. Unit test added: `tests/discounts.test.js` validates that second application of same code throws.

---

## Lessons Learned

- Validation and commitment must be atomic for idempotency-sensitive operations.
- "Check then act" patterns are inherently race-prone; always prefer "act and handle constraint violation."
