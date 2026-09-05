import { describe, it, expect } from 'vitest';
import { formatINR, formatPercent, formatPlainPercent, getAlphaBadgeStyle } from '../utils/formatters';

describe('Frontend Formatter Helpers', () => {
  it('formatINR formats numbers into INR currency string', () => {
    expect(formatINR(123456.78)).toContain('1,23,456.78');
    expect(formatINR(0)).toContain('0.00');
    expect(formatINR(null)).toContain('0.00');
  });

  it('formatPercent formats decimal returns into signed percentage strings', () => {
    expect(formatPercent(0.185)).toBe('+18.50%');
    expect(formatPercent(-0.042)).toBe('-4.20%');
    expect(formatPercent(0)).toBe('0.00%');
  });

  it('formatPlainPercent formats percentage without leading plus sign', () => {
    expect(formatPlainPercent(0.185)).toBe('18.50%');
  });

  it('getAlphaBadgeStyle assigns emerald style for positive alpha and rose for negative alpha', () => {
    const pos = getAlphaBadgeStyle(0.065);
    expect(pos.bgClass).toContain('emerald');
    expect(pos.label).toContain('OUTPERFORMING');

    const neg = getAlphaBadgeStyle(-0.025);
    expect(neg.bgClass).toContain('rose');
    expect(neg.label).toContain('UNDERPERFORMING');
  });
});
