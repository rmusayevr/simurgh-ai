import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { SimurghMark } from '../components/SimurghMark';
import { AlertCircle } from 'lucide-react';

const PROVIDER_LABELS: Record<string, string> = {
    github: 'GitHub',
    google: 'Google',
    atlassian: 'Atlassian',
};

/**
 * OAuthCallback — generic handler for all OAuth provider redirects.
 *
 * Mounted at /auth/:provider/callback
 * Reads ?code= and ?error= from the URL, POSTs to the matching backend
 * endpoint, stores the returned tokens, and navigates to the dashboard.
 */
export const OAuthCallback = () => {
    const navigate = useNavigate();
    const { provider } = useParams<{ provider: string }>();
    const [searchParams] = useSearchParams();
    const { loginWithOAuthTokens } = useAuth();
    const called = useRef(false);

    const code = searchParams.get('code');
    const error = searchParams.get('error');
    const providerLabel = PROVIDER_LABELS[provider ?? ''] ?? provider ?? 'OAuth';

    useEffect(() => {
        if (called.current) return;
        called.current = true;

        if (error || !code || !provider) {
            navigate('/login?oauth_error=1', { replace: true });
            return;
        }

        const finish = async () => {
            try {
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
            } catch {
                navigate('/login?oauth_error=1', { replace: true });
            }
        };

        finish();
    }, [code, error, provider, navigate, loginWithOAuthTokens]);

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
                        Completing sign-in with {providerLabel}…
                    </p>
                </div>
            )}
        </div>
    );
};