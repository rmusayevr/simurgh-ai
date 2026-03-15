import React, { lazy, Suspense, useEffect, useState, useCallback } from 'react';
import { ErrorBoundary } from './components/ErrorBoundary';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useLocation,
} from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Sidebar } from './components/layout/Sidebar';
import { MaintenanceBanner } from './components/layout/MaintenanceBanner';
import { publicApi } from './api/client';
import { Hammer, LogOut, Loader2 } from 'lucide-react';

// ─── Lazy-loaded pages (code splitting) ───────────────────────────────────────
const LandingPage = lazy(() => import('./pages/LandingPage').then(m => ({ default: m.LandingPage })));
const Login = lazy(() => import('./pages/Login').then(m => ({ default: m.Login })));
const Register = lazy(() => import('./pages/Register').then(m => ({ default: m.Register })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const ProjectDetails = lazy(() => import('./pages/ProjectDetails').then(m => ({ default: m.ProjectDetails })));
const SessionPage = lazy(() => import('./pages/SessionPage').then(m => ({ default: m.SessionPage })));

const ProposalDetailPage = lazy(() => import('./pages/ProposalDetailPage'));

const ProposalListPage = lazy(() => import('./pages/ProposalListPage').then(m => ({ default: m.ProposalListPage })));

const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const AdminPage = lazy(() => import('./pages/AdminPage').then(m => ({ default: m.AdminPage })));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword').then(m => ({ default: m.ForgotPassword })));
const TermsOfService = lazy(() => import('./pages/TermsOfService').then(m => ({ default: m.TermsOfService })));
const PrivacyPolicy = lazy(() => import('./pages/PrivacyPolicy').then(m => ({ default: m.PrivacyPolicy })));
const ResetPassword = lazy(() => import('./pages/ResetPassword').then(m => ({ default: m.ResetPassword })));
const VerifyEmail = lazy(() => import('./pages/VerifyEmail').then(m => ({ default: m.VerifyEmail })));
const EmailSent = lazy(() => import('./pages/EmailSent').then(m => ({ default: m.EmailSent })));
const ThesisAnalytics = lazy(() => import('./pages/ThesisAnalytics').then(m => ({ default: m.ThesisAnalytics })));
const ExperimentRegistration = lazy(() => import('./pages/ExperimentRegistration').then(m => ({ default: m.ExperimentRegistration })));
const ExperimentInterface = lazy(() => import('./components/evaluation/ExperimentInterface').then(m => ({ default: m.ExperimentInterface })));
const ParticipantLogin = lazy(() => import('./pages/ParticipantLogin').then(m => ({ default: m.ParticipantLogin })));

// ─── Shared loading fallback ──────────────────────────────────────────────────
const PageLoader = () => (
  <div className="h-screen w-screen flex items-center justify-center bg-slate-50">
    <Loader2 size={36} className="animate-spin text-indigo-600" />
  </div>
);

// ─── Route guards ─────────────────────────────────────────────────────────────
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <PageLoader />;
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
};

const AdminRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, user, loading } = useAuth();
  if (loading) return <PageLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!user?.is_superuser) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
};

// ─── Admin page wrapper ───────────────────────────────────────────────────────
const AdminPageWrapper = ({ defaultTab }: { defaultTab?: string }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  return (
    <AdminPage
      currentUser={user}
      onLogout={logout}
      onBackToApp={() => navigate('/dashboard')}
      defaultTab={defaultTab}
    />
  );
};


const SuperuserRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, user, loading } = useAuth();
  if (loading) return <PageLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!user?.is_superuser) return <Navigate to="/experiment" replace />;
  return <>{children}</>;
};

/** Bare layout for experiment participants: no sidebar, no nav, clean white shell. */
const ExperimentLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isMaintenance } = useMaintenanceStatus();
  const { user, logout } = useAuth();
  const isAdmin = user?.is_superuser || user?.role === 'ADMIN';
  if (isMaintenance && !isAdmin) {
    return <MaintenanceScreen onLogout={logout} />;
  }
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-4xl mx-auto px-4 py-10">
        {children}
      </div>
    </div>
  );
};

