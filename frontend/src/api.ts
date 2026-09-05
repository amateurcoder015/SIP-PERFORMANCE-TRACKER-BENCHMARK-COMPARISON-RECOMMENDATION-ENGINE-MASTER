import {
  UploadResponse,
  PerformanceResponse,
  RecommendationResult,
  ParsedTransaction,
} from './types';

const API_BASE = '/api';

export async function uploadTransactionsCSV(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/upload-transactions`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Failed to upload CSV.' }));
    throw new Error(errorData.detail || 'Failed to parse transactions CSV.');
  }

  return res.json();
}

export async function fetchPerformance(
  transactions: ParsedTransaction[],
  benchmarkName: string = 'NIFTY50',
  valuationDate?: string,
  minYearsRequired: number = 1.0
): Promise<PerformanceResponse> {
  const payload = {
    transactions,
    benchmark_name: benchmarkName,
    valuation_date: valuationDate || null,
    min_years_required: minYearsRequired,
  };

  const res = await fetch(`${API_BASE}/performance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Performance evaluation failed.' }));
    throw new Error(errorData.detail || 'Failed to evaluate fund performance.');
  }

  return res.json();
}

export async function fetchRecommendations(
  targetSchemeCode: string,
  maxCandidatesToConfirm: number = 30,
  topN: number = 5,
  minYearsRequired: number = 3.0
): Promise<RecommendationResult> {
  const payload = {
    target_scheme_code: targetSchemeCode,
    max_candidates_to_confirm: maxCandidatesToConfirm,
    top_n: topN,
    min_years_required: minYearsRequired,
  };

  const res = await fetch(`${API_BASE}/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Recommendation fetch failed.' }));
    throw new Error(errorData.detail || 'Failed to fetch alternative fund recommendations.');
  }

  return res.json();
}
