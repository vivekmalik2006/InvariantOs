/**
 * inventory.js — Inventory management for the demo e-commerce service.
 *
 * Business rules enforced here:
 *   RULE-008: Inventory must be decremented atomically when a shipment is created.
 */

'use strict';

// In-memory inventory store for demo purposes.
// In production this would be a DB transaction.
const _inventory = {};

/**
 * setInventory — seed inventory levels (used in tests).
 *
 * @param {object} levels - { sku: quantity, ... }
 */
function setInventory(levels) {
  Object.assign(_inventory, levels);
}

/**
 * getStock — return current stock level for a SKU.
 *
 * @param {string} sku
 * @returns {number}
 */
function getStock(sku) {
  return _inventory[sku] || 0;
}

/**
 * decrementInventory — atomically decrement stock for each item in a shipment.
 *
 * RULE-008: this must happen atomically (all-or-nothing). If any item is out
 * of stock, the whole operation is rejected before any decrement occurs.
 *
 * @param {Array<{sku: string, quantity: number}>} items
 * @throws {Error} If any item has insufficient stock.
 */
async function decrementInventory(items) {
  // Pre-validate — RULE-008 atomicity: check all before touching any
  for (const item of items) {
    const stock = getStock(item.sku);
    if (stock < item.quantity) {
      throw new Error(
        `Insufficient stock for SKU ${item.sku}: requested ${item.quantity}, available ${stock}.`
      );
    }
  }

  // All checks passed — now decrement atomically
  for (const item of items) {
    _inventory[item.sku] = (_inventory[item.sku] || 0) - item.quantity;
  }
}

module.exports = {
  setInventory,
  getStock,
  decrementInventory,
};
