import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Mail, Inbox, RefreshCw, Loader2 } from 'lucide-react';
import { api } from '../api/client';

export const EmailSent = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const mode = searchParams.get('mode');
    const email = searchParams.get('email') || "";

    const [cooldown, setCooldown] = useState(0);
    const [isResending, setIsResending] = useState(false);

    useEffect(() => {
        if (cooldown > 0) {
            const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
            return () => clearTimeout(timer);
        }
    }, [cooldown]);

    const handleResend = async () => {
        if (cooldown > 0 || !email) return;

        setIsResending(true);
        try {
            await api.post('/auth/resend-verification', { email });
            setCooldown(60);
        } catch (err) {
            console.error("Resend failed", err);
        } finally {
            setIsResending(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
            <div className="max-w-md w-full bg-white rounded-3xl shadow-xl border border-slate-100 overflow-hidden">

                <div className="bg-cyan-600 p-12 flex justify-center relative">
                    <div className="relative z-10 bg-white p-4 rounded-2xl shadow-2xl">
                        <Mail size={40} className="text-cyan-600" />
                    </div>
                </div>

                <div className="p-10 text-center">
                    <h2 className="text-3xl font-black text-slate-900 mb-4 tracking-tight">
                        {mode === 'reset' ? 'Reset Link Sent' : 'Check your inbox'}
                    </h2>
                    <p className="text-slate-500 leading-relaxed mb-8">
                        {mode === 'reset'
                            ? `We've sent a secure password reset link to `
                            : `We've sent an activation link to `
                        }
                        <span className="font-bold text-slate-700">{email || "your email"}</span>.
                    </p>

                    <div className="space-y-3">
                        <button
                            onClick={() => window.open('https://mail.google.com', '_blank')}
                            className="w-full bg-slate-900 text-white font-bold py-4 rounded-xl hover:bg-slate-800 transition-all flex items-center justify-center gap-2 shadow-lg"
                        >
                            <Inbox size={18} /> Open Gmail
                        </button>

                        {/* RESEND BUTTON */}
                        <button
                            onClick={handleResend}
                            disabled={cooldown > 0 || isResending}
                            className="w-full bg-white text-slate-600 font-bold py-4 rounded-xl border border-slate-200 hover:bg-slate-50 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                        >
                            {isResending ? (
                                <Loader2 className="animate-spin" size={18} />
                            ) : (
                                <RefreshCw size={18} className={cooldown > 0 ? 'animate-spin-slow' : ''} />
                            )}
                            {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend Activation Email"}
                        </button>
                    </div>

                    <button
                        onClick={() => navigate('/login')}
                        className="mt-6 text-sm font-bold text-cyan-600 hover:text-cyan-800 transition-colors"
                    >
                        Back to Login
                    </button>
                </div>
            </div>
        </div>
    );
};