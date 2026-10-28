import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import type { ExamplesResponse, HistoryResponse, QueryResponse } from '../types/api';

const mockExamples: ExamplesResponse = {
  total_count: 2,
  categories: [
    {
      category: 'revenue',
      title: 'Revenue',
      description: 'Revenue questions',
      examples: [
        {
          title: 'Total Revenue',
          question: 'What is the total revenue across all completed orders?',
        },
      ],
    },
  ],
};

const mockHistory: HistoryResponse = {
  total: 1,
  limit: 20,
  offset: 0,
  items: [
    {
      id: 1,
      request_id: 'req_hist_01',
      created_at: '2024-11-01T12:00:00Z',
      question: 'Previous historical question',
      status: 'success',
      sql: 'SELECT 1;',
      row_count: 1,
      error_code: null,
      duration_ms: 25.4,
    },
  ],
};

describe('App Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // Default fetch mock handles GET /examples and GET /history
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/examples')) {
        return {
          ok: true,
          json: async () => mockExamples,
          headers: new Headers(),
        } as Response;
      }
      if (url.includes('/history')) {
        return {
          ok: true,
          json: async () => mockHistory,
          headers: new Headers(),
        } as Response;
      }
      return {
        ok: true,
        json: async () => ({}),
        headers: new Headers(),
      } as Response;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders initial empty state before any query is run', async () => {
    render(<App />);
    expect(
      screen.getByRole('heading', { name: /AI-Powered Analytics Assistant/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Ask natural language business questions/i)
    ).toBeInTheDocument();
    // Wait for async initial fetches (example chips) to settle
    expect(await screen.findByText('Total Revenue')).toBeInTheDocument();
  });

  it('handles loading state while waiting for API query response', async () => {
    let resolveQuery!: (res: Response) => void;
    const queryPromise = new Promise<Response>((resolve) => {
      resolveQuery = resolve;
    });

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/query')) {
        return queryPromise;
      }
      if (url.includes('/examples')) {
        return {
          ok: true,
          json: async () => mockExamples,
          headers: new Headers(),
        } as Response;
      }
      return { ok: true, json: async () => ({}), headers: new Headers() } as Response;
    });

    render(<App />);

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'What is total revenue?' } });
    fireEvent.click(screen.getByRole('button', { name: /Run Query/i }));

    // Verify loading skeleton and button state
    expect(screen.getByText(/Analyzing.../i)).toBeInTheDocument();
    expect(screen.getByText(/Processing Analytical Query/i)).toBeInTheDocument();
    expect(screen.getByText(/1. Translating Question/i)).toBeInTheDocument();

    // Resolve query
    const successPayload: QueryResponse = {
      status: 'success',
      question: 'What is total revenue?',
      answer: 'Total revenue is $500.',
      sql: 'SELECT 500;',
      columns: ['rev'],
      rows: [[500]],
      row_count: 1,
      truncated: false,
      chart_hint: null,
      explanation_source: 'llm',
      request_id: 'req_123',
      history_id: 1,
      rejection_reasons: [],
    };

    resolveQuery({
      ok: true,
      headers: new Headers({ 'X-Request-ID': 'req_123' }),
      json: async () => successPayload,
    } as Response);

    await waitFor(() => {
      expect(screen.getByText('Total revenue is $500.')).toBeInTheDocument();
    });
  });

  it('displays results table, answer, and chart on success', async () => {
    const successResponse: QueryResponse = {
      status: 'success',
      question: 'Revenue by region?',
      answer: 'Revenue breakdown by customer region.',
      sql: 'SELECT region, revenue FROM summary;',
      columns: ['region', 'revenue'],
      rows: [
        ['North America', 150000.0],
        ['EMEA', 120000.0],
      ],
      row_count: 2,
      truncated: false,
      chart_hint: {
        type: 'bar',
        x_key: 'region',
        y_key: 'revenue',
        title: 'Regional Revenue',
      },
      explanation_source: 'llm',
      request_id: 'req_success_1',
      history_id: 2,
      rejection_reasons: [],
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/query')) {
        return {
          ok: true,
          headers: new Headers({ 'X-Request-ID': 'req_success_1' }),
          json: async () => successResponse,
        } as Response;
      }
      return { ok: true, json: async () => mockExamples, headers: new Headers() } as Response;
    });

    render(<App />);

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Revenue by region?' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Run Query/i }));

    await waitFor(() => {
      expect(screen.getByText('Query Executed Successfully')).toBeInTheDocument();
      expect(screen.getByText('Revenue breakdown by customer region.')).toBeInTheDocument();
      expect(screen.getByText('North America')).toBeInTheDocument();
      expect(screen.getByText('Regional Revenue')).toBeInTheDocument();
    });
  });

  it('displays unsupported banner when question cannot be answered', async () => {
    const unsupportedResponse: QueryResponse = {
      status: 'unsupported',
      question: 'Stock price in 2030?',
      answer: null,
      sql: null,
      columns: [],
      rows: [],
      row_count: 0,
      truncated: false,
      chart_hint: null,
      explanation_source: 'none',
      request_id: 'req_unsup',
      history_id: 3,
      rejection_reasons: ['Stock forecast is outside database schema.'],
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/query')) {
        return {
          ok: true,
          headers: new Headers({ 'X-Request-ID': 'req_unsup' }),
          json: async () => unsupportedResponse,
        } as Response;
      }
      return { ok: true, json: async () => mockExamples, headers: new Headers() } as Response;
    });

    render(<App />);

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Stock price in 2030?' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Run Query/i }));

    await waitFor(() => {
      expect(screen.getByText('Question Out of Scope')).toBeInTheDocument();
      expect(
        screen.getByText(/I can't answer that from the available data/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText('Stock forecast is outside database schema.')
      ).toBeInTheDocument();
    });
  });

  it('displays rejected banner for security violations with detailed reasons', async () => {
    const rejectedResponse: QueryResponse = {
      status: 'rejected',
      question: 'Drop table orders',
      answer: null,
      sql: 'DROP TABLE orders;',
      columns: [],
      rows: [],
      row_count: 0,
      truncated: false,
      chart_hint: null,
      explanation_source: 'none',
      request_id: 'req_rej',
      history_id: 4,
      rejection_reasons: [
        "Root statement type 'Drop' is not permitted.",
        'Only SELECT queries are allowed.',
      ],
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/query')) {
        return {
          ok: true,
          headers: new Headers({ 'X-Request-ID': 'req_rej' }),
          json: async () => rejectedResponse,
        } as Response;
      }
      return { ok: true, json: async () => mockExamples, headers: new Headers() } as Response;
    });

    render(<App />);

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Drop table orders' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Run Query/i }));

    await waitFor(() => {
      expect(screen.getByText('Query Rejected for Safety')).toBeInTheDocument();
      expect(
        screen.getByText("Root statement type 'Drop' is not permitted.")
      ).toBeInTheDocument();
      expect(screen.getByText('Only SELECT queries are allowed.')).toBeInTheDocument();
    });
  });

  it('displays API error envelope with request_id on server errors', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/query')) {
        return {
          ok: false,
          status: 503,
          headers: new Headers({ 'X-Request-ID': 'req_fail_123' }),
          json: async () => ({
            error: {
              code: 'LLM_UNAVAILABLE',
              message: 'Upstream LLM service is currently unreachable.',
            },
            request_id: 'req_fail_123',
          }),
        } as Response;
      }
      return { ok: true, json: async () => mockExamples, headers: new Headers() } as Response;
    });

    render(<App />);

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'What is revenue?' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Run Query/i }));

    await waitFor(() => {
      expect(screen.getByText('Request Failed: LLM_UNAVAILABLE')).toBeInTheDocument();
      expect(
        screen.getByText('Upstream LLM service is currently unreachable.')
      ).toBeInTheDocument();
      expect(screen.getByText('req_fail_123')).toBeInTheDocument();
    });
  });

  it('displays friendly network error when fetch completely fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/query')) {
        throw new TypeError('Failed to fetch');
      }
      return { ok: true, json: async () => mockExamples, headers: new Headers() } as Response;
    });

    render(<App />);

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'What is revenue?' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Run Query/i }));

    await waitFor(() => {
      expect(screen.getByText('Request Failed: NETWORK_ERROR')).toBeInTheDocument();
      expect(
        screen.getByText(/Unable to reach the DataQuery analytics server/i)
      ).toBeInTheDocument();
    });
  });

  it('shows empty-result state when query succeeds with 0 rows', async () => {
    const zeroRowsResponse: QueryResponse = {
      status: 'success',
      question: 'Orders over 1 billion dollars',
      answer: 'No rows matched this question.',
      sql: 'SELECT * FROM orders WHERE total > 1000000000;',
      columns: ['id', 'total'],
      rows: [],
      row_count: 0,
      truncated: false,
      chart_hint: null,
      explanation_source: 'fallback',
      request_id: 'req_zero',
      history_id: 5,
      rejection_reasons: [],
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/query')) {
        return {
          ok: true,
          headers: new Headers({ 'X-Request-ID': 'req_zero' }),
          json: async () => zeroRowsResponse,
        } as Response;
      }
      return { ok: true, json: async () => mockExamples, headers: new Headers() } as Response;
    });

    render(<App />);

    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Orders over 1 billion dollars' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Run Query/i }));

    await waitFor(() => {
      expect(screen.getByText('No matching records found')).toBeInTheDocument();
      expect(screen.getByText('Summary generated from fallback')).toBeInTheDocument();
    });
  });

  it('clicking an example chip fills input and executes query', async () => {
    const successResponse: QueryResponse = {
      status: 'success',
      question: 'What is the total revenue across all completed orders?',
      answer: 'Total revenue is $1,250,000.',
      sql: 'SELECT SUM(amount) FROM payments;',
      columns: ['total'],
      rows: [[1250000]],
      row_count: 1,
      truncated: false,
      chart_hint: null,
      explanation_source: 'llm',
      request_id: 'req_ex_1',
      history_id: 6,
      rejection_reasons: [],
    };

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes('/examples')) {
        return { ok: true, json: async () => mockExamples, headers: new Headers() } as Response;
      }
      if (url.includes('/query')) {
        return {
          ok: true,
          headers: new Headers({ 'X-Request-ID': 'req_ex_1' }),
          json: async () => successResponse,
        } as Response;
      }
      return { ok: true, json: async () => ({}), headers: new Headers() } as Response;
    });

    render(<App />);

    // Wait for chip to load
    const chip = await screen.findByRole('button', { name: /Total Revenue/i });
    fireEvent.click(chip);

    // Verify textarea was updated and query ran
    await waitFor(() => {
      expect(screen.getByText('Total revenue is $1,250,000.')).toBeInTheDocument();
    });
  });

  it('opens history panel, displays audit items, and re-fills query on click', async () => {
    render(<App />);

    // Wait for initial async example chips to settle
    expect(await screen.findByText('Total Revenue')).toBeInTheDocument();

    // Click History button in header
    const historyBtn = screen.getByRole('button', { name: /Open Query History Panel/i });
    fireEvent.click(historyBtn);

    // History drawer should appear
    expect(await screen.findByText('Previous historical question')).toBeInTheDocument();

    // Click history item
    fireEvent.click(screen.getByText('Previous historical question'));

    // Drawer closes and textarea is filled
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    await waitFor(() => {
      expect(textarea.value).toBe('Previous historical question');
    });
  });
});
