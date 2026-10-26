import type { QueryStatus } from '../types/api';

interface StatusBannerProps {
  status?: QueryStatus | 'error';
  rejectionReasons?: string[];
  errorMessage?: string;
  errorCode?: string;
  requestId?: string;
  rowCount?: number;
}

export function StatusBanner({
  status,
  rejectionReasons = [],
  errorMessage,
  errorCode,
  requestId,
  rowCount,
}: StatusBannerProps) {
  if (!status) {
    return null;
  }

  if (status === 'success') {
    return (
      <div className="status-banner status-success" role="status">
        <div className="status-indicator">✓</div>
        <div className="status-content">
          <div className="status-title">Query Executed Successfully</div>
          <div className="status-subtext">
            Found {rowCount ?? 0} {rowCount === 1 ? 'record' : 'records'}.
          </div>
        </div>
      </div>
    );
  }

  if (status === 'unsupported') {
    return (
      <div className="status-banner status-unsupported" role="alert">
        <div className="status-indicator">⚠</div>
        <div className="status-content">
          <div className="status-title">Question Out of Scope</div>
          <div className="status-subtext">
            I can't answer that from the available data.
          </div>
          {rejectionReasons.length > 0 && (
            <ul className="reasons-list">
              {rejectionReasons.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    );
  }

  if (status === 'rejected') {
    return (
      <div className="status-banner status-rejected" role="alert">
        <div className="status-indicator">🛡</div>
        <div className="status-content">
          <div className="status-title">Query Rejected for Safety</div>
          <div className="status-subtext">
            The generated SQL statement violated system security or schema policies:
          </div>
          <ul className="reasons-list">
            {rejectionReasons.map((reason, idx) => (
              <li key={idx}>{reason}</li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="status-banner status-error" role="alert">
        <div className="status-indicator">✕</div>
        <div className="status-content">
          <div className="status-title">
            {errorCode ? `Request Failed: ${errorCode}` : 'Request Error'}
          </div>
          <div className="status-subtext">
            {errorMessage || 'An error occurred while communicating with the server.'}
          </div>
          {requestId && (
            <div className="request-id-tag">
              <span>Request ID:</span> <code>{requestId}</code>
            </div>
          )}
        </div>
      </div>
    );
  }

  return null;
}
