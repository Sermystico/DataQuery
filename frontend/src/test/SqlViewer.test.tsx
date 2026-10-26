import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SqlViewer } from '../components/SqlViewer';

describe('SqlViewer', () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it('renders nothing when sql is null', () => {
    const { container } = render(<SqlViewer sql={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('toggles SQL code visibility on button click', () => {
    const sql = 'SELECT * FROM customers WHERE region = "EMEA";';
    render(<SqlViewer sql={sql} />);

    const toggleBtn = screen.getByRole('button', {
      name: /Show generated SQL/i,
    });
    expect(toggleBtn).toBeInTheDocument();
    expect(screen.queryByText(sql)).not.toBeInTheDocument();

    // Open
    fireEvent.click(toggleBtn);
    expect(screen.getByText(sql)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Hide generated SQL/i })
    ).toBeInTheDocument();

    // Close
    fireEvent.click(screen.getByRole('button', { name: /Hide generated SQL/i }));
    expect(screen.queryByText(sql)).not.toBeInTheDocument();
  });

  it('copies SQL to clipboard when copy button is clicked', async () => {
    const sql = 'SELECT COUNT(*) FROM orders;';
    render(<SqlViewer sql={sql} />);

    // Open viewer
    fireEvent.click(screen.getByRole('button', { name: /Show generated SQL/i }));

    const copyBtn = screen.getByRole('button', {
      name: /Copy generated SQL to clipboard/i,
    });
    fireEvent.click(copyBtn);

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(sql);
    expect(await screen.findByText(/✓ Copied!/i)).toBeInTheDocument();
  });
});
