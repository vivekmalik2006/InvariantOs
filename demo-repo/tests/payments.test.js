/**
 * payments.test.js — Unit tests for payment confirmation and refund processing.
 *
 * Covers: RULE-002 (refund cannot exceed payment), RULE-007 (payment before PAID)
 */

'use strict';

const { confirmPayment, processRefund, getPaymentAmount } = require('../src/payments');

describe('confirmPayment (RULE-007)', () => {
  test('returns true for a SUCCESS payment', async () => {
    const paymentInfo = { paymentId: 'PAY-001', status: 'SUCCESS' };
    const result = await confirmPayment(paymentInfo);
    expect(result).toBe(true);
  });

  test('returns false for a FAILED payment', async () => {
    const paymentInfo = { paymentId: 'PAY-002', status: 'FAILED' };
    const result = await confirmPayment(paymentInfo);
    expect(result).toBe(false);
  });

  test('returns false when paymentInfo is null', async () => {
    const result = await confirmPayment(null);
    expect(result).toBe(false);
  });

  test('returns false when paymentId is missing', async () => {
    const result = await confirmPayment({ status: 'SUCCESS' });
    expect(result).toBe(false);
  });
});

describe('processRefund (RULE-002)', () => {
  const order = { id: 'ORD-001', paymentAmount: 100 };

  test('issues a valid partial refund', () => {
    const refund = processRefund(order, 50);
    expect(refund.refundAmount).toBe(50);
    expect(refund.originalAmount).toBe(100);
    expect(refund.status).toBe('REFUND_ISSUED');
  });

  test('issues a full refund equal to original payment', () => {
    const refund = processRefund(order, 100);
    expect(refund.refundAmount).toBe(100);
  });

  test('throws if refund exceeds original payment (RULE-002)', () => {
    expect(() => processRefund(order, 150)).toThrow(/exceeds original payment/);
  });

  test('throws if refund is 1 cent over (boundary check)', () => {
    expect(() => processRefund(order, 100.01)).toThrow(/exceeds original payment/);
  });
});

describe('getPaymentAmount', () => {
  test('returns order paymentAmount', () => {
    expect(getPaymentAmount({ paymentAmount: 99.99 })).toBe(99.99);
  });

  test('returns 0 if paymentAmount is missing', () => {
    expect(getPaymentAmount({})).toBe(0);
  });
});
