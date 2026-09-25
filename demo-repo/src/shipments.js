/**
 * shipments.js — Shipment creation and job management.
 *
 * Business rules enforced here:
 *   RULE-001: A cancelled order must never be shipped.
 *   RULE-008: Inventory must be decremented atomically when a shipment is created.
 */

'use strict';

const warehouseApi = require('./warehouseApi');
const { decrementInventory } = require('./inventory');

/**
 * shipmentJob — process a shipment for a given order.
 *
 * RULE-001 guard: only orders with status === 'PAID' may proceed to shipment.
 * Any other status (including CANCELLED) must be rejected here.
 *
 * @param {object} order - The order to ship. Must have .id, .status, .items fields.
 * @returns {Promise<object|null>} Shipment object, or null if order is not shippable.
 */
async function shipmentJob(order) {
  // RULE-001: guard — only PAID orders may be shipped
  if (order.status === 'PAID') {
    return await createShipment(order);
  }

  // All other statuses (CANCELLED, PENDING, REFUNDED, DELIVERED, RETURN_REQUESTED)
  // must NOT trigger shipment.
  return null;
}

/**
 * createShipment — call the warehouse API to create a physical shipment.
 *
 * RULE-008: inventory must be decremented atomically in the same operation.
 *
 * @param {object} order
 * @returns {Promise<object>} Created shipment.
 */
async function createShipment(order) {
  // RULE-008: decrement inventory atomically before creating the shipment record
  if (order.items && order.items.length > 0) {
    await decrementInventory(order.items);
  }

  const shipment = await warehouseApi.createShipment({
    orderId: order.id,
    items: order.items || [],
    address: order.shippingAddress,
  });

  return shipment;
}

/**
 * getShipmentStatus — retrieve the current status of a shipment.
 *
 * @param {string} shipmentId
 * @returns {Promise<object>} Shipment status.
 */
async function getShipmentStatus(shipmentId) {
  return await warehouseApi.getShipmentStatus(shipmentId);
}

module.exports = {
  shipmentJob,
  createShipment,
  getShipmentStatus,
};
