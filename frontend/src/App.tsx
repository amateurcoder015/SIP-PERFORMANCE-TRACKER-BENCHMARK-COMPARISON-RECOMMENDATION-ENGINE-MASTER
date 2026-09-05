import React, { useState } from 'react';
import { Header } from './components/Header';
import { UploadPanel } from './components/UploadPanel';
import { PortfolioSummaryPanel } from './components/PortfolioSummaryPanel';
import { FundPerformanceCard } from './components/FundPerformanceCard';
import { RecommendationPanel } from './components/RecommendationPanel';
import { MetadataPanel } from './components/MetadataPanel';
import { UploadResponse, PerformanceResponse, RecommendationResult } from './types';
import { fetchPerformance, fetchRecommendations } from './api';
import { Layers } from 'lucide-react';

export const App: React.FC = () => {
  const [uploadData, setUploadData] = useState<UploadResponse | null>(null);
  const [performanceData, setPerformanceData] = useState<PerformanceResponse | null>(null);
  const [selectedBenchmark, setSelectedBenchmark] = useState<string>('NIFTY50');
  const [valuationDate, setValuationDate] = useState<string | undefined>(undefined);

  const [isLoadingPerformance, setIsLoadingPerformance] = useState<boolean>(false);
  const [performanceError, setPerformanceError] = useState<string | null>(null);

  // Recommendations state
  const [selectedSchemeForRecommend, setSelectedSchemeForRecommend] = useState<string | null>(null);
  const [recommendationData, setRecommendationData] = useState<RecommendationResult | null>(null);
  const [isLoadingRecommend, setIsLoadingRecommend] = useState<boolean>(false);
  const [recommendError, setRecommendError] = useState<string | null>(null);

  const handleUploadSuccess = (data: UploadResponse) => {
    setUploadData(data);
    setPerformanceData(null);
    setRecommendationData(null);
    setSelectedSchemeForRecommend(null);
    setPerformanceError(null);
  };

  const handleRunPerformance = async (benchmarkName: string, valDate?: string) => {
    if (!uploadData || !uploadData.transactions.length) return;

    setIsLoadingPerformance(true);
    setPerformanceError(null);
    setSelectedBenchmark(benchmarkName);
    setValuationDate(valDate);
    setRecommendationData(null);
    setSelectedSchemeForRecommend(null);

    try {
      const res = await fetchPerformance(uploadData.transactions, benchmarkName, valDate);
      setPerformanceData(res);
    } catch (err: any) {
      setPerformanceError(err.message || 'Failed to evaluate fund performance');
    } finally {
      setIsLoadingPerformance(false);
    }
  };

  const handleSelectRecommend = async (schemeCode: string) => {
    setSelectedSchemeForRecommend(schemeCode);
    setIsLoadingRecommend(true);
    setRecommendError(null);

    try {
      const res = await fetchRecommendations(schemeCode, 30, 5, 3.0);
      setRecommendationData(res);
    } catch (err: any) {
      setRecommendError(err.message || 'Failed to fetch recommendations');
    } finally {
      setIsLoadingRecommend(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <Header />

      {/* Bento Grid Layer 1: Upload + Portfolio Summary + Metadata */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-stretch">
        {/* Upload & Setup Card (4 cols on lg) */}
        <div className="md:col-span-6 lg:col-span-5">
          <UploadPanel
            onUploadSuccess={handleUploadSuccess}
            onRunPerformance={handleRunPerformance}
            isLoadingUpload={false}
            isLoadingPerformance={isLoadingPerformance}
            uploadData={uploadData}
            error={performanceError}
          />
        </div>

        {/* Portfolio Sum Totals Card (4 cols on lg) */}
        <div className="md:col-span-6 lg:col-span-4">
          <PortfolioSummaryPanel performanceData={performanceData} />
        </div>

        {/* Metadata & Data Freshness Card (3 cols on lg) */}
        <div className="md:col-span-12 lg:col-span-3">
          <MetadataPanel benchmarkName={selectedBenchmark} valuationDate={valuationDate} />
        </div>
      </div>

      {/* Bento Grid Layer 2: Per-Fund Performance Tiles */}
      {performanceData && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-7 h-7 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                <Layers className="w-4 h-4" />
              </div>
              <h2 className="text-lg font-bold text-white">
                Per-Fund Money-Weighted Returns (XIRR) vs. {selectedBenchmark}
              </h2>
            </div>
            <span className="text-xs text-slate-400 font-mono">
              {Object.keys(performanceData).length} Funds Evaluated
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Object.entries(performanceData).map(([code, item]) => (
              <FundPerformanceCard
                key={code}
                schemeCode={code}
                item={item}
                onSelectRecommend={handleSelectRecommend}
                isSelectedForRecommend={selectedSchemeForRecommend === code}
                isLoadingRecommend={isLoadingRecommend && selectedSchemeForRecommend === code}
              />
            ))}
          </div>
        </div>
      )}

      {/* Bento Grid Layer 3: Long-Term Peer Recommendation Panel */}
      {(selectedSchemeForRecommend || recommendationData || isLoadingRecommend) && (
        <div className="mt-8">
          <RecommendationPanel
            recommendationData={recommendationData}
            isLoading={isLoadingRecommend}
            error={recommendError}
          />
        </div>
      )}
    </div>
  );
};
