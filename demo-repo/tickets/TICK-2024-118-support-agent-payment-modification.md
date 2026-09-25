# Ticket TICK-2024-118 — Support Agent Modified Customer Payment Amount

**Type:** Security / Access Control Violation  
**Priority:** Critical  
**Status:** Closed — Fixed  
**Reporter:** Security Team  
**Assignee:** IAM Squad  

---

## Description

A support agent (`role: support_agent`) was able to call `updatePaymentDetails()` and change a customer's payment amount from $299 to $0, effectively issuing a full refund disguised as a payment modification. This is a RULE-004 violation: support agents must only VIEW payment details, not modify them.

---

## Root Cause

The `updatePaymentDetails()` endpoint did not enforce role-based access control. Any authenticated user, regardless of role, could call it.

```javascript
// Before (broken — no role check):
function updatePaymentDetails(order, updates) {
  return { ...order, ...updates };
}
```

---

## Impact

- 3 incidents confirmed where support agents modified payment amounts.
- Estimated fraudulent loss: $1,450.
- GDPR notification filed — payment data modified without customer consent.

---

## Fix

Added `ROLE_PERMISSIONS` map and role check to `updatePaymentDetails()`:

```javascript
function updatePaymentDetails(role, order, updates) {
  const permissions = ROLE_PERMISSIONS[role] || [];
  if (!permissions.includes('modify_payment')) {
    throw new Error(`Role '${role}' is not permitted to modify payment details — RULE-004.`);
  }
  return { ...order, ...updates };
}
```

`support_agent` role only has `['view_payment', 'view_orders']` — no `modify_payment`.

---

## Acceptance Criteria

- [ ] Calling `updatePaymentDetails('support_agent', order, updates)` throws.
- [ ] Calling `updatePaymentDetails('admin', order, updates)` succeeds.
- [ ] `getPaymentDetails('support_agent', order)` still works (read is allowed).
