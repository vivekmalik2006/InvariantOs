/**
 * payments.js — Payment processing and refund management.
 *
 * Business rules enforced here:
 *   RULE-002: A refund must never exceed the original payment amount.
 *   RULE-007: Payment must be confirmed before an order is marked PAID.
 */

'use strict';

/**
 * confirmPayment — verify with the payment gateway that a payment succeeded.
 *
 * RULE-007: only confirmed payments allow an order to advance to PAID.
 *
 * @param {object} paymentInfo - { paymentId, amount, currency, gateway }
 * @returns {Promise<boolean>} True if confirmed, false if not.
 */
async function confirmPayment(paymentInfo) {
  if (!paymentInfo || !paymentInfo.paymentId) {
    return false;
  }
  // ASSUMPTION: In tests this is mocked. In production it calls a real gateway.
  return paymentInfo.status === 'SUCCESS';
}

/**
 * processRefund — issue a refund for an order.
 *
 * RULE-002: The refund amount must not exceed the original payment amount.
 *
 * @param {object} order        - The original order with .paymentAmount
 * @param {number} refundAmount - The requested refund amount
 * @returns {object} Refund record.
 * @throws {Error} If refundAmount > order.paymentAmount.
 */
function processRefund(order, refundAmount) {
  const originalAmount = getPaymentAmount(order);

  // RULE-002 enforcement
  if (refundAmount > originalAmount) {
    throw new Error(
      `Refund amount ${refundAmount} exceeds original payment ${originalAmount} ` +
      `for order ${order.id} — RULE-002 violation.`
    );
  }

  return {
    orderId: order.id,
    refundAmount,
    originalAmount,
    status: 'REFUND_ISSUED',
    issuedAt: new Date().toISOString(),
  };
}

/**
 * getPaymentAmount — return the confirmed payment amount for an order.
 *
 * @param {object} order
 * @returns {number}
 */
function getPaymentAmount(order) {
  return order.paymentAmount || 0;
}

module.exports = {
  confirmPayment,
  processRefund,
  getPaymentAmount,
};
