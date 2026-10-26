/**
 * TypeScript API contracts mirroring DataQuery backend Pydantic schemas.
 * 
 * Strict alignment with:
 * - backend/app/schemas/query.py
 * - backend/app/schemas/errors.py
 * - backend/app/schemas/examples.py
 * - backend/app/schemas/history.py
 * - backend/app/schemas/schema.py
 */

export interface ChartHint {
  type: 'bar' | 'line' | 'none';
  x_key: string | null;
  y_key: string | null;
  title?: string | null;
}

export interface QueryRequest {
  question: string;
  include_explanation?: boolean;
}

export type QueryStatus = 'success' | 'unsupported' | 'rejected';
export type ExplanationSource = 'llm' | 'fallback' | 'none';

export interface QueryResponse {
  status: QueryStatus;
  question: string;
  answer: string | null;
  sql: string | null;
  columns: string[];
  rows: (string | number | boolean | null)[][];
  row_count: number;
  truncated: boolean;
  chart_hint: ChartHint | null;
  explanation_source: ExplanationSource;
  request_id: string;
  history_id: number | null;
  rejection_reasons: string[];
}

export interface ErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface ErrorEnvelope {
  error: ErrorDetail;
  request_id: string;
}

export interface ExampleQuestion {
  title: string;
  question: string;
}

export interface CategoryExamples {
  category: string;
  title: string;
  description: string;
  examples: ExampleQuestion[];
}

export interface ExamplesResponse {
  total_count: number;
  categories: CategoryExamples[];
}

export interface QueryHistoryItem {
  id: number;
  request_id: string;
  created_at: string;
  question: string;
  status: 'success' | 'unsupported' | 'rejected' | 'error' | string;
  sql: string | null;
  row_count: number | null;
  error_code: string | null;
  duration_ms: number | null;
}

export interface HistoryResponse {
  items: QueryHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ColumnSchema {
  name: string;
  type: string;
  primary_key: boolean;
  nullable: boolean;
  description: string;
  references: string | null;
}

export interface TableSchema {
  name: string;
  description: string;
  columns: ColumnSchema[];
}

export interface SchemaResponse {
  database: string;
  as_of_date: string;
  tables: TableSchema[];
  business_definitions: Record<string, string>;
}
