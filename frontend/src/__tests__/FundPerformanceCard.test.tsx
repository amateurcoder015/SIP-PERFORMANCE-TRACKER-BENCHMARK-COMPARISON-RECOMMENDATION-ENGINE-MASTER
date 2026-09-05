import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FundPerformanceCard } from '../components/FundPerformanceCard';
import { FundPerformanceError } from '../types';

describe('FundPerformanceCard Component', () => {
  const failedFundItem: FundPerformanceError = {
    scheme_code: '400',
    error: 'Fund 400 has insufficient history for long-term scoring (data span 0.8 years < minimum 1.0 years required).',
  };

  it('renders specific domain error message when fund evaluation fails instead of a generic failure state', () => {
    const handleSelectRecommend = vi.fn();

    render(
      <FundPerformanceCard
        schemeCode="400"
        item={failedFundItem}
        onSelectRecommend={handleSelectRecommend}
        isSelectedForRecommend={false}
        isLoadingRecommend={false}
      />
    );

    expect(screen.getByText(/Evaluation Failed/i)).toBeInTheDocument();
    expect(screen.getByText(/Fund 400 has insufficient history for long-term scoring/i)).toBeInTheDocument();
    expect(screen.getByText(/data span 0.8 years < minimum 1.0 years required/i)).toBeInTheDocument();
  });
});
