# Order Lifecycle — Business Rules & State Machine

This document is the authoritative reference for how orders flow through the e-commerce platform. Every engineering change that touches order status, payment, or shipment logic **must** be reviewed against the rules in this document.

## 1. Order Status State Machine

Orders transition through a defined set of statuses. Not all transitions are valid.

```
PENDING ──► PAID ──► SHIPPED ──► DELIVERED
   │          │
   └──► CANCELLED (terminal)
              │
              └──► REFUNDED (terminal)
```

**Valid transitions:**

| From Status    | Allowed Next Statuses             |
|----------------|-----------------------------------|
| PENDING        | PAID, CANCELLED                   |
| PAID           | SHIPPED, CANCELLED, REFUNDED      |
| SHIPPED        | DELIVERED, RETURN_REQUESTED       |
| DELIVERED      | RETURN_REQUESTED, REFUNDED        |
| CANCELLED      | *(none — terminal)*               |
| REFUNDED       | *(none — terminal)*               |
| RETURN_REQUESTED | REFUNDED                        |

## 2. Critical Business Rules

### RULE-001 — Cancelled Orders Must Never Be Shipped

**Statement:** A cancelled order must never result in a shipment being created.

**Rationale:** Once an order reaches CANCELLED status, the customer has explicitly or automatically revoked their purchase intent. Creating a shipment for a cancelled order causes physical goods to be dispatched without a valid sale, resulting in inventory loss, customer confusion, and potential fraud exposure.

**Enforcement:** The `shipmentJob()` function must guard with `order.status === 'PAID'` before calling `warehouseAPI.createShipment()`. Any loosening of this condition (e.g., changing to `order.status !== 'CANCELLED'`) would allow REFUNDED, PENDING, and other non-paid statuses to trigger shipments.

**Source:** Internal postmortem PM-2024-03 — production incident where a batch job re-processed CANCELLED orders and dispatched 47 shipments.

**Related functions:** `cancelOrder`, `updateOrderStatus`, `shipmentJob`, `warehouseAPI.createShipment`

**Related entities:** Order, Shipment, OrderStatus

---

### RULE-006 — Shipped Orders Cannot Revert to PENDING or PAID

**Statement:** An order that has reached SHIPPED status must not be allowed to transition back to PENDING or PAID.

**Rationale:** Reverting a shipped order to PENDING or PAID would allow the same physical shipment to be "re-processed," potentially creating duplicate shipments and double-charging customers. The state machine is intentionally one-directional past the SHIPPED milestone.

**Enforcement:** `updateOrderStatus()` must reject the transitions `SHIPPED → PENDING` and `SHIPPED → PAID`.

**Related functions:** `updateOrderStatus`, `validateStatusTransition`

---

### RULE-007 — Payment Must Be Confirmed Before Marking PAID

**Statement:** An order must not be transitioned to PAID status until the payment gateway has explicitly confirmed the payment.

**Rationale:** Optimistically marking orders PAID before gateway confirmation caused inventory to be allocated and shipments to be triggered for payments that subsequently failed (chargebacks, expired cards, fraud). This resulted in shipped goods with no corresponding revenue.

**Source:** Internal ticket TICK-2024-091 — "optimistic payment marking caused 12 ghost shipments in Q1 2024."

**Enforcement:** `processOrder()` must call `confirmPayment()` and receive `true` before calling `updateOrderStatus(order, 'PAID')`.

**Related functions:** `confirmPayment`, `markOrderPaid`, `processOrder`

**Related entities:** Payment, Order, PaymentGateway

---

## 3. Payment Rules

### RULE-002 — Refund Cannot Exceed Original Payment

**Statement:** A refund amount must never exceed the original confirmed payment amount for the same order.

**Rationale:** Issuing a refund larger than the original payment creates a net negative charge to the business. This has occurred in cases where manual refund entries bypassed the payment gateway's own validation.

**Enforcement:** `processRefund()` must compare `refundAmount` against `getPaymentAmount(order)` and throw if `refundAmount > originalAmount`.

**Related functions:** `processRefund`, `getPaymentAmount`

**Related entities:** Refund, Payment, Order

---

## 4. Promotion Rules

### RULE-003 — Discount Code: One Use Per Customer

**Statement:** A discount code must not be applied more than once per customer.

**Rationale:** Promotional discount codes are designed for single-use per customer. Multiple applications of the same code by the same customer undermine campaign economics and have been exploited in the past to obtain compounding discounts.

**Source:** Ticket TICK-2024-105 — "SUMMER20 code applied 4 times to same customer, $200 revenue loss."

**Enforcement:** `validateDiscountCode()` must check the (customerId, discountCode) pair against used-codes storage before allowing `applyDiscount()` to proceed.

**Related functions:** `applyDiscount`, `validateDiscountCode`

**Related entities:** DiscountCode, Customer, Order

---

## 5. Access Control Rules

### RULE-004 — Support Agents Cannot Modify Payment Details

**Statement:** A user with the `support_agent` role must not be permitted to modify payment details — they may only view them.

**Rationale:** Support agents have read access to payment details to help customers, but write access would create a fraud vector (agents could manipulate payment amounts). Separation of duties requires that only `admin` roles can write payment data.

**Enforcement:** `updatePaymentDetails()` must check role permissions and reject any caller without `modify_payment` permission. `support_agent` must only have `view_payment`.

**Related functions:** `updatePaymentDetails`, `getPaymentDetails`

**Related entities:** SupportAgent, Payment, Role

---

### RULE-005 — Cross-Tenant Data Isolation

**Statement:** A user must only access orders belonging to their own organisation. Cross-tenant reads or writes are prohibited.

**Rationale:** Each organisation's order data is confidential. Without org-level filtering, a compromised or misconfigured session could expose another tenant's complete order history, constituting a GDPR/data-breach incident.

**Enforcement:** `getOrdersByUser()` must require a non-null `orgId` parameter and filter results to `order.orgId === orgId`. `validateOrgAccess()` must throw if `userOrgId !== targetOrgId`.

**Related functions:** `getOrdersByUser`, `validateOrgAccess`

**Related entities:** User, Organization, Order

---

## 6. Inventory Rules

### RULE-008 — Atomic Inventory Decrement on Shipment

**Statement:** Inventory must be decremented atomically when a shipment is created, to prevent overselling.

**Rationale:** Non-atomic inventory updates have caused overselling incidents where concurrent shipment creation both passed the stock check but one decremented after the other had already exhausted supply, shipping goods that didn't exist.

**Enforcement:** `createShipment()` must call `decrementInventory()` before calling `warehouseAPI.createShipment()`. Both operations must be treated as a unit (all-or-nothing pre-check before any decrement).

**Related functions:** `createShipment`, `decrementInventory`

**Related entities:** Inventory, Shipment, Product

---

## 7. Change Review Checklist

Any PR touching the following functions requires mandatory review against this document:

- `shipmentJob` / `createShipment` — check RULE-001, RULE-008
- `updateOrderStatus` — check RULE-001, RULE-006
- `processRefund` / `getPaymentAmount` — check RULE-002
- `applyDiscount` / `validateDiscountCode` — check RULE-003
- `updatePaymentDetails` / `getPaymentDetails` — check RULE-004
- `getOrdersByUser` / `validateOrgAccess` — check RULE-005
- `confirmPayment` / `markOrderPaid` — check RULE-007
- `decrementInventory` — check RULE-008
