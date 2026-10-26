import type { ExplanationSource } from '../types/api';

interface AnswerCardProps {
  answer: string | null;
  explanationSource: ExplanationSource;
}

export function AnswerCard({ answer, explanationSource }: AnswerCardProps) {
  if (!answer) {
    return null;
  }

  return (
    <section className="answer-card" aria-label="Natural language explanation">
      <div className="answer-header">
        <div className="answer-title-group">
          <span className="sparkle-icon" aria-hidden="true">✦</span>
          <h2 className="answer-title">Answer Summary</h2>
        </div>
        {explanationSource === 'fallback' && (
          <span
            className="fallback-badge"
            title="Explanation derived deterministically from analytical results."
          >
            Summary generated from fallback
          </span>
        )}
      </div>
      <p className="answer-body">{answer}</p>
    </section>
  );
}
