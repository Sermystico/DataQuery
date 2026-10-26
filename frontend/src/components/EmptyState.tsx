interface EmptyStateProps {
  type: 'initial' | 'zero_rows';
  question?: string;
}

export function EmptyState({ type, question }: EmptyStateProps) {
  if (type === 'zero_rows') {
    return (
      <div className="empty-state zero-rows-state" role="status">
        <div className="empty-icon" aria-hidden="true">
          🔍
        </div>
        <h3 className="empty-title">No matching records found</h3>
        <p className="empty-description">
          The query executed successfully against the analytical database, but returned 0 rows
          {question ? ` for "${question}"` : ''}.
        </p>
        <p className="empty-hint">
          Tip: Try widening your date filters, verifying categorical values, or asking a more general question.
        </p>
      </div>
    );
  }

  return (
    <div className="empty-state initial-state" role="region" aria-label="Welcome Guide">
      <div className="empty-icon" aria-hidden="true">
        📊
      </div>
      <h2 className="empty-title">AI-Powered Analytics Assistant</h2>
      <p className="empty-description">
        Ask natural language business questions about e-commerce customers, orders, inventory,
        and revenue. DataQuery translates your intent into secure read-only SQL, provides visual charts,
        and synthesizes plain-English summaries.
      </p>
      <div className="features-preview">
        <div className="feature-item">
          <span className="feature-icon">🛡</span>
          <span className="feature-text">Guaranteed Read-Only SQL with AST Validation</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">📈</span>
          <span className="feature-text">Automated Chart Visualization Hints</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">💬</span>
          <span className="feature-text">Hallucination-Proof Data Explanations</span>
        </div>
      </div>
    </div>
  );
}
