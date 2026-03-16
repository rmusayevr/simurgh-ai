import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams, useParams, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { SimurghMark } from '../components/SimurghMark';
import { AlertCircle } from 'lucide-react';

const PROVIDER_LABELS: Record<string, string> = {
    github: 'GitHub',
    google: 'Google',
    atlassian: 'Atlassian',
};

/**
 * OAuthCallback — handles both OAuth login redirects and the Atlassian
 * "connect" flow from Settings → Integrations.
 *
 * Login flow:  /auth/:provider/callback  — stores tokens, navigates to dashboard
 * Connect flow: /auth/atlassian/connect/callback — saves credential on current
 *               user, navigates back to Settings → Integrations tab
 */
export const OAuthCallback = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { provider } = useParams<{ provider: string }>();
    const [searchParams] = useSearchParams();
    const { loginWithOAuthTokens } = useAuth();
    const called = useRef(false);

    const code = searchParams.get('code');
    const error = searchParams.get('error');

    // Detect connect flow by path
    const isConnectFlow = location.pathname.includes('/connect/callback');
    const providerLabel = PROVIDER_LABELS[provider ?? 'atlassian'] ?? 'OAuth';

    useEffect(() => {
        if (called.current) return;
        called.current = true;

        if (error || !code) {
            navigate('/login?oauth_error=1', { replace: true });
            return;
        }

        const finish = async () => {
            try {
                if (isConnectFlow) {
                    // ── Connect flow: attach credential to current user ────────
                    await api.post('/auth/atlassian/connect/callback', {
                        code,
                        state: 'connect',
                    });
                    navigate('/settings?tab=integrations&connected=1', { replace: true });
                } else {
                    // ── Login flow: exchange for Simurgh tokens ───────────────
                    const res = await fetch(`/api/v1/auth/${provider}/callback`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ code, state: provider }),
                    });

                    if (!res.ok) {
                        const data = await res.json().catch(() => ({}));
                        throw new Error(data?.detail || 'Authentication failed.');
                    }

                    const { access_token, refresh_token } = await res.json();
                    await loginWithOAuthTokens(access_token, refresh_token);
                    navigate('/dashboard', { replace: true });
                }
            } catch (err: unknown) {
                const e = err as { response?: { data?: { detail?: string } }; message?: string };
                const detail = e?.response?.data?.detail || e?.message || 'unknown error';
                if (isConnectFlow) {
                    navigate(`/settings?tab=integrations&error=1&msg=${encodeURIComponent(detail)}`, { replace: true });
                } else {
                    navigate('/login?oauth_error=1', { replace: true });
                }
            }
        };

        finish();
    }, [code, error, provider, navigate, loginWithOAuthTokens, isConnectFlow]);

    return (
        <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-6">
            <div className="inline-flex items-center gap-2.5">
                <SimurghMark size={36} />
                <span className="font-black text-xl tracking-tight text-slate-900">
                    Simurgh <span className="text-cyan-600">AI</span>
                </span>
            </div>

            {error ? (
                <div className="flex items-center gap-2 text-red-600 bg-red-50 border border-red-100 px-5 py-3 rounded-xl text-sm font-medium">
                    <AlertCircle size={16} />
                    {providerLabel} authentication was cancelled.
                </div>
            ) : (
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-slate-200 border-t-cyan-600 rounded-full animate-spin" />
                    <p className="text-slate-500 text-sm font-medium">
                        {isConnectFlow
                            ? `Connecting your ${providerLabel} account…`
                            : `Completing sign-in with ${providerLabel}…`}
                    </p>
                </div>
            )}
        </div>
    );
};