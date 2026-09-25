/**
 * accessControl.js — Role-based access enforcement.
 *
 * Business rules enforced here:
 *   RULE-004: A support agent must not modify payment details, only view them.
 *   RULE-005: A user must only access orders belonging to their own organisation.
 */

'use strict';

const ROLE_PERMISSIONS = {
  admin:         ['view_payment', 'modify_payment', 'view_orders', 'modify_orders'],
  support_agent: ['view_payment', 'view_orders'],
  customer:      ['view_orders'],
};

/**
 * validateOrgAccess — confirm a user belongs to the org they are trying to access.
 *
 * RULE-005 enforcement.
 *
 * @param {string} userId
 * @param {string} userOrgId   - The org the user belongs to (from their JWT / session)
 * @param {string} targetOrgId - The org being accessed
 * @throws {Error} If orgIds don't match.
 */
function validateOrgAccess(userId, userOrgId, targetOrgId) {
  if (userOrgId !== targetOrgId) {
    throw new Error(
      `Access denied: user ${userId} (org ${userOrgId}) cannot access org ${targetOrgId} — RULE-005.`
    );
  }
}

/**
 * getPaymentDetails — fetch payment details for an order.
 *
 * Available to: admin, support_agent (view only per RULE-004).
 *
 * @param {string} role
 * @param {object} order
 * @returns {object} Payment details.
 */
function getPaymentDetails(role, order) {
  const permissions = ROLE_PERMISSIONS[role] || [];
  if (!permissions.includes('view_payment')) {
    throw new Error(`Role '${role}' is not permitted to view payment details.`);
  }
  return {
    paymentId: order.paymentId,
    amount: order.paymentAmount,
    currency: order.currency || 'USD',
  };
}

/**
 * updatePaymentDetails — modify payment details for an order.
 *
 * RULE-004: support agents must NOT be able to call this.
 *
 * @param {string} role
 * @param {object} order
 * @param {object} updates - Fields to update
 * @returns {object} Updated order.
 * @throws {Error} If role is not permitted.
 */
function updatePaymentDetails(role, order, updates) {
  const permissions = ROLE_PERMISSIONS[role] || [];
  if (!permissions.includes('modify_payment')) {
    throw new Error(
      `Role '${role}' is not permitted to modify payment details — RULE-004.`
    );
  }
  return { ...order, ...updates };
}

module.exports = {
  validateOrgAccess,
  getPaymentDetails,
  updatePaymentDetails,
  ROLE_PERMISSIONS,
};