const ProtectedExperiment = ({ children }: { children: React.ReactNode }) => (
  <ProtectedRoute>
    <ExperimentLayout>
      <ErrorBoundary>
        {children}
      </ErrorBoundary>
    </ExperimentLayout>
  </ProtectedRoute>
);

const getActiveTab = (path: string): string => {
  if (path.startsWith('/settings')) return 'settings';
  if (path.startsWith('/project')) return 'history';
  return 'dashboard';
};

const TAB_ROUTES: Record<string, string> = {
  dashboard: '/dashboard',
  generator: '/dashboard',
  history: '/dashboard',
  settings: '/settings',
};

// ─── Maintenance screen ───────────────────────────────────────────────────────
const MaintenanceScreen = ({ onLogout }: { onLogout: () => void }) => (
  <div className="h-screen w-screen bg-slate-900 flex flex-col items-center justify-center p-6 text-center relative">
    <div className="absolute top-6 right-6">
      <button
        onClick={onLogout}
        className="flex items-center gap-2 text-slate-500 hover:text-white transition-colors text-sm font-bold px-4 py-2 rounded-lg hover:bg-slate-800"
      >
        <LogOut size={16} />
        Logout
      </button>
    </div>
    <div className="bg-amber-500/10 p-6 rounded-full mb-6">
      <Hammer size={64} className="text-amber-500 animate-bounce" />
    </div>
    <h1 className="text-3xl font-black text-white mb-2">Under Maintenance</h1>
    <p className="text-slate-400 max-w-md">
      We are currently fine-tuning the AI engines. The dashboard is temporarily
      locked for standard users. We'll be back shortly!
    </p>
  </div>
);

// ─── Custom hook: maintenance status ─────────────────────────────────────────
const useMaintenanceStatus = () => {
  const [isMaintenance, setIsMaintenance] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    publicApi
      .getSystemStatus()
      .then((res) => setIsMaintenance(res.data.maintenance_mode ?? false))
      .catch(() => setIsMaintenance(false))
      .finally(() => setLoading(false));
  }, []);

  return { isMaintenance, loading };
};

// ─── Custom hook: thesis/research mode ───────────────────────────────────────
const useThesisMode = () => {
  const [thesisMode, setThesisMode] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    publicApi
      .getSystemStatus()
      .then((res) => setThesisMode(res.data.thesis_mode ?? false))
      .catch(() => setThesisMode(false))
      .finally(() => setLoading(false));
  }, []);

  return { thesisMode, loading };
};

/** Renders children only when THESIS_MODE is enabled server-side.
 *  Otherwise redirects to /dashboard so research routes are invisible
 *  to public users. Superusers bypass the flag entirely. */
const ThesisModeRoute = ({ children }: { children: React.ReactNode }) => {
  const { thesisMode, loading } = useThesisMode();
  const { user, loading: authLoading } = useAuth();

  if (loading || authLoading) return <PageLoader />;

  // Superusers bypass the flag
  if (user?.is_superuser) return <>{children}</>;

  if (!thesisMode) return <Navigate to="/dashboard" replace />;

  return <>{children}</>;
};

