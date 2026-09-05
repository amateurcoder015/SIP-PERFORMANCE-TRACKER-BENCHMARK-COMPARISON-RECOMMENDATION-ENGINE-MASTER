/**
 * Format raw number into INR Currency (e.g., ₹1,23,456.78).
 */
export function formatINR(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) return '₹0.00';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  }).format(val);
}

/**
 * Format decimal return into percentage string (e.g. 0.185 -> 18.50%).
 */
export function formatPercent(val: number | null | undefined, decimals: number = 2): string {
  if (val === null || val === undefined || isNaN(val)) return '0.00%';
  const pct = val * 100.0;
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(decimals)}%`;
}

/**
 * Format plain percentage without leading + sign.
 */
export function formatPlainPercent(val: number | null | undefined, decimals: number = 2): string {
  if (val === null || val === undefined || isNaN(val)) return '0.00%';
  const pct = val * 100.0;
  return `${pct.toFixed(decimals)}%`;
}

/**
 * Get CSS color classes for Alpha value.
 * Positive alpha = Emerald signal, Negative alpha = Rose signal.
 */
export function getAlphaBadgeStyle(alpha: number): {
  bgClass: string;
  textClass: string;
  borderClass: string;
  label: string;
} {
  if (alpha >= 0.0) {
    return {
      bgClass: 'bg-emerald-950/60',
      textClass: 'text-emerald-400',
      borderClass: 'border-emerald-500/30',
      label: `OUTPERFORMING (+${(alpha * 100).toFixed(2)}% Alpha)`,
    };
  }
  return {
    bgClass: 'bg-rose-950/60',
    textClass: 'text-rose-400',
    borderClass: 'border-rose-500/30',
    label: `UNDERPERFORMING (${(alpha * 100).toFixed(2)}% Alpha)`,
  };
}
