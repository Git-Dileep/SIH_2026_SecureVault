import { Component, type ReactNode } from 'react';
import { ShieldAlert } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="flex flex-col items-center justify-center p-12 text-center border rounded-lg h-[400px]" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg-surface)' }}>
          <div className="w-16 h-16 rounded-full flex items-center justify-center mb-6" style={{ background: 'var(--color-danger-muted)', color: 'var(--color-danger)' }}>
            <ShieldAlert size={32} />
          </div>
          <h2 className="text-[18px] font-semibold mb-2">Something went wrong</h2>
          <p className="text-[13px] text-muted mb-6 max-w-md">
            The application encountered an unexpected error. Please refresh the page or return to the dashboard.
          </p>
          <div className="flex gap-4">
            <button className="btn btn-primary" onClick={() => window.location.href = '/'}>
              Return to Dashboard
            </button>
            <button className="btn btn-secondary" onClick={() => window.location.reload()}>
              Refresh Page
            </button>
          </div>
          {this.state.error && (
            <div className="mt-8 p-4 bg-bg-primary border rounded text-left w-full max-w-2xl overflow-auto text-[11px] mono text-muted" style={{ borderColor: 'var(--color-border)' }}>
              {this.state.error.message}
            </div>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}