// ─── Main layout (authenticated shell) ───────────────────────────────────────
const MainLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, logout, loading: authLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { isMaintenance, loading: statusLoading } = useMaintenanceStatus();

  const handleTabChange = useCallback(
    (tabId: string) => {
      navigate(TAB_ROUTES[tabId] ?? '/dashboard');
    },
    [navigate]
  );

  if (authLoading || statusLoading) {
    return <div className="h-screen w-screen bg-slate-50 animate-pulse" />;
  }

  const isAdmin = user?.is_superuser || user?.role === 'ADMIN';

  if (isMaintenance && !isAdmin) {
    return <MaintenanceScreen onLogout={logout} />;
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden relative">
      <MaintenanceBanner isActive={isMaintenance} />
      <div className="flex flex-1 overflow-hidden">
        <div className="bg-mesh" />
        <Sidebar
          activeTab={getActiveTab(location.pathname)}
          onTabChange={handleTabChange}
        />
        <main className="flex-1 flex flex-col relative z-10 h-full overflow-hidden">
          <div className="flex-1 overflow-y-auto bg-slate-50/80 p-6 md:p-8 scroll-smooth">
            <div className="max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500">
              {children}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

// ─── Route helpers ────────────────────────────────────────────────────────────
/** Wraps a page in ProtectedRoute + MainLayout + per-route ErrorBoundary.
 *  The ErrorBoundary is placed INSIDE MainLayout so the sidebar and nav
 *  remain functional if the page content crashes. */
const ProtectedLayout = ({ children }: { children: React.ReactNode }) => (
  <ProtectedRoute>
    <MainLayout>
      <ErrorBoundary>
        {children}
      </ErrorBoundary>
    </MainLayout>
  </ProtectedRoute>
);

// ─── App ──────────────────────────────────────────────────────────────────────
function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public routes */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route path="/email-sent" element={<EmailSent />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/terms" element={<TermsOfService />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
            <Route path="/reset-password" element={<ResetPassword />} />

            {/* Participant study entry point — only available when THESIS_MODE is on */}
            <Route path="/study" element={<ThesisModeRoute><ParticipantLogin /></ThesisModeRoute>} />

            {/* Admin route (own layout) */}
            <Route
              path="/admin"
              element={
                <AdminRoute>
                  <ErrorBoundary>
                    <AdminPageWrapper />
                  </ErrorBoundary>
                </AdminRoute>
              }
            />

            {/* Researcher tool: persona deviation coding (direct URL) */}
            <Route
              path="/admin/persona-verification"
              element={
                <AdminRoute>
                  <ErrorBoundary>
                    <AdminPageWrapper defaultTab="persona-coding" />
                  </ErrorBoundary>
                </AdminRoute>
              }
            />

            {/* Protected app routes */}
            <Route path="/dashboard" element={<ProtectedLayout><Dashboard /></ProtectedLayout>} />

            {/* ── Project routes with nested tab routing ── */}
            <Route
              path="/project/:id"
              element={<ProtectedLayout><ProjectDetails /></ProtectedLayout>}
            >
              {/* Default: redirect to context tab */}
              <Route index element={<Navigate to="context" replace />} />
              <Route path="context" element={null} />
              <Route path="stakeholders" element={null} />
              {/* Generator with its own sub-tabs */}
              <Route path="generator">
                <Route index element={<Navigate to="active" replace />} />
                <Route path="new" element={null} />
                <Route path="active" element={null} />
                <Route path="history" element={null} />
              </Route>
            </Route>

            {/* Mission workspace (DRAFT / PROCESSING states) */}
            <Route
              path="/project/:id/mission/:missionId"
              element={<ProtectedLayout><SessionPage /></ProtectedLayout>}
            />

            {/*
              Proposal detail (COMPLETED state) — shows 3-proposal comparison.
              Navigated to automatically when the poller detects COMPLETED.
            */}
            <Route
              path="/project/:id/proposal/:proposalId"
              element={<ProtectedLayout><ProposalDetailPage /></ProtectedLayout>}
            />

            {/* Legacy route: /proposals/:id → redirect to dashboard */}
            <Route
              path="/proposals/:proposalId"
              element={<Navigate to="/dashboard" replace />}
            />

            {/* Proposal list (legacy, kept for admin/history use) */}
            <Route
              path="/project/:id/proposals"
              element={<ProtectedLayout><ProposalListPage /></ProtectedLayout>}
            />

            <Route path="/settings" element={<ProtectedLayout><Settings /></ProtectedLayout>} />
            {/* Research routes — only mounted when THESIS_MODE=true on the server */}
            <Route path="/experiment/register"
              element={
                <ThesisModeRoute>
                  <ProtectedExperiment>
                    <ExperimentRegistration />
                  </ProtectedExperiment>
                </ThesisModeRoute>
              } />
            <Route
              path="/experiment"
              element={
                <ThesisModeRoute>
                  <ProtectedExperiment>
                    <ExperimentInterface />
                  </ProtectedExperiment>
                </ThesisModeRoute>
              }
            />
            <Route path="/thesis" element={<SuperuserRoute><MainLayout><ThesisAnalytics /></MainLayout></SuperuserRoute>} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;