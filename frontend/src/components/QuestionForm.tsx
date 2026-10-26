import { type ChangeEvent, type FormEvent, type KeyboardEvent, useState } from 'react';

interface QuestionFormProps {
  initialValue?: string;
  loading: boolean;
  onSubmit: (question: string) => void;
}

export function QuestionForm({ initialValue = '', loading, onSubmit }: QuestionFormProps) {
  const [question, setQuestion] = useState(initialValue);
  const [prevInitial, setPrevInitial] = useState(initialValue);
  const [touched, setTouched] = useState(false);

  if (initialValue !== prevInitial) {
    setPrevInitial(initialValue);
    setQuestion(initialValue);
  }

  const trimmed = question.trim();
  const isTooShort = touched && trimmed.length > 0 && trimmed.length < 3;
  const isTooLong = question.length > 500;
  const isValid = trimmed.length >= 3 && question.length <= 500;

  const handleSubmit = (e?: FormEvent) => {
    if (e) {
      e.preventDefault();
    }
    setTouched(true);
    if (!isValid || loading) {
      return;
    }
    onSubmit(trimmed);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setQuestion(e.target.value);
    if (!touched) {
      setTouched(true);
    }
  };

  return (
    <form className="question-form" onSubmit={handleSubmit} noValidate>
      <div className="input-wrapper">
        <label htmlFor="question-input" className="sr-only">
          Natural Language Analytics Question
        </label>
        <textarea
          id="question-input"
          name="question"
          className={`question-textarea ${isTooShort || isTooLong ? 'input-error' : ''}`}
          rows={3}
          placeholder="Ask any question about orders, revenue, products, or customers... (Press Enter to send)"
          value={question}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={loading}
          maxLength={520}
          aria-invalid={isTooShort || isTooLong}
          aria-describedby="char-counter error-hint"
        />
        <div className="input-footer">
          <div className="validation-hint" id="error-hint" role="status">
            {isTooShort && (
              <span className="error-text">Question must be at least 3 characters.</span>
            )}
            {isTooLong && (
              <span className="error-text">Question cannot exceed 500 characters.</span>
            )}
          </div>
          <div className="char-counter" id="char-counter" aria-live="polite">
            <span className={question.length > 500 ? 'counter-overflow' : ''}>
              {question.length}
            </span>
            /500
          </div>
        </div>
      </div>
      <div className="form-actions">
        <button
          type="submit"
          className="submit-btn"
          disabled={!isValid || loading}
          aria-busy={loading}
        >
          {loading ? (
            <span className="btn-loading">
              <span className="spinner" aria-hidden="true" />
              <span>Analyzing...</span>
            </span>
          ) : (
            <span>Run Query</span>
          )}
        </button>
      </div>
    </form>
  );
}
