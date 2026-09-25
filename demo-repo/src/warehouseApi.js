/**
 * warehouseApi.js — HTTP client adapter for the external Warehouse API.
 *
 * All calls to the third-party warehouse system go through this module.
 * Mocked entirely in tests via jest.mock('./warehouseApi').
 */

'use strict';

const BASE_URL = process.env.WAREHOUSE_API_URL || 'https://warehouse.internal/api/v1';

/**
 * createShipment — create a new shipment record in the warehouse system.
 *
 * @param {object} payload  - { orderId, items, address }
 * @returns {Promise<object>} The created shipment object { shipmentId, status, ... }
 */
async function createShipment(payload) {
  // In production this is an HTTP POST. In tests, jest.mock replaces this.
  const response = await fetch(`${BASE_URL}/shipments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Warehouse API error ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

/**
 * getShipmentStatus — query the current status of an existing shipment.
 *
 * @param {string} shipmentId
 * @returns {Promise<object>} { shipmentId, status, updatedAt }
 */
async function getShipmentStatus(shipmentId) {
  const response = await fetch(`${BASE_URL}/shipments/${shipmentId}`);
  if (!response.ok) {
    throw new Error(`Warehouse API error ${response.status}`);
  }
  return response.json();
}

/**
 * cancelShipment — cancel a shipment that hasn't been picked up yet.
 *
 * @param {string} shipmentId
 * @returns {Promise<void>}
 */
async function cancelShipment(shipmentId) {
  const response = await fetch(`${BASE_URL}/shipments/${shipmentId}/cancel`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Warehouse API error ${response.status}`);
  }
}

module.exports = {
  createShipment,
  getShipmentStatus,
  cancelShipment,
};
