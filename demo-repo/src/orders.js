/**
 * orders.js — Order lifecycle management for the InvariantOS demo e-commerce service.
 *
 * Business rules enforced here:
 *   RULE-001: A cancelled order must never be shipped.
 *   RULE-006: An order that is already shipped must not transition back to PENDING or PAID.
 *   RULE-007: Payment must be confirmed before an order is marked PAID.
 */

'use strict';

const { shipmentJob } = require('./shipments');
const { confirmPayment } = require('./payments');

/**
 * Valid order status transitions.
 * RULE-006: once SHIPPED, cannot go back to PENDING or PAID.
 */
const VALID_TRANSITIONS = {
  PENDING: ['PAID', 'CANCELLED'],
  PAID:    ['SHIPPED', 'CANCELLED', 'REFUNDED'],
  SHIPPED: ['DELIVERED', 'RETURN_REQUESTED'],
  CANCELLED: [],          // terminal — no outbound transitions
  DELIVERED: ['RETURN_REQUESTED', 'REFUNDED'],
  REFUNDED:  [],          // terminal
  RETURN_REQUESTED: ['REFUNDED'],
};

/**
 * updateOrderStatus — transition an order to a new status.
 *
 * @param {object} order   - The order object (must have .id and .status fields).
 * @param {string} newStatus - The target status to transition to.
 * @returns {object} Updated order with the new status.
 * @throws {Error} If the transition is not permitted.
 */
function updateOrderStatus(order, newStatus) {
  const allowed = VALID_TRANSITIONS[order.status];
  if (!allowed) {
    throw new Error(`Unknown current status: ${order.status}`);
  }
  if (!allowed.includes(newStatus)) {
    throw new Error(
      `Invalid status transition: ${order.status} → ${newStatus} ` +
      `(order ${order.id}). Allowed: ${allowed.join(', ') || 'none (terminal)'}`
    );
  }
  return { ...order, status: newStatus };
}

/**
 * cancelOrder — cancel an order.
 *
 * Once cancelled, the order must never be shipped (RULE-001).
 *
 * @param {object} order
 * @returns {object} Cancelled order.
 */
function cancelOrder(order) {
  return updateOrderStatus(order, 'CANCELLED');
}

/**
 * processOrder — entry point that drives the full order lifecycle.
 *
 * After payment confirmation, triggers the shipment job.
 * The shipment job enforces RULE-001 internally.
 *
 * @param {object} order
 * @param {object} paymentInfo
 * @returns {Promise<object>} Fully processed order.
 */
async function processOrder(order, paymentInfo) {
  // RULE-007: payment must be confirmed before marking PAID
  const paymentConfirmed = await confirmPayment(paymentInfo);
  if (!paymentConfirmed) {
    throw new Error(`Payment not confirmed for order ${order.id}`);
  }

  const paidOrder = updateOrderStatus(order, 'PAID');

  // Trigger shipment asynchronously — RULE-001 is enforced inside shipmentJob
  await shipmentJob(paidOrder);

  return paidOrder;
}

/**
 * getOrdersByUser — retrieve orders belonging to a specific user/org.
 *
 * RULE-005: a user must only access orders belonging to their own organisation.
 * Callers MUST pass a validated orgId; this function enforces the filter.
 *
 * @param {string} userId
 * @param {string} orgId
 * @param {object[]} allOrders
 * @returns {object[]} Filtered orders.
 */
function getOrdersByUser(userId, orgId, allOrders) {
  if (!orgId) {
    throw new Error('orgId is required — cross-tenant access is not permitted (RULE-005).');
  }
  return allOrders.filter(o => o.userId === userId && o.orgId === orgId);
}

module.exports = {
  updateOrderStatus,
  cancelOrder,
  processOrder,
  getOrdersByUser,
  VALID_TRANSITIONS,
};
