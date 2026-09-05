import React from 'react';
import { Award, AlertTriangle, Sparkles, Clock, Hash, AlertOctagon } from 'lucide-react';
import { PerformanceItem, FundPerformanceResult } from '../types';
import { formatINR, formatPercent, getAlphaBadgeStyle } from '../utils/formatters';

interface FundPerformanceCardProps {
  schemeCode: string;
  item: PerformanceItem;
  onSelectRecommend: (schemeCode: string) => void;
  isSelectedForRecommend: boolean;
  isLoadingRecommend: boolean;
}

export const FundPerformanceCard: React.FC<FundPerformanceCardProps> = ({
  schemeCode,
  item,
  onSelectRecommend,
  isSelectedForRecommend,
  isLoadingRecommend,
}) => {
  // Handle failed fund evaluation state
  if ('error' in item) {
    return (
      <div className="bento-card bento-glow-rose rounded-2xl p-5 border border-rose-500/30 bg-rose-950/20 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-xs text-rose-400 font-semibold px-2 py-0.5 rounded bg-rose-950 border border-rose-500/40">
              Scheme #{schemeCode}
            </span>
            <span className="text-xs font-semibold text-rose-400 flex items-center gap-1">
              <AlertOctagon className="w-3.5 h-3.5" /> Evaluation Failed
            </span>
          </div>
          <h4 className="text-sm font-semibold text-slate-200 mb-2">Scheme Code {schemeCode}</h4>
          <div className="p-3 rounded-xl bg-rose-950/80 border border-rose-500/30 text-xs text-rose-300 font-mono space-y-1">
            <span className="font-bold text-rose-200 block mb-1">Domain Error:</span>
            <p>{item.error}</p>
          </div>
        </div>
        <p className="text-[11px] text-slate-500 mt-4">
          This fund failed individual evaluation (e.g. insufficient NAV history span). Other portfolio funds remain valid.
        </p>
      </div>
    );
  }

  const fund = item as FundPerformanceResult;
  const alphaStyle = getAlphaBadgeStyle(fund.alpha);

  return (
    <div
      className={`bento-card rounded-2xl p-5 flex flex-col justify-between transition-all ${
        isSelectedForRecommend ? 'border-indigo-500 shadow-indigo-500/20 bg-slate-900/90' : ''
      }`}
    >
      <div>
        {/* Header Badges */}
        <div className="flex items-start justify-between gap-2 mb-3">
          <div>
            <span className="text-[10px] font-mono text-indigo-400 font-bold px-2 py-0.5 rounded bg-indigo-950/80 border border-indigo-500/30 uppercase tracking-wider">
              AMFI #{fund.scheme_code}
            </span>
            <h4 className="text-base font-bold text-white mt-1 leading-snug">{fund.scheme_name}</h4>
          </div>
          <div className={`px-2.5 py-1 rounded-lg border text-[11px] font-bold ${alphaStyle.bgClass} ${alphaStyle.textClass} ${alphaStyle.borderClass} shrink-0`}>
            {alphaStyle.label}
          </div>
        </div>

        {/* XIRR Comparison Box */}
        <div className="grid grid-cols-2 gap-3 my-4 p-3.5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div>
            <span className="text-[11px] font-medium text-slate-400 block mb-0.5">Your Actual XIRR</span>
            <span className="text-xl font-extrabold text-white font-mono">{formatPercent(fund.actual_xirr)}</span>
            <span className="text-[10px] text-slate-500 block">Money-Weighted</span>
          </div>

          <div>
            <span className="text-[11px] font-medium text-slate-400 block mb-0.5">
              {fund.benchmark_name} XIRR
            </span>
            <span className="text-xl font-bold text-indigo-300 font-mono">{formatPercent(fund.benchmark_xirr)}</span>
            <span className="text-[10px] text-slate-500 block">Replicated Cashflows</span>
          </div>
        </div>

        {/* Investment Details */}
        <div className="grid grid-cols-3 gap-2 text-xs mb-4">
          <div className="bg-slate-900/40 border border-slate-800/60 rounded-lg p-2">
            <span className="text-slate-500 block text-[10px]">Invested</span>
            <span className="font-semibold text-slate-200 font-mono">{formatINR(fund.total_invested)}</span>
          </div>
          <div className="bg-slate-900/40 border border-slate-800/60 rounded-lg p-2">
            <span className="text-slate-500 block text-[10px]">Current Value</span>
            <span className="font-semibold text-slate-200 font-mono">{formatINR(fund.current_value)}</span>
          </div>
          <div className="bg-slate-900/40 border border-slate-800/60 rounded-lg p-2">
            <span className="text-slate-500 block text-[10px]">Gain / Loss</span>
            <span className={`font-semibold font-mono ${fund.absolute_gain >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {formatINR(fund.absolute_gain)}
            </span>
          </div>
        </div>

        {/* Meta Pills */}
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 py-1">
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-indigo-400" /> {fund.investment_span_years.toFixed(1)} yrs span
          </span>
          <span className="flex items-center gap-1">
            <Hash className="w-3.5 h-3.5 text-indigo-400" /> {fund.num_transactions} SIP txs
          </span>
          <span className="flex items-center gap-1">
            <Award className="w-3.5 h-3.5 text-indigo-400" /> {fund.units_held.toFixed(2)} units
          </span>
        </div>

        {/* Date Mismatch Warnings */}
        {fund.nav_date_mismatch_warnings && fund.nav_date_mismatch_warnings.length > 0 && (
          <div className="mt-3 p-2.5 rounded-xl bg-amber-950/40 border border-amber-500/30 text-amber-300 text-xs space-y-1">
            <div className="flex items-center gap-1.5 font-semibold text-amber-400">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" /> NAV Mismatch Warning:
            </div>
            {fund.nav_date_mismatch_warnings.map((warn, idx) => (
              <p key={idx} className="text-[11px] text-amber-200/90 pl-5">
                • {warn}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* Recommend Peer Button */}
      <button
        onClick={() => onSelectRecommend(fund.scheme_code)}
        disabled={isLoadingRecommend}
        className={`mt-4 w-full py-2.5 px-3 rounded-xl text-xs font-semibold flex items-center justify-center space-x-2 transition-all border ${
          isSelectedForRecommend
            ? 'bg-indigo-600 text-white border-indigo-400 shadow-lg shadow-indigo-600/30'
            : 'bg-slate-900 hover:bg-slate-800 text-indigo-300 border-slate-700/80 hover:border-indigo-500/40'
        }`}
      >
        <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
        <span>{isSelectedForRecommend ? 'Viewing Alternative Peer Recommendations' : 'Find Alternative Peer Recommendations'}</span>
      </button>
    </div>
  );
};
