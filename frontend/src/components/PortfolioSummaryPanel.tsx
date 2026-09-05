import React from 'react';
import { Wallet, ArrowUpRight, ArrowDownRight, Layers } from 'lucide-react';
import { PerformanceResponse, FundPerformanceResult } from '../types';
import { formatINR, formatPlainPercent } from '../utils/formatters';

interface PortfolioSummaryPanelProps {
  performanceData: PerformanceResponse | null;
}

export const PortfolioSummaryPanel: React.FC<PortfolioSummaryPanelProps> = ({ performanceData }) => {
  if (!performanceData) {
    return (
      <div className="bento-card rounded-2xl p-6 flex flex-col justify-center items-center text-center h-full min-h-[160px]">
        <div className="w-10 h-10 rounded-xl bg-slate-800/80 border border-slate-700/50 flex items-center justify-center text-slate-500 mb-2">
          <Wallet className="w-5 h-5" />
        </div>
        <h3 className="text-sm font-medium text-slate-400">Portfolio Summary</h3>
        <p className="text-xs text-slate-600 max-w-[220px] mt-1">
          Upload transactions and run evaluation to see total invested capital and current valuation.
        </p>
      </div>
    );
  }

  // Calculate simple sums ONLY across successfully evaluated funds
  let totalInvested = 0;
  let totalCurrentValue = 0;
  let successCount = 0;

  Object.values(performanceData).forEach((item) => {
    if (!('error' in item)) {
      const fund = item as FundPerformanceResult;
      totalInvested += fund.total_invested;
      totalCurrentValue += fund.current_value;
      successCount += 1;
    }
  });

  const absoluteGain = totalCurrentValue - totalInvested;
  const gainPercent = totalInvested > 0 ? absoluteGain / totalInvested : 0;
  const isPositive = absoluteGain >= 0;

  return (
    <div className="bento-card rounded-2xl p-6 flex flex-col justify-between h-full relative overflow-hidden">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Wallet className="w-4 h-4" />
          </div>
          <h3 className="text-sm font-semibold text-slate-200">Portfolio Sum Totals</h3>
        </div>
        <span className="text-xs text-slate-400 flex items-center gap-1 bg-slate-900 border border-slate-800 px-2 py-1 rounded-md">
          <Layers className="w-3 h-3 text-indigo-400" /> {successCount} Funds Summed
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 my-4">
        {/* Total Invested */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-3.5">
          <span className="text-xs font-medium text-slate-400 block mb-1">Total Contributions</span>
          <span className="text-lg font-bold text-white font-mono">{formatINR(totalInvested)}</span>
        </div>

        {/* Current Valuation */}
        <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-3.5">
          <span className="text-xs font-medium text-slate-400 block mb-1">Current Valuation</span>
          <span className="text-lg font-bold text-indigo-300 font-mono">{formatINR(totalCurrentValue)}</span>
        </div>

        {/* Total Gain / Loss */}
        <div className={`bg-slate-900/60 border rounded-xl p-3.5 ${isPositive ? 'border-emerald-500/30' : 'border-rose-500/30'}`}>
          <span className="text-xs font-medium text-slate-400 block mb-1">Absolute Gain / Loss</span>
          <div className="flex items-baseline space-x-2">
            <span className={`text-lg font-bold font-mono ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
              {formatINR(absoluteGain)}
            </span>
            <span className={`text-xs font-semibold flex items-center ${isPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isPositive ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
              {formatPlainPercent(gainPercent)}
            </span>
          </div>
        </div>
      </div>

      <div className="text-[11px] text-slate-500 bg-slate-900/40 border border-slate-800/60 rounded-lg p-2.5">
        <span className="font-semibold text-slate-400">Note:</span> Portfolio totals represent simple capital sums (Current Value minus Invested) across evaluated funds. Money-weighted returns (XIRR) are evaluated strictly per-fund below.
      </div>
    </div>
  );
};
