export interface ParsedTransaction {
  date: string;
  scheme_code: string;
  scheme_name: string | null;
  amount: number;
}

export interface SchemeSummary {
  scheme_code: string;
  scheme_name: string;
  transaction_count: number;
  total_amount: number;
  start_date: string;
  end_date: string;
}

export interface UploadResponse {
  total_transactions: number;
  schemes: SchemeSummary[];
  transactions: ParsedTransaction[];
}

export interface FundPerformanceResult {
  scheme_code: string;
  scheme_name: string;
  total_invested: number;
  current_value: number;
  units_held: number;
  effective_valuation_date: string;
  actual_xirr: number;
  benchmark_name: string;
  benchmark_xirr: number;
  alpha: number;
  absolute_gain: number;
  num_transactions: number;
  investment_span_years: number;
  nav_date_mismatch_warnings: string[];
}

export interface FundPerformanceError {
  scheme_code: string;
  error: string;
}

export type PerformanceItem = FundPerformanceResult | FundPerformanceError;

export interface PerformanceResponse {
  [scheme_code: string]: PerformanceItem;
}

export interface FundScore {
  scheme_code: string;
  scheme_name: string;
  normalized_category: string;
  windows_used: number[];
  mean_rolling_cagr_by_window: Record<string, number>;
  stdev_rolling_cagr_by_window: Record<string, number>;
  risk_adjusted_metric: number;
  composite_score: number;
  expense_ratio_considered: boolean;
  data_span_years: number;
}

export interface SkippedFund {
  scheme_code: string;
  reason: string;
}

export interface RecommendationResult {
  target_score: FundScore;
  normalized_category: string;
  recommendations: FundScore[];
  reasoning: Record<string, string>;
  skipped_funds: SkippedFund[];
  candidates_confirmed_count: number;
  disclaimer: string;
}
