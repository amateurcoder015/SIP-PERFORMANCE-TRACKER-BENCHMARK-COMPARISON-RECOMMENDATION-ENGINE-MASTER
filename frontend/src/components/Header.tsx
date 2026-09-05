import React from 'react';
import { TrendingUp, ShieldAlert } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="bento-card rounded-2xl p-6 mb-6 relative overflow-hidden border-b border-indigo-500/20">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex items-center space-x-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shadow-lg shadow-indigo-500/10">
            <TrendingUp className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-2xl font-bold tracking-tight text-white">
                SIP Performance & Recommendation Engine
              </h1>
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
                Bento Analytics v1.0
              </span>
            </div>
            <p className="text-sm text-slate-400 mt-0.5">
              Personalized money-weighted returns (XIRR), cashflow benchmark replication, and long-term peer discovery.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs bg-slate-900/80 border border-slate-800 rounded-xl px-3.5 py-2 text-slate-400">
          <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
          <span>Personal Decision Support • Historical NAV Analytics</span>
        </div>
      </div>
    </header>
  );
};
