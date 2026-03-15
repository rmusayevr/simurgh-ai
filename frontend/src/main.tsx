import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'

// ─── Top-level error boundary ─────────────────────────────────────────────────
// Catches any render error that escapes all per-route boundaries below.
// Without this, an uncaught render error produces a blank white screen.
// With it, the user sees a recoverable "Something went wrong" screen.

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)