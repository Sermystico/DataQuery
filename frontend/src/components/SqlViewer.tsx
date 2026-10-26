import { useState } from 'react';

interface SqlViewerProps {
  sql: string | null;
}

export function SqlViewer({ sql }: SqlViewerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!sql) {
    return null;
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy SQL:', err);
    }
  };

  return (
    <div className="sql-viewer-card">
      <div className="sql-viewer-header">
        <button
          type="button"
          className="toggle-sql-btn"
          onClick={() => setIsOpen(!isOpen)}
          aria-expanded={isOpen}
          aria-controls="generated-sql-block"
        >
          <span className="toggle-icon" aria-hidden="true">
            {isOpen ? '▼' : '▶'}
          </span>
          <span>{isOpen ? 'Hide generated SQL' : 'Show generated SQL'}</span>
        </button>

        {isOpen && (
          <button
            type="button"
            className="copy-sql-btn"
            onClick={handleCopy}
            aria-label="Copy generated SQL to clipboard"
          >
            {copied ? '✓ Copied!' : 'Copy SQL'}
          </button>
        )}
      </div>

      {isOpen && (
        <div id="generated-sql-block" className="sql-code-wrapper">
          <pre className="sql-code">
            <code>{sql}</code>
          </pre>
        </div>
      )}
    </div>
  );
}
