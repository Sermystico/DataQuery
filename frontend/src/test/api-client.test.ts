import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiClientError } from '../api/client';
import type { ErrorEnvelope, QueryResponse } from '../types/api';

describe('ApiClient', () => {
  let client: ApiClient;

  beforeEach(() => {
    client = new ApiClient({ baseUrl: 'http://localhost:8000/api/v1' });
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('successfully executes query and parses JSON response', async () => {
    const mockResponse: QueryResponse = {
      status: 'success',
      question: 'Total revenue?',
      answer: 'Total revenue is $1000.',
      sql: 'SELECT SUM(amount) FROM payments;',
      columns: ['total_revenue'],
      rows: [[1000.0]],
      row_count: 1,
      truncated: false,
      chart_hint: null,
      explanation_source: 'llm',
      request_id: 'req_test123',
      history_id: 1,
      rejection_reasons: [],
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      headers: new Headers({ 'X-Request-ID': 'req_test123' }),
      json: async () => mockResponse,
    } as Response);

    const res = await client.executeQuery({ question: 'Total revenue?' });
    expect(res.status).toBe('success');
    expect(res.answer).toBe('Total revenue is $1000.');
    expect(res.request_id).toBe('req_test123');
  });

  it('parses standard backend ErrorEnvelope on HTTP error', async () => {
    const errorEnvelope: ErrorEnvelope = {
      error: {
        code: 'VALIDATION_REJECTED',
        message: 'Disallowed table access.',
        details: { table: 'pg_shadow' },
      },
      request_id: 'req_err_999',
    };

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
      headers: new Headers({ 'X-Request-ID': 'req_err_999' }),
      json: async () => errorEnvelope,
    } as Response);

    try {
      await client.executeQuery({ question: 'Select from pg_shadow' });
      expect.fail('Should have thrown ApiClientError');
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiClientError);
      if (err instanceof ApiClientError) {
        expect(err.code).toBe('VALIDATION_REJECTED');
        expect(err.message).toBe('Disallowed table access.');
        expect(err.requestId).toBe('req_err_999');
        expect(err.status).toBe(400);
      }
    }
  });

  it('translates network fetch failure into friendly NETWORK_ERROR', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(
      new TypeError('Failed to fetch')
    );

    try {
      await client.executeQuery({ question: 'What is revenue?' });
      expect.fail('Should have thrown ApiClientError');
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiClientError);
      if (err instanceof ApiClientError) {
        expect(err.code).toBe('NETWORK_ERROR');
        expect(err.message).toContain('Unable to reach');
      }
    }
  });

  it('translates timeout AbortError into friendly TIMEOUT_ERROR', async () => {
    const abortErr = new DOMException('The operation was aborted', 'AbortError');
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(abortErr);

    try {
      await client.executeQuery({ question: 'What is revenue?' });
      expect.fail('Should have thrown ApiClientError');
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiClientError);
      if (err instanceof ApiClientError) {
        expect(err.code).toBe('TIMEOUT_ERROR');
        expect(err.message).toContain('timed out');
      }
    }
  });
});
