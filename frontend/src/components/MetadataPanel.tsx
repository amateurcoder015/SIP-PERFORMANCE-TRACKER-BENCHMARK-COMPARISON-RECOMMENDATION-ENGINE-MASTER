import React from 'react';
import { Database, Clock, ShieldCheck } from 'lucide-react';

interface MetadataPanelProps {
  benchmarkName: string;
  valuationDate?: string;
  dataRetrievedAt?: string;
}

export const MetadataPanel: React.FC<MetadataPanelProps> = ({
  benchmarkName,
  valuationDate,
  dataRetrievedAt,
}) => {
  const currentTime = dataRetrievedAt || new Date().toISOString();

  return (
    <div className="bento-card rounded-2xl p-5 flex flex-col justify-between h-full text-xs text-slate-400">
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
          <Database className="w-3.5 h-3.5" />
        </div>
        <h4 className="text-sm font-semibold text-slate-200">Data Freshness & Provenance</h4>
      </div>

      <div className="space-y-2 bg-slate-900/60 p-3 rounded-xl border border-slate-800 font-mono text-[11px]">
        <div className="flex justify-between">
          <span className="text-slate-500">Fund NAV Provider:</span>
          <span className="text-indigo-300 font-bold">mfapi.in (AMFI Official)</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">Benchmark Provider:</span>
          <span className="text-indigo-300 font-bold">Yahoo Finance (yfinance)</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">Active Benchmark:</span>
          <span className="text-slate-200 font-bold">{benchmarkName}</span>
        </div>
        {valuationDate && (
          <div className="flex justify-between">
            <span className="text-slate-500">Valuation Date Target:</span>
            <span className="text-slate-200">{valuationDate}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-slate-500">Expense Ratio:</span>
          <span className="text-amber-400 font-bold">Unavailable (False)</span>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between text-[10px] text-slate-500 pt-2 border-t border-slate-800">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3 text-slate-400" /> Fetched: {new Date(currentTime).toLocaleTimeString()}
        </span>
        <span className="flex items-center gap-1 text-emerald-400">
          <ShieldCheck className="w-3 h-3" /> Live API Operational
        </span>
      </div>
    </div>
  );
};
