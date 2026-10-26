/**
 * Standard API Client for DataQuery backend.
 * 
 * Invariants:
 * 1. Base URL defaults to '/api/v1' using the Vite dev proxy to http://localhost:8000.
 * 2. Timeout handling with AbortController.
 * 3. Structured parsing of backend ErrorEnvelope { error: { code, message, details }, request_id }.
 * 4. Friendly error mapping for network disconnects and timeouts.
 * 5. Zero secrets, credentials, or API keys in frontend code.
 */

import type {
  ErrorEnvelope,
  ExamplesResponse,
  HistoryResponse,
  QueryHistoryItem,
  QueryRequest,
  QueryResponse,
  SchemaResponse,
} from '../types/api';

export class ApiClientError extends Error {
  readonly code: string;
  readonly details?: Record<string, unknown> | null;
  readonly requestId?: string;
  readonly status?: number;

  constructor(
    message: string,
    options: {
      code?: string;
      details?: Record<string, unknown> | null;
      requestId?: string;
      status?: number;
    } = {}
  ) {
    super(message);
    this.name = 'ApiClientError';
    this.code = options.code ?? 'UNKNOWN_ERROR';
    this.details = options.details;
    this.requestId = options.requestId;
    this.status = options.status;
  }
}

export interface ClientConfig {
  baseUrl?: string;
  defaultTimeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 90000;

export class ApiClient {
  private readonly baseUrl: string;
  private readonly defaultTimeoutMs: number;

  constructor(config: ClientConfig = {}) {
    const rawBaseUrl =
      config.baseUrl ??
      (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL
        ? import.meta.env.VITE_API_BASE_URL
        : '/api/v1');

    // Strip trailing slash if present
    this.baseUrl = rawBaseUrl.replace(/\/+$/, '');
    this.defaultTimeoutMs = config.defaultTimeoutMs ?? DEFAULT_TIMEOUT_MS;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    customTimeoutMs?: number
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    const timeoutMs = customTimeoutMs ?? this.defaultTimeoutMs;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
    }, timeoutMs);

    // If an external signal was passed, forward aborts
    if (options.signal) {
      options.signal.addEventListener('abort', () => controller.abort());
    }

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          ...options.headers,
        },
      });

      const responseRequestId =
        response.headers.get('X-Request-ID') ?? undefined;

      if (!response.ok) {
        let envelope: ErrorEnvelope | null = null;
        try {
          envelope = (await response.json()) as ErrorEnvelope;
        } catch {
          // Response body was not JSON
        }

        if (envelope && envelope.error) {
          throw new ApiClientError(envelope.error.message, {
            code: envelope.error.code,
            details: envelope.error.details,
            requestId: envelope.request_id || responseRequestId,
            status: response.status,
          });
        }

        throw new ApiClientError(`Server returned HTTP ${response.status}`, {
          code: `HTTP_${response.status}`,
          requestId: responseRequestId,
          status: response.status,
        });
      }

      return (await response.json()) as T;
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        throw err;
      }

      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new ApiClientError('Request timed out. Please try again.', {
          code: 'TIMEOUT_ERROR',
        });
      }

      if (err instanceof TypeError) {
        throw new ApiClientError(
          'Unable to reach the DataQuery analytics server. Please check your connection.',
          {
            code: 'NETWORK_ERROR',
          }
        );
      }

      throw new ApiClientError(
        err instanceof Error ? err.message : 'An unexpected error occurred.',
        {
          code: 'CLIENT_ERROR',
        }
      );
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Submit natural language question for execution.
   */
  async executeQuery(
    payload: QueryRequest,
    signal?: AbortSignal
  ): Promise<QueryResponse> {
    return this.request<QueryResponse>('/query', {
      method: 'POST',
      body: JSON.stringify(payload),
      signal,
    });
  }

  /**
   * Retrieve curated example questions grouped by analytical domain.
   */
  async getExamples(signal?: AbortSignal): Promise<ExamplesResponse> {
    return this.request<ExamplesResponse>('/examples', {
      method: 'GET',
      signal,
    });
  }

  /**
   * Retrieve paginated query audit history.
   */
  async getHistory(
    limit: number = 20,
    offset: number = 0,
    signal?: AbortSignal
  ): Promise<HistoryResponse> {
    const params = new URLSearchParams({
      limit: String(Math.max(1, Math.min(limit, 100))),
      offset: String(Math.max(0, offset)),
    });
    return this.request<HistoryResponse>(`/history?${params.toString()}`, {
      method: 'GET',
      signal,
    });
  }

  /**
   * Retrieve single query execution details by ID.
   */
  async getHistoryItem(
    id: number,
    signal?: AbortSignal
  ): Promise<QueryHistoryItem> {
    return this.request<QueryHistoryItem>(`/history/${id}`, {
      method: 'GET',
      signal,
    });
  }

  /**
   * Retrieve catalog schema explorer definitions.
   */
  async getSchema(signal?: AbortSignal): Promise<SchemaResponse> {
    return this.request<SchemaResponse>('/schema', {
      method: 'GET',
      signal,
    });
  }
}

export const apiClient = new ApiClient();
