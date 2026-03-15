import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, ArrowLeft, AlertCircle, Info } from 'lucide-react';
import { api } from '../api/client';
import { publicApi } from '../api/client';

export const ForgotPassword = () => {
    const navigate = useNavigate();
    const [email, setEmail] = useState('');
    const [status, setStatus] = useState<'idle' | 'loading'>('idle');
    const [error, setError] = useState('');
    const [emailEnabled, setEmailEnabled] = useState<boolean | null>(null);

    useEffect(() => {
        publicApi.getSystemStatus()
            .then(res => setEmailEnabled(res.data.email_enabled))
            .catch(() => setEmailEnabled(true));
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setStatus('loading');
        setError('');

        try {
            await api.post('/auth/password-recovery', { email: email });
            navigate(`/email-sent?mode=reset&email=${encodeURIComponent(email)}`);
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } } };
            const msg = error?.response?.data?.detail || "Something went wrong. Please try again.";
            setError(msg);
            setStatus('idle');
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-100 p-8 animate-in fade-in zoom-in-95 duration-300">
                <button
                    onClick={() => navigate('/login')}
                    className="flex items-center text-sm font-bold text-slate-400 hover:text-cyan-600 mb-8 transition-colors group"
                >
                    <ArrowLeft size={16} className="mr-2 group-hover:-translate-x-1 transition-transform" />
                    Back to Login
                </button>

                <h2 className="text-3xl font-black text-slate-900 mb-2 tracking-tight">Recover Access</h2>
                <p className="text-slate-500 mb-8 text-sm leading-relaxed">
                    Lost your keys? Enter your registered email and we'll send a secure link to reset your credentials.
                </p>

                {/* SMTP not configured — show friendly message instead of a confusing 503 */}
                {emailEnabled === false ? (
                    <div className="bg-blue-50 text-blue-700 p-4 rounded-xl text-sm flex items-start gap-3 border border-blue-100">
                        <Info size={16} className="mt-0.5 shrink-0" />
                        <div>
                            <p className="font-semibold mb-1">Password reset is unavailable</p>
                            <p>
                                This feature requires email to be configured on the server.
                                Please contact the administrator to reset your password manually.
                            </p>
                        </div>
                    </div>
                ) : (
                    <>
                        {error && (
                            <div className="bg-red-50 text-red-600 p-4 rounded-xl text-sm flex items-center gap-2 border border-red-100 mb-6 animate-in fade-in slide-in-from-top-1">
                                <AlertCircle size={16} />
                                <span>{error}</span>
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-6">
                            <div>
                                <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">
                                    Identity Verification
                                </label>
                                <div className="relative">
                                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300" size={18} />
                                    <input
                                        required
                                        type="email"
                                        placeholder="name@company.com"
                                        className="w-full pl-12 pr-4 py-4 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-2 focus:ring-cyan-500 focus:bg-white outline-none transition-all"
                                        value={email}
                                        onChange={e => setEmail(e.target.value)}
                                    />
                                </div>
                            </div>

                            <button
                                type="submit"
                                disabled={status === 'loading' || emailEnabled === null}
                                className="w-full bg-slate-900 text-white font-bold py-4 rounded-2xl hover:bg-cyan-600 transition-all shadow-lg shadow-slate-200 flex items-center justify-center gap-2 disabled:opacity-70"
                            >
                                {status === 'loading' ? (
                                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                ) : (
                                    'Send Recovery Link'
                                )}
                            </button>
                        </form>
                    </>
                )}
            </div>
        </div>
    );
};