import React from 'react';
import { Sparkles, Trophy, ShieldAlert, AlertCircle, Info, ChevronRight } from 'lucide-react';
import { RecommendationResult } from '../types';
import { formatPlainPercent } from '../utils/formatters';

interface RecommendationPanelProps {
  recommendationData: RecommendationResult | null;
  isLoading: boolean;
  error: string | null;
}

export const RecommendationPanel: React.FC<RecommendationPanelProps> = ({
  recommendationData,
  isLoading,
  error,
}) => {
  if (isLoading) {
    return (
      <div className="bento-card rounded-2xl p-6 flex flex-col justify-center items-center text-center h-full min-h-[300px]">
        <div className="w-10 h-10 border-3 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mb-3" />
        <h3 className="text-sm font-semibold text-slate-200">Discovering & Scoring Peer Mutual Funds...</h3>
        <p className="text-xs text-slate-400 mt-1 max-w-[280px]">
          Phase (a) cheap pre-filtering + Phase (b) category confirmation & multi-window rolling CAGR scoring.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bento-card rounded-2xl p-6 border border-rose-500/30 bg-rose-950/20 text-rose-300">
        <div className="flex items-center space-x-2 text-rose-400 mb-2">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <h3 className="text-sm font-semibold">Recommendation Error</h3>
        </div>
        <p className="text-xs">{error}</p>
      </div>
    );
  }

  if (!recommendationData) {
    return (
      <div className="bento-card rounded-2xl p-6 flex flex-col justify-center items-center text-center h-full min-h-[250px]">
        <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-3">
          <Sparkles className="w-5 h-5" />
        </div>
        <h3 className="text-sm font-semibold text-slate-300">Long-Term Alternative Peer Recommendations</h3>
        <p className="text-xs text-slate-500 max-w-[320px] mt-1">
          Select any fund card above to discover real AMFI peer funds in the same category scored on 3y/5y/10y rolling CAGRs & consistency.
        </p>
      </div>
    );
  }

  const { target_score, normalized_category, recommendations, reasoning, skipped_funds, candidates_confirmed_count, disclaimer } =
    recommendationData;

  return (
    <div className="bento-card rounded-2xl p-6 flex flex-col justify-between h-full space-y-6">
      {/* Panel Header */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
              <Trophy className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">
                Long-Term Peer Alternatives — <span className="text-indigo-400">{normalized_category} Category</span>
              </h3>
              <p className="text-xs text-slate-400">
                Confirmed {candidates_confirmed_count} candidate peers in {normalized_category} category.
              </p>
            </div>
          </div>
          <span className="text-xs font-mono text-indigo-300 bg-indigo-950 border border-indigo-500/30 px-3 py-1 rounded-lg">
            Target Score: {target_score.composite_score.toFixed(3)}
          </span>
        </div>

        {/* Target Fund Score Summary Box */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 mb-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-300">Target Baseline: {target_score.scheme_name}</span>
            <span className="text-xs text-slate-400 font-mono">Span: {target_score.data_span_years.toFixed(1)} yrs</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800">
              <span className="text-slate-500 text-[10px] block">Composite Score</span>
              <span className="font-bold text-indigo-300 font-mono">{target_score.composite_score.toFixed(3)} / 1.00</span>
            </div>
            <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800">
              <span className="text-slate-500 text-[10px] block">3-Yr Mean Rolling CAGR</span>
              <span className="font-bold text-slate-200 font-mono">
                {formatPlainPercent(target_score.mean_rolling_cagr_by_window['3y'])}
              </span>
            </div>
            <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800">
              <span className="text-slate-500 text-[10px] block">3-Yr Rolling Stdev</span>
              <span className="font-bold text-slate-200 font-mono">
                {formatPlainPercent(target_score.stdev_rolling_cagr_by_window['3y'])}
              </span>
            </div>
            <div className="bg-slate-950/60 p-2 rounded-lg border border-slate-800">
              <span className="text-slate-500 text-[10px] block">Expense Ratio Signal</span>
              <span className="font-bold text-amber-400 text-[11px]">Not Considered (False)</span>
            </div>
          </div>
        </div>

        {/* Ranked Peer Recommendations List */}
        <div className="space-y-4">
          <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" /> Top {recommendations.length} Ranked Peer Shortlist
          </h4>

          {recommendations.map((peer, idx) => {
            const peer3yCAGR = peer.mean_rolling_cagr_by_window['3y'];
            const peer3yStdev = peer.stdev_rolling_cagr_by_window['3y'];
            const peerReasoning = reasoning[peer.scheme_code] || 'Ranked peer based on 50/30/20 composite scoring.';

            return (
              <div
                key={peer.scheme_code}
                className="bg-slate-900/90 border border-slate-800 hover:border-indigo-500/40 rounded-xl p-4 transition-all shadow-md"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                  <div className="flex items-center space-x-2">
                    <span className="w-6 h-6 rounded-full bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-xs font-bold text-indigo-300 shrink-0">
                      #{idx + 1}
                    </span>
                    <div>
                      <span className="text-[10px] font-mono text-indigo-400 font-bold px-1.5 py-0.5 rounded bg-indigo-950 border border-indigo-500/30">
                        AMFI #{peer.scheme_code}
                      </span>
                      <h5 className="text-sm font-bold text-white inline-block ml-2">{peer.scheme_name}</h5>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3 text-xs">
                    <span className="text-slate-400 font-mono">
                      Score: <strong className="text-emerald-400 font-bold">{peer.composite_score.toFixed(3)}</strong>
                    </span>
                  </div>
                </div>

                {/* Metrics pill row */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 my-2 text-xs">
                  <div className="bg-slate-950/70 p-2 rounded-lg border border-slate-800/80">
                    <span className="text-slate-500 text-[10px] block">3-Year Mean Rolling CAGR</span>
                    <span className="font-semibold text-emerald-400 font-mono">{formatPlainPercent(peer3yCAGR)}</span>
                  </div>
                  <div className="bg-slate-950/70 p-2 rounded-lg border border-slate-800/80">
                    <span className="text-slate-500 text-[10px] block">3-Year Rolling Variance Stdev</span>
                    <span className="font-semibold text-slate-300 font-mono">{formatPlainPercent(peer3yStdev)}</span>
                  </div>
                  <div className="bg-slate-950/70 p-2 rounded-lg border border-slate-800/80 col-span-2 sm:col-span-1">
                    <span className="text-slate-500 text-[10px] block">Windows Analyzed</span>
                    <span className="font-semibold text-indigo-300 font-mono">
                      {peer.windows_used.map((w) => `${w}y`).join(', ')}
                    </span>
                  </div>
                </div>

                {/* Verbatim Reasoning String */}
                <div className="mt-2.5 p-3 rounded-lg bg-indigo-950/30 border border-indigo-500/20 text-xs text-indigo-200 leading-relaxed font-sans">
                  <span className="font-semibold text-indigo-400 block mb-0.5 flex items-center gap-1">
                    <ChevronRight className="w-3.5 h-3.5 text-indigo-400" /> Peer Comparative Rationale:
                  </span>
                  <p>{peerReasoning}</p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Skipped Funds Note */}
        {skipped_funds && skipped_funds.length > 0 && (
          <div className="mt-4 p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 space-y-1">
            <span className="font-semibold text-slate-300 flex items-center gap-1">
              <Info className="w-3.5 h-3.5 text-indigo-400" /> Skipped Candidate Funds ({skipped_funds.length}):
            </span>
            {skipped_funds.map((sf, idx) => (
              <p key={idx} className="text-[11px] text-slate-500 font-mono pl-4">
                • Scheme #{sf.scheme_code}: {sf.reason}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* MANDATORY PROMINENT FINANCIAL ADVICE DISCLAIMER CARD */}
      <div className="mt-6 p-4 rounded-xl bg-amber-950/50 border-2 border-amber-500/40 text-amber-200 shadow-lg shadow-amber-950/30">
        <div className="flex items-center space-x-2 text-amber-400 font-bold text-xs uppercase tracking-wider mb-1.5">
          <ShieldAlert className="w-4 h-4 shrink-0 text-amber-400" />
          <span>Mandatory Disclaimer</span>
        </div>
        <p className="text-xs leading-relaxed font-medium text-amber-100">{disclaimer}</p>
      </div>
    </div>
  );
};
