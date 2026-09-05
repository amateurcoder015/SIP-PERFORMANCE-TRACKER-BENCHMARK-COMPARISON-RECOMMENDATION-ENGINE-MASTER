import React, { useState } from 'react';
import { Upload, FileCheck, Play, AlertCircle, Calendar, BarChart3 } from 'lucide-react';
import { UploadResponse } from '../types';
import { formatINR } from '../utils/formatters';

interface UploadPanelProps {
  onUploadSuccess: (data: UploadResponse) => void;
  onRunPerformance: (benchmarkName: string, valuationDate?: string) => void;
  isLoadingUpload: boolean;
  isLoadingPerformance: boolean;
  uploadData: UploadResponse | null;
  error: string | null;
}

export const UploadPanel: React.FC<UploadPanelProps> = ({
  onUploadSuccess,
  onRunPerformance,
  isLoadingUpload,
  isLoadingPerformance,
  uploadData,
  error,
}) => {
  const [selectedBenchmark, setSelectedBenchmark] = useState<string>('NIFTY50');
  const [valuationDate, setValuationDate] = useState<string>('');
  const [dragActive, setDragActive] = useState<boolean>(false);

  const handleFile = (file: File) => {
    if (!file.name.endsWith('.csv')) {
      alert('Please upload a valid .csv transaction file.');
      return;
    }
    const fakeEvent = { target: { files: [file] } } as unknown as React.ChangeEvent<HTMLInputElement>;
    handleFileInput(fakeEvent);
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const { uploadTransactionsCSV } = await import('../api');
      const res = await uploadTransactionsCSV(file);
      onUploadSuccess(res);
    } catch (err: any) {
      alert(err.message || 'CSV upload failed');
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="bento-card rounded-2xl p-6 flex flex-col justify-between h-full">
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Upload className="w-4 h-4" />
            </div>
            <h2 className="text-lg font-semibold text-white">SIP Transactions CSV Input</h2>
          </div>
          <span className="text-xs text-slate-400">Step 1 of 2</span>
        </div>

        {/* Dropzone */}
        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-6 text-center transition-all cursor-pointer relative ${
            dragActive
              ? 'border-indigo-400 bg-indigo-500/10'
              : 'border-slate-700/60 hover:border-slate-600 bg-slate-900/40'
          }`}
        >
          <input
            type="file"
            accept=".csv"
            onChange={handleFileInput}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            disabled={isLoadingUpload}
          />
          <div className="flex flex-col items-center justify-center space-y-2">
            <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-indigo-400">
              {uploadData ? <FileCheck className="w-5 h-5 text-emerald-400" /> : <Upload className="w-5 h-5" />}
            </div>
            {uploadData ? (
              <div>
                <p className="text-sm font-medium text-emerald-400">
                  Found {uploadData.total_transactions} transactions for {uploadData.schemes.length} mutual funds
                </p>
                <p className="text-xs text-slate-400 mt-0.5">Click or drag a new CSV to replace</p>
              </div>
            ) : (
              <div>
                <p className="text-sm font-medium text-slate-200">
                  {isLoadingUpload ? 'Parsing CSV File...' : 'Drop your SIP transaction CSV here'}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">Expected columns: date, amount, scheme_code (or scheme_name)</p>
              </div>
            )}
          </div>
        </div>

        {/* Upload Summary Table */}
        {uploadData && (
          <div className="mt-4 bg-slate-900/70 border border-slate-800 rounded-xl p-3.5 space-y-2 text-xs">
            <div className="flex items-center justify-between text-slate-400 font-medium pb-1 border-b border-slate-800">
              <span>Detected Fund Schemes ({uploadData.schemes.length})</span>
              <span>Tx Count / Invested</span>
            </div>
            {uploadData.schemes.map((s) => (
              <div key={s.scheme_code} className="flex items-center justify-between text-slate-300">
                <span className="font-mono text-indigo-300 truncate max-w-[200px]" title={s.scheme_name}>
                  {s.scheme_code} — {s.scheme_name}
                </span>
                <span>
                  {s.transaction_count} txs ({formatINR(s.total_amount)})
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Configuration Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1.5">
              <BarChart3 className="w-3.5 h-3.5 text-indigo-400" /> Benchmark Index
            </label>
            <select
              value={selectedBenchmark}
              onChange={(e) => setSelectedBenchmark(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="NIFTY50">Nifty 50 (^NSEI)</option>
              <option value="SENSEX">S&P BSE Sensex (^BSESN)</option>
              <option value="NIFTYMIDCAP">Nifty Midcap 100 (^NSMIDCP)</option>
              <option value="NIFTYBANK">Nifty Bank (^NSEBANK)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-indigo-400" /> Valuation Date (Optional)
            </label>
            <input
              type="date"
              value={valuationDate}
              onChange={(e) => setValuationDate(e.target.value)}
              placeholder="Latest NAV Date"
              className="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>
      </div>

      {/* Action Button */}
      <div className="mt-5">
        {error && (
          <div className="mb-3 p-3 bg-rose-950/60 border border-rose-500/30 rounded-xl text-xs text-rose-300 flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <button
          onClick={() => onRunPerformance(selectedBenchmark, valuationDate || undefined)}
          disabled={!uploadData || isLoadingPerformance}
          className={`w-full py-3 px-4 rounded-xl text-xs font-semibold flex items-center justify-center space-x-2 transition-all shadow-lg ${
            !uploadData || isLoadingPerformance
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50'
              : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/30 border border-indigo-400/30'
          }`}
        >
          {isLoadingPerformance ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Fetching NAV History & Benchmark Data...</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" />
              <span>Run Performance Evaluation</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
