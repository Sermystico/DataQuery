import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { QueryHistoryItem } from '../types/api';

interface HistoryPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectQuery: (question: string) => void;
  refreshTrigger?: number;
}

export function HistoryPanel({
  isOpen,
  onClose,
  onSelectQuery,
  refreshTrigger = 0,
}: HistoryPanelProps) {
  const [historyItems, setHistoryItems] = useState<QueryHistoryItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getHistory(20, 0);
      setHistoryItems(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('Failed to load history:', err);
      setError('Unable to load query history.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      // oxlint-disable-next-line react/set-state-in-effect
      fetchHistory();
    }
  }, [isOpen, refreshTrigger]);

  if (!isOpen) {
    return null;
  }

  const formatTimestamp = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) +
        ', ' +
        date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return isoString;
    }
  };

  return (
    <aside
      className="history-drawer"
      aria-label="Query Execution History"
      role="dialog"
      aria-modal="true"
    >
      <div className="history-header">
        <div className="history-title-group">
          <span className="history-icon" aria-hidden="true">⏱</span>
          <h2 className="history-title">Query History</h2>
          <span className="history-count-badge">{total}</span>
        </div>
        <div className="history-header-actions">
          <button
            type="button"
            className="icon-btn refresh-btn"
            onClick={fetchHistory}
            disabled={loading}
            title="Refresh history"
            aria-label="Refresh history"
          >
            ↻
          </button>
          <button
            type="button"
            className="icon-btn close-btn"
            onClick={onClose}
            title="Close history panel"
            aria-label="Close history panel"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="history-content">
        {loading && (
          <div className="history-loading">
            <span className="spinner" aria-hidden="true" />
            <span>Loading audit history...</span>
          </div>
        )}

        {error && (
          <div className="history-error" role="alert">
            <span>{error}</span>
            <button type="button" onClick={fetchHistory} className="retry-btn">
              Retry
            </button>
          </div>
        )}

        {!loading && !error && historyItems.length === 0 && (
          <div className="history-empty">
            <p>No historical queries recorded yet.</p>
          </div>
        )}

        {!loading && !error && historyItems.length > 0 && (
          <ul className="history-list">
            {historyItems.map((item) => (
              <li key={item.id} className="history-item">
                <button
                  type="button"
                  className="history-item-btn"
                  onClick={() => {
                    onSelectQuery(item.question);
                    onClose();
                  }}
                  title={`Run "${item.question}"`}
                >
                  <div className="history-item-header">
                    <span className={`status-pill status-${item.status}`}>
                      {item.status}
                    </span>
                    <span className="history-time">
                      {formatTimestamp(item.created_at)}
                    </span>
                  </div>
                  <div className="history-question">{item.question}</div>
                  <div className="history-meta">
                    {item.row_count !== null && (
                      <span className="history-meta-tag">
                        {item.row_count} {item.row_count === 1 ? 'row' : 'rows'}
                      </span>
                    )}
                    {item.duration_ms !== null && (
                      <span className="history-meta-tag">
                        {Math.round(item.duration_ms)}ms
                      </span>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
