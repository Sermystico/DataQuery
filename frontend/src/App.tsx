import { useCallback, useState } from 'react';
import './App.css';
import { ApiClientError, apiClient } from './api/client';
import { AnswerCard } from './components/AnswerCard';
import { ChartView } from './components/ChartView';
import { EmptyState } from './components/EmptyState';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ExampleChips } from './components/ExampleChips';
import { HistoryPanel } from './components/HistoryPanel';
import { LoadingSkeleton } from './components/LoadingSkeleton';
import { QuestionForm } from './components/QuestionForm';
import { ResultsTable } from './components/ResultsTable';
import { SqlViewer } from './components/SqlViewer';
import { StatusBanner } from './components/StatusBanner';
import type { QueryResponse } from './types/api';

export function App() {
  const [currentQuestion, setCurrentQuestion] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [apiError, setApiError] = useState<{
    message: string;
    code?: string;
    requestId?: string;
  } | null>(null);
  const [historyOpen, setHistoryOpen] = useState<boolean>(false);
  const [historyRefreshKey, setHistoryRefreshKey] = useState<number>(0);

  const executeQuestion = useCallback(
    async (questionText: string) => {
      if (loading) {
        return;
      }

      setLoading(true);
      setApiError(null);
      setCurrentQuestion(questionText);

      try {
        const result = await apiClient.executeQuery({
          question: questionText,
          include_explanation: true,
        });
        setResponse(result);
        setHistoryRefreshKey((prev) => prev + 1);
      } catch (err: unknown) {
        setResponse(null);
        if (err instanceof ApiClientError) {
          setApiError({
            message: err.message,
            code: err.code,
            requestId: err.requestId,
          });
        } else if (err instanceof Error) {
          setApiError({
            message: err.message,
            code: 'CLIENT_ERROR',
          });
        } else {
          setApiError({
            message: 'An unexpected error occurred.',
            code: 'UNKNOWN_ERROR',
          });
        }
      } finally {
        setLoading(false);
      }
    },
    [loading]
  );

  const handleSelectExample = (question: string) => {
    setCurrentQuestion(question);
    executeQuestion(question);
  };

  const handleSelectHistory = (question: string) => {
    setCurrentQuestion(question);
    executeQuestion(question);
  };

  return (
    <ErrorBoundary>
      <div className="app-layout">
        <header className="app-header">
          <div className="header-inner">
            <div className="brand-group">
              <span className="brand-icon" aria-hidden="true">⚡</span>
              <div className="brand-titles">
                <h1 className="brand-name">DataQuery</h1>
                <span className="brand-subtitle">AI-Powered Analytics Assistant</span>
              </div>
            </div>

            <div className="header-actions">
              <button
                type="button"
                className="history-toggle-btn"
                onClick={() => setHistoryOpen(true)}
                aria-label="Open Query History Panel"
                title="View recent queries audit log"
              >
                <span className="btn-icon" aria-hidden="true">⏱</span>
                <span>History</span>
              </button>
            </div>
          </div>
        </header>

        <main className="main-content">
          <div className="query-box-section">
            <QuestionForm
              initialValue={currentQuestion}
              loading={loading}
              onSubmit={executeQuestion}
            />

            <ExampleChips
              onSelect={handleSelectExample}
              disabled={loading}
            />
          </div>

          <div className="results-section">
            {loading && <LoadingSkeleton />}

            {!loading && apiError && (
              <StatusBanner
                status="error"
                errorMessage={apiError.message}
                errorCode={apiError.code}
                requestId={apiError.requestId}
              />
            )}

            {!loading && response && (
              <div className="response-display">
                <StatusBanner
                  status={response.status}
                  rejectionReasons={response.rejection_reasons}
                  rowCount={response.row_count}
                />

                {response.status === 'success' && (
                  <>
                    <AnswerCard
                      answer={response.answer}
                      explanationSource={response.explanation_source}
                    />

                    {response.chart_hint && (
                      <ChartView
                        chartHint={response.chart_hint}
                        columns={response.columns}
                        rows={response.rows}
                      />
                    )}

                    {response.row_count === 0 ? (
                      <EmptyState type="zero_rows" question={response.question} />
                    ) : (
                      <ResultsTable
                        columns={response.columns}
                        rows={response.rows}
                        rowCount={response.row_count}
                        truncated={response.truncated}
                      />
                    )}

                    <SqlViewer sql={response.sql} />
                  </>
                )}

                {response.status === 'rejected' && (
                  <SqlViewer sql={response.sql} />
                )}
              </div>
            )}

            {!loading && !apiError && !response && (
              <EmptyState type="initial" />
            )}
          </div>
        </main>

        <HistoryPanel
          isOpen={historyOpen}
          onClose={() => setHistoryOpen(false)}
          onSelectQuery={handleSelectHistory}
          refreshTrigger={historyRefreshKey}
        />

        <footer className="app-footer">
          <div className="footer-inner">
            <span>DataQuery Analytics Engine • PostgreSQL 16 & SQLGlot Guardrails</span>
          </div>
        </footer>
      </div>
    </ErrorBoundary>
  );
}

export default App;
