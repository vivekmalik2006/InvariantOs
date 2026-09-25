/**
 * orders.test.js — Unit tests for the order lifecycle module.
 *
 * Covers: updateOrderStatus, cancelOrder, processOrder, getOrdersByUser
 */

'use strict';

const { updateOrderStatus, cancelOrder, processOrder, getOrdersByUser, VALID_TRANSITIONS } = require('../src/orders');

jest.mock('../src/shipments', () => ({
  shipmentJob: jest.fn().mockResolvedValue({ shipmentId: 'SHIP-001', status: 'CREATED' }),
}));

jest.mock('../src/payments', () => ({
  confirmPayment: jest.fn().mockResolvedValue(true),
}));

describe('updateOrderStatus', () => {
  test('transitions PENDING → PAID correctly', () => {
    const order = { id: 'ORD-001', status: 'PENDING' };
    const updated = updateOrderStatus(order, 'PAID');
    expect(updated.status).toBe('PAID');
  });

  test('transitions PENDING → CANCELLED correctly', () => {
    const order = { id: 'ORD-001', status: 'PENDING' };
    const updated = updateOrderStatus(order, 'CANCELLED');
    expect(updated.status).toBe('CANCELLED');
  });

  test('rejects PAID → PENDING (RULE-006: shipped orders cannot revert)', () => {
    const order = { id: 'ORD-001', status: 'SHIPPED' };
    expect(() => updateOrderStatus(order, 'PENDING')).toThrow(/Invalid status transition/);
  });

  test('rejects SHIPPED → PAID (RULE-006)', () => {
    const order = { id: 'ORD-001', status: 'SHIPPED' };
    expect(() => updateOrderStatus(order, 'PAID')).toThrow(/Invalid status transition/);
  });

  test('rejects CANCELLED → any status (terminal)', () => {
    const order = { id: 'ORD-001', status: 'CANCELLED' };
    expect(() => updateOrderStatus(order, 'PAID')).toThrow(/terminal/);
  });

  test('throws on unknown current status', () => {
    const order = { id: 'ORD-001', status: 'BOGUS' };
    expect(() => updateOrderStatus(order, 'PAID')).toThrow(/Unknown current status/);
  });
});

describe('cancelOrder', () => {
  test('cancels a PENDING order', () => {
    const order = { id: 'ORD-001', status: 'PENDING' };
    const cancelled = cancelOrder(order);
    expect(cancelled.status).toBe('CANCELLED');
  });

  test('cancels a PAID order', () => {
    const order = { id: 'ORD-001', status: 'PAID' };
    const cancelled = cancelOrder(order);
    expect(cancelled.status).toBe('CANCELLED');
  });
});

describe('processOrder', () => {
  beforeEach(() => jest.clearAllMocks());

  test('processes a valid order end-to-end', async () => {
    const { confirmPayment } = require('../src/payments');
    const { shipmentJob }   = require('../src/shipments');

    confirmPayment.mockResolvedValueOnce(true);
    shipmentJob.mockResolvedValueOnce({ shipmentId: 'SHIP-002' });

    const order = { id: 'ORD-002', status: 'PENDING' };
    const paymentInfo = { paymentId: 'PAY-001', status: 'SUCCESS' };

    const result = await processOrder(order, paymentInfo);
    expect(result.status).toBe('PAID');
    expect(shipmentJob).toHaveBeenCalledWith(expect.objectContaining({ status: 'PAID' }));
  });

  test('throws if payment is not confirmed (RULE-007)', async () => {
    const { confirmPayment } = require('../src/payments');
    confirmPayment.mockResolvedValueOnce(false);

    const order = { id: 'ORD-003', status: 'PENDING' };
    const paymentInfo = { paymentId: 'PAY-002', status: 'FAILED' };

    await expect(processOrder(order, paymentInfo)).rejects.toThrow(/Payment not confirmed/);
  });
});

describe('getOrdersByUser', () => {
  const allOrders = [
    { id: 'ORD-010', userId: 'user-A', orgId: 'org-1' },
    { id: 'ORD-011', userId: 'user-A', orgId: 'org-2' },  // different org
    { id: 'ORD-012', userId: 'user-B', orgId: 'org-1' },
  ];

  test('returns only orders for the correct user and org (RULE-005)', () => {
    const result = getOrdersByUser('user-A', 'org-1', allOrders);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('ORD-010');
  });

  test('throws if no orgId provided (RULE-005 — cross-tenant prevention)', () => {
    expect(() => getOrdersByUser('user-A', null, allOrders)).toThrow(/orgId is required/);
  });
});
