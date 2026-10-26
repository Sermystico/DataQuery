import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { QuestionForm } from '../components/QuestionForm';

describe('QuestionForm', () => {
  it('disables submit button and shows error when question is less than 3 characters', () => {
    const handleSubmit = vi.fn();
    render(<QuestionForm loading={false} onSubmit={handleSubmit} />);

    const textarea = screen.getByRole('textbox', {
      name: /Natural Language Analytics Question/i,
    });
    const submitBtn = screen.getByRole('button', { name: /Run Query/i });

    // Initially empty -> disabled
    expect(submitBtn).toBeDisabled();

    // Type 2 characters -> validation error
    fireEvent.change(textarea, { target: { value: 'ab' } });
    expect(submitBtn).toBeDisabled();
    expect(
      screen.getByText(/Question must be at least 3 characters/i)
    ).toBeInTheDocument();

    // Submit attempt fails
    fireEvent.click(submitBtn);
    expect(handleSubmit).not.toHaveBeenCalled();
  });

  it('enables submit button and calls onSubmit when valid question is typed and clicked', () => {
    const handleSubmit = vi.fn();
    render(<QuestionForm loading={false} onSubmit={handleSubmit} />);

    const textarea = screen.getByRole('textbox');
    const submitBtn = screen.getByRole('button', { name: /Run Query/i });

    fireEvent.change(textarea, { target: { value: 'Total revenue by region?' } });
    expect(submitBtn).not.toBeDisabled();

    fireEvent.click(submitBtn);
    expect(handleSubmit).toHaveBeenCalledWith('Total revenue by region?');
  });

  it('submits on Enter key press but allows Shift+Enter for newlines', () => {
    const handleSubmit = vi.fn();
    render(<QuestionForm loading={false} onSubmit={handleSubmit} />);

    const textarea = screen.getByRole('textbox');

    fireEvent.change(textarea, { target: { value: 'Valid question here' } });

    // Shift + Enter should NOT submit
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    expect(handleSubmit).not.toHaveBeenCalled();

    // Enter alone should submit
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(handleSubmit).toHaveBeenCalledWith('Valid question here');
  });

  it('disables textarea and submit button when loading', () => {
    render(<QuestionForm loading={true} onSubmit={vi.fn()} />);

    const textarea = screen.getByRole('textbox');
    const submitBtn = screen.getByRole('button');

    expect(textarea).toBeDisabled();
    expect(submitBtn).toBeDisabled();
    expect(screen.getByText(/Analyzing.../i)).toBeInTheDocument();
  });

  it('updates character counter accurately', () => {
    render(<QuestionForm loading={false} onSubmit={vi.fn()} />);

    const textarea = screen.getByRole('textbox');
    expect(screen.getByText('0')).toBeInTheDocument();

    fireEvent.change(textarea, { target: { value: 'Hello world' } });
    expect(screen.getByText('11')).toBeInTheDocument();
  });
});
