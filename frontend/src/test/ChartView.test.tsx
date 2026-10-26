import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ChartView } from '../components/ChartView';

describe('ChartView', () => {
  it('renders null when chartHint is null or type is none', () => {
    const { container: c1 } = render(
      <ChartView chartHint={null} columns={['a']} rows={[[1]]} />
    );
    expect(c1).toBeEmptyDOMElement();

    const { container: c2 } = render(
      <ChartView
        chartHint={{ type: 'none', x_key: null, y_key: null }}
        columns={['a']}
        rows={[[1]]}
      />
    );
    expect(c2).toBeEmptyDOMElement();
  });

  it('renders null when x_key or y_key is not in columns', () => {
    const { container } = render(
      <ChartView
        chartHint={{ type: 'bar', x_key: 'missing_col', y_key: 'rev' }}
        columns={['region', 'rev']}
        rows={[['North', 100]]}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders bar chart when valid bar chart hint is provided', () => {
    render(
      <ChartView
        chartHint={{ type: 'bar', x_key: 'region', y_key: 'revenue', title: 'Regional Revenue' }}
        columns={['region', 'revenue']}
        rows={[
          ['North America', 150000],
          ['EMEA', 120000],
        ]}
      />
    );

    expect(screen.getByText('Regional Revenue')).toBeInTheDocument();
    expect(screen.getByText('Bar Chart')).toBeInTheDocument();
  });

  it('renders line chart when valid line chart hint is provided', () => {
    render(
      <ChartView
        chartHint={{ type: 'line', x_key: 'order_month', y_key: 'order_count', title: 'Monthly Trends' }}
        columns={['order_month', 'order_count']}
        rows={[
          ['2024-01', 120],
          ['2024-02', 145],
        ]}
      />
    );

    expect(screen.getByText('Monthly Trends')).toBeInTheDocument();
    expect(screen.getByText('Line Trend')).toBeInTheDocument();
  });
});
