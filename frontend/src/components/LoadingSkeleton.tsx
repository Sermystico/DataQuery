export function LoadingSkeleton() {
  return (
    <div className="loading-card" role="status" aria-live="polite" aria-label="Executing query">
      <div className="loading-pipeline">
        <div className="pipeline-spinner-wrap">
          <div className="pipeline-spinner" aria-hidden="true" />
        </div>
        <div className="pipeline-text">
          <div className="pipeline-title">Processing Analytical Query</div>
          <div className="pipeline-steps">
            <span className="step-badge">1. Translating Question</span>
            <span className="step-arrow">→</span>
            <span className="step-badge">2. AST Policy Validation</span>
            <span className="step-arrow">→</span>
            <span className="step-badge">3. Read-Only Execution</span>
          </div>
        </div>
      </div>
      <div className="skeleton-body">
        <div className="skeleton-line skeleton-header" />
        <div className="skeleton-line skeleton-p1" />
        <div className="skeleton-line skeleton-p2" />
        <div className="skeleton-grid">
          <div className="skeleton-cell" />
          <div className="skeleton-cell" />
          <div className="skeleton-cell" />
        </div>
      </div>
    </div>
  );
}
