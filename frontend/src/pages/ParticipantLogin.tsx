/**
 * ParticipantLogin.tsx
 *
 * A clean, focused login screen shown to study participants.
 * No sidebar, no nav, no links to the rest of the app.
 * After login, redirects straight to /experiment.
 *
 * Researchers send participants the direct URL: /study
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, AlertCircle, FlaskConical, Lock, Mail, ChevronRight, Clock, Shield, Users } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export function ParticipantLogin() {
    const { login, isAuthenticated, loading: authLoading } = useAuth();
    const navigate = useNavigate();

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Redirect inside useEffect — never during render
    useEffect(() => {
        if (!authLoading && isAuthenticated) {
            navigate('/experiment', { replace: true });
        }
    }, [isAuthenticated, authLoading, navigate]);

    // Don't flash the form while auth is still restoring from localStorage
    if (authLoading) return null;

    const handleLogin = async () => {
        if (!email.trim() || !password.trim()) {
            setError('Please enter your credentials.');
            return;
        }
        setLoading(true);
        setError('');
        try {
            await login(email.trim(), password);
            // Navigation handled by the useEffect above once isAuthenticated flips
        } catch {
            setError('Invalid credentials. Please check the email and password sent to you by the researcher.');
        } finally {
            setLoading(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') handleLogin();
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-cyan-950 to-slate-900 flex flex-col items-center justify-center px-4 py-16">

            {/* Brand mark */}
            <div className="flex items-center gap-3 mb-10">
                <div className="w-10 h-10 bg-gradient-to-br from-cyan-500 to-violet-600 rounded-xl flex items-center justify-center shadow-lg shadow-cyan-500/30">
                    <FlaskConical size={20} className="text-white" />
                </div>
                <div>
                    <p className="text-white font-black text-lg leading-none">MSc Research Study</p>
                    <p className="text-cyan-400 text-xs font-medium">AI-Assisted Architecture Decision Making</p>
                </div>
            </div>

            <div className="w-full max-w-md space-y-5">

                {/* Hero card */}
                <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-3xl p-8 text-center">
                    <h1 className="text-2xl font-black text-white mb-2">
                        Welcome, Participant
                    </h1>
                    <p className="text-slate-400 text-sm leading-relaxed">
                        Sign in with the credentials provided in your invitation email to begin the study session.
                    </p>

                    {/* Study stats */}
                    <div className="grid grid-cols-3 gap-3 mt-6">
                        {[
                            { icon: Clock, label: '15–25 min', sub: 'Est. duration' },
                            { icon: Shield, label: 'Anonymous', sub: 'Your data' },
                            { icon: Users, label: '2 conditions', sub: 'Per session' },
                        ].map(({ icon: Icon, label, sub }) => (
                            <div key={sub} className="bg-white/5 rounded-xl p-3 border border-white/5">
                                <Icon size={16} className="text-cyan-400 mx-auto mb-1" />
                                <p className="text-white text-xs font-bold">{label}</p>
                                <p className="text-slate-500 text-[10px]">{sub}</p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Login form */}
                <div className="bg-white rounded-2xl shadow-2xl shadow-black/40 p-8 space-y-5">
                    <h2 className="text-lg font-black text-slate-900">Sign in to continue</h2>

                    {/* Email */}
                    <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">
                            Email
                        </label>
                        <div className="relative">
                            <Mail size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                            <input
                                type="email"
                                value={email}
                                onChange={e => setEmail(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="p01@study.local"
                                autoComplete="email"
                                className="w-full pl-10 pr-4 py-3 rounded-xl border border-slate-200 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all placeholder:text-slate-300"
                            />
                        </div>
                    </div>

                    {/* Password */}
                    <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">
                            Password
                        </label>
                        <div className="relative">
                            <Lock size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                            <input
                                type="password"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="••••••••"
                                autoComplete="current-password"
                                className="w-full pl-10 pr-4 py-3 rounded-xl border border-slate-200 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all placeholder:text-slate-300"
                            />
                        </div>
                    </div>

                    {/* Error */}
                    {error && (
                        <div className="flex items-start gap-2.5 bg-red-50 border border-red-100 text-red-700 rounded-xl px-4 py-3">
                            <AlertCircle size={15} className="shrink-0 mt-0.5" />
                            <p className="text-sm leading-snug">{error}</p>
                        </div>
                    )}

                    {/* Submit */}
                    <button
                        onClick={handleLogin}
                        disabled={loading}
                        className="w-full py-3.5 bg-cyan-600 hover:bg-cyan-700 disabled:bg-cyan-400 text-white rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0"
                    >
                        {loading
                            ? <><Loader2 size={16} className="animate-spin" /> Signing in…</>
                            : <>Begin Study Session <ChevronRight size={16} /></>}
                    </button>
                </div>

                {/* Footer note */}
                <p className="text-center text-slate-500 text-xs leading-relaxed">
                    Having trouble signing in? Contact the researcher directly.<br />
                    Do not share your credentials with others.
                </p>
            </div>
        </div>
    );
}