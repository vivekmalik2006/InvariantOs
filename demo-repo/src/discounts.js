/**
 * discounts.js — Discount code application.
 *
 * Business rules enforced here:
 *   RULE-003: A discount code must not be applied more than once per customer.
 */

'use strict';

// Track which (customerId, discountCode) pairs have already been used.
const _usedDiscounts = new Set();

/**
 * validateDiscountCode — check that a discount code is valid and has not been used.
 *
 * RULE-003: each discount code can only be used once per customer.
 *
 * @param {string} customerId
 * @param {string} discountCode
 * @returns {boolean} True if valid and unused.
 */
function validateDiscountCode(customerId, discountCode) {
  const key = `${customerId}:${discountCode}`;
  if (_usedDiscounts.has(key)) {
    return false; // RULE-003: already used
  }
  // Additional code validity checks would go here (expiry, existence, etc.)
  return true;
}

/**
 * applyDiscount — apply a discount code to an order.
 *
 * RULE-003: rejects if this customer has already used this code.
 *
 * @param {object} order
 * @param {string} customerId
 * @param {string} discountCode
 * @param {number} discountPercent
 * @returns {object} Updated order with discount applied.
 * @throws {Error} If discount code has already been used by this customer.
 */
function applyDiscount(order, customerId, discountCode, discountPercent) {
  if (!validateDiscountCode(customerId, discountCode)) {
    throw new Error(
      `Discount code '${discountCode}' has already been used by customer ${customerId} — RULE-003.`
    );
  }

  // Mark as used
  const key = `${customerId}:${discountCode}`;
  _usedDiscounts.add(key);

  const discountAmount = order.total * (discountPercent / 100);
  return {
    ...order,
    total: order.total - discountAmount,
    discountApplied: { code: discountCode, amount: discountAmount },
  };
}

/**
 * resetDiscounts — clear all used discount records (used in tests only).
 */
function resetDiscounts() {
  _usedDiscounts.clear();
}

module.exports = {
  validateDiscountCode,
  applyDiscount,
  resetDiscounts,
};
