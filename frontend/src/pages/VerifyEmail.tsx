import { useEffect, useState, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { api } from '../api/client';

export const VerifyEmail = () => {
    const [searchParams] = useSearchParams();
    const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
    const navigate = useNavigate();
    const token = searchParams.get('token');

    // Add a ref to track if we've already fired the request
    const hasFetched = useRef(false);

    useEffect(() => {
        // If no token or we already fetched, bail out immediately
        if (!token || hasFetched.current) return;

        // Lock it so it can't fire again
        hasFetched.current = true;

        const verify = async () => {
            try {
                await api.post('/auth/verify-email', { token });
                setStatus('success');
                setTimeout(() => navigate('/login'), 3000);
            } catch (error) {
                console.error("Verification failed:", error);
                setStatus('error');
            }
        };

        verify();
    }, [token, navigate]); // Added navigate to dependency array for good measure

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6 text-center">
            <div className="max-w-md w-full bg-white p-8 rounded-2xl border border-slate-200 shadow-xl">
                {status === 'loading' && (
                    <div className="flex flex-col items-center gap-4">
                        <Loader2 className="animate-spin text-cyan-600" size={40} />
                        <h2 className="font-bold text-slate-800">Verifying your account...</h2>
                    </div>
                )}
                {status === 'success' && (
                    <div className="flex flex-col items-center gap-4">
                        <CheckCircle className="text-emerald-500" size={60} />
                        <h2 className="text-2xl font-black text-slate-900">Account Activated!</h2>
                        <p className="text-slate-500">Welcome to Simurgh AI. Redirecting to login...</p>
                    </div>
                )}
                {status === 'error' && (
                    <div className="flex flex-col items-center gap-4">
                        <XCircle className="text-red-500" size={60} />
                        <h2 className="text-2xl font-black text-slate-900">Link Expired</h2>
                        <p className="text-slate-500">The verification link is invalid or has already been used.</p>
                        <button onClick={() => navigate('/login')} className="mt-4 text-cyan-600 font-bold hover:underline">
                            Back to Login
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};