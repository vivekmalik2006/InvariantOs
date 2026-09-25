/**
 * shipments.test.js — Unit tests for shipment job and warehouse integration.
 *
 * RULE-001: These tests confirm the guard: only PAID orders are shipped.
 */

'use strict';

const { shipmentJob, createShipment } = require('../src/shipments');

jest.mock('../src/warehouseApi');
jest.mock('../src/inventory');

const warehouseApi  = require('../src/warehouseApi');
const { decrementInventory } = require('../src/inventory');

beforeEach(() => {
  jest.clearAllMocks();
  warehouseApi.createShipment.mockResolvedValue({ shipmentId: 'SHIP-TEST-001', status: 'CREATED' });
  decrementInventory.mockResolvedValue(undefined);
});

describe('shipmentJob — RULE-001 guard', () => {
  test('creates a shipment for a PAID order', async () => {
    const order = { id: 'ORD-PAID-1', status: 'PAID', items: [{ sku: 'SKU-A', quantity: 1 }] };
    const result = await shipmentJob(order);
    expect(result).not.toBeNull();
    expect(warehouseApi.createShipment).toHaveBeenCalledTimes(1);
  });

  test('does NOT create shipment for a CANCELLED order (RULE-001)', async () => {
    const order = { id: 'ORD-CANC-1', status: 'CANCELLED', items: [] };
    const result = await shipmentJob(order);
    expect(result).toBeNull();
    expect(warehouseApi.createShipment).not.toHaveBeenCalled();
  });

  test('does NOT create shipment for a PENDING order', async () => {
    const order = { id: 'ORD-PEND-1', status: 'PENDING', items: [] };
    const result = await shipmentJob(order);
    expect(result).toBeNull();
    expect(warehouseApi.createShipment).not.toHaveBeenCalled();
  });

  test('does NOT create shipment for a REFUNDED order', async () => {
    const order = { id: 'ORD-REF-1', status: 'REFUNDED', items: [] };
    const result = await shipmentJob(order);
    expect(result).toBeNull();
    expect(warehouseApi.createShipment).not.toHaveBeenCalled();
  });

  test('does NOT create shipment for a DELIVERED order', async () => {
    const order = { id: 'ORD-DEL-1', status: 'DELIVERED', items: [] };
    const result = await shipmentJob(order);
    expect(result).toBeNull();
    expect(warehouseApi.createShipment).not.toHaveBeenCalled();
  });
});

describe('createShipment — RULE-008 inventory decrement', () => {
  test('decrements inventory when creating a shipment', async () => {
    const order = {
      id: 'ORD-INV-1',
      status: 'PAID',
      items: [{ sku: 'SKU-B', quantity: 2 }],
      shippingAddress: '123 Main St',
    };
    await createShipment(order);
    expect(decrementInventory).toHaveBeenCalledWith(order.items);
    expect(warehouseApi.createShipment).toHaveBeenCalledWith({
      orderId: 'ORD-INV-1',
      items: order.items,
      address: '123 Main St',
    });
  });

  test('skips decrementInventory if order has no items', async () => {
    const order = { id: 'ORD-NOINV-1', status: 'PAID', items: [] };
    await createShipment(order);
    expect(decrementInventory).not.toHaveBeenCalled();
  });
});
