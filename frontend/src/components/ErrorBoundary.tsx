/**
 * Reusable React Error Boundary.
 *
 * Catches render-phase errors that bubble up from any descendant component
 * and replaces the broken subtree with a contained error UI rather than
 * unmounting the entire application.
 *
 * Why a class component?
 *   Error boundaries can only be implemented as class components in React —
 *   the required lifecycle methods (getDerivedStateFromError, componentDidCatch)
 *   have no hooks equivalent.  This is the single exception to "use function
 *   components everywhere" in this codebase.
 *
 * Usage — two patterns:
 *
 *   1. Route-level (one per lazy page, keeps other pages functional):
 *      <ErrorBoundary>
 *        <Suspense fallback={<PageLoader />}>
 *          <SomePage />
 *        </Suspense>
 *      </ErrorBoundary>
 *
 *   2. Component-level (isolates a single risky widget):
 *      <ErrorBoundary fallback={<p>Diagram unavailable</p>}>
 *        <MermaidDiagram chart={rawAiOutput} />
 *      </ErrorBoundary>
 *
 * The optional `onError` prop lets callers plug in an error reporting service
 * (Sentry, LogRocket, etc.) without coupling this component to any SDK.
 *
 * The optional `resetKeys` prop mirrors the react-error-boundary pattern:
 * when any value in the array changes the boundary automatically resets,
 * which is useful for data-driven components like <MermaidDiagram chart={...}>
 * where a new prop value should trigger a fresh render attempt.
 */

import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Props {
    children: React.ReactNode;
    /** Custom fallback UI.  Receives the error and a reset callback. */
    fallback?: (error: Error, reset: () => void) => React.ReactNode;
    /** Called after componentDidCatch — plug in Sentry / LogRocket here. */
    onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
    /**
     * When any value in this array changes the boundary resets automatically.
     * Mirrors the API from the popular `react-error-boundary` library.
     */
    resetKeys?: unknown[];
}

interface State {
    hasError: boolean;
    error: Error | null;
}

// ─── Default fallback UI ──────────────────────────────────────────────────────
// eslint-disable-next-line react-refresh/only-export-components
function DefaultFallback({ error, onReset }: { error: Error; onReset: () => void }) {
    return (
        <div
            role="alert"
            className="flex flex-col items-center justify-center gap-4 p-10 text-center
                       rounded-2xl bg-red-50 border border-red-100 text-slate-700"
        >
            <AlertTriangle size={40} className="text-red-400 shrink-0" />
            <div>
                <p className="font-bold text-lg text-slate-800 mb-1">Something went wrong</p>
                <p className="text-sm text-slate-500 max-w-sm">
                    This section encountered an unexpected error and could not render.
                </p>
                {/* Show the error message in development for faster debugging */}
                {import.meta.env.DEV && (
                    <pre className="mt-3 text-left text-xs text-red-600 bg-red-100
                                    rounded-lg p-3 overflow-auto max-w-md">
                        {error.message}
                    </pre>
                )}
            </div>
            <button
                onClick={onReset}
                className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200
                           rounded-xl text-sm font-bold text-slate-700 hover:bg-slate-50
                           transition-colors shadow-sm"
            >
                <RefreshCw size={15} />
                Try again
            </button>
        </div>
    );
}

// ─── Error Boundary ───────────────────────────────────────────────────────────

export class ErrorBoundary extends React.Component<Props, State> {
    static defaultProps = { resetKeys: [] };

    state: State = { hasError: false, error: null };

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
        // Always log to the console so developers see the stack in DevTools.
        console.error('[ErrorBoundary] Caught error:', error, errorInfo);
        // Forward to any external error reporter the caller provided.
        this.props.onError?.(error, errorInfo);
    }

    componentDidUpdate(prevProps: Props): void {
        // Reset automatically when any resetKey changes — allows the boundary
        // to recover when its data source changes (e.g. a new AI-generated chart).
        const { resetKeys = [] } = this.props;
        const { resetKeys: prevResetKeys = [] } = prevProps;

        if (
            this.state.hasError &&
            resetKeys.some((key, i) => key !== prevResetKeys[i])
        ) {
            this.reset();
        }
    }

    reset = (): void => {
        this.setState({ hasError: false, error: null });
    };

    render(): React.ReactNode {
        const { hasError, error } = this.state;
        const { children, fallback } = this.props;

        if (hasError && error) {
            if (fallback) return fallback(error, this.reset);
            return <DefaultFallback error={error} onReset={this.reset} />;
        }

        return children;
    }
}