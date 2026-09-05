import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { RecommendationPanel } from '../components/RecommendationPanel';
import { RecommendationResult } from '../types';

describe('RecommendationPanel Component', () => {
  const sampleRecommendationData: RecommendationResult = {
    target_score: {
      scheme_code: '122639',
      scheme_name: 'Parag Parikh Flexi Cap Fund',
      normalized_category: 'Flexi Cap',
      windows_used: [3.0, 5.0],
      mean_rolling_cagr_by_window: { '3y': 0.18, '5y': 0.16 },
      stdev_rolling_cagr_by_window: { '3y': 0.08, '5y': 0.07 },
      risk_adjusted_metric: 1.5,
      composite_score: 0.82,
      expense_ratio_considered: false,
      data_span_years: 5.5,
    },
    normalized_category: 'Flexi Cap',
    recommendations: [
      {
        scheme_code: '120843',
        scheme_name: 'Quant Flexi Cap Fund',
        normalized_category: 'Flexi Cap',
        windows_used: [3.0, 5.0],
        mean_rolling_cagr_by_window: { '3y': 0.21, '5y': 0.18 },
        stdev_rolling_cagr_by_window: { '3y': 0.1, '5y': 0.09 },
        risk_adjusted_metric: 1.6,
        composite_score: 0.819,
        expense_ratio_considered: false,
        data_span_years: 5.5,
      },
    ],
    reasoning: {
      '120843': 'Ranked #1 in Flexi Cap category with a composite score of 0.819.',
    },
    skipped_funds: [],
    candidates_confirmed_count: 10,
    disclaimer:
      'DISCLAIMER: NOT FINANCIAL ADVICE. This tool provides comparative analytics based on historical mutual fund daily NAV data for personal informational use only. It is not personalized investment, financial, or tax advice, and past performance does not guarantee future results.',
  };

  it('renders recommendation results and ALWAYS renders the exact mandatory financial advice disclaimer prominently', () => {
    render(
      <RecommendationPanel
        recommendationData={sampleRecommendationData}
        isLoading={false}
        error={null}
      />
    );

    // Verify recommendations rendered
    expect(screen.getByText(/Quant Flexi Cap Fund/i)).toBeInTheDocument();
    expect(screen.getByText(/Ranked #1 in Flexi Cap category/i)).toBeInTheDocument();

    // Assert Co-occurrence of Disclaimer
    expect(screen.getByText(/MANDATORY DISCLAIMER/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /DISCLAIMER: NOT FINANCIAL ADVICE. This tool provides comparative analytics based on historical mutual fund daily NAV data for personal informational use only./i
      )
    ).toBeInTheDocument();
  });
});
