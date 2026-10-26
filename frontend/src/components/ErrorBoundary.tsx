import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an unhandled component error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary-card" role="alert">
          <h2>Something went wrong</h2>
          <p>
            An unexpected client error occurred while rendering the interface.
          </p>
          {this.state.error && (
            <pre className="error-message">{this.state.error.message}</pre>
          )}
          <button
            type="button"
            className="primary-btn"
            onClick={this.handleReset}
          >
            Reload Application
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
