import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LogIn, Mail, Lock, AlertCircle, CheckCircle } from 'lucide-react';
import { SimurghMark } from '../components/SimurghMark';

export const Login = () => {
    const navigate = useNavigate();
    const { login } = useAuth();
    const [searchParams] = useSearchParams();
    const [formData, setFormData] = useState({ email: '', password: '' });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const registered = searchParams.get('registered') === '1';
    const oauthError = searchParams.get('oauth_error') === '1';

    const handleGitHubLogin = () => {
        // Redirect to backend which bounces to GitHub
        window.location.href = '/api/v1/auth/github';
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            await login(formData.email, formData.password);
            navigate('/dashboard');
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } } };
            const msg = error?.response?.data?.detail || 'Invalid email or password.';
            setError(typeof msg === 'string' ? msg : 'Authentication failed.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
            <div className="w-full max-w-md animate-in fade-in zoom-in-95 duration-300">

                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center gap-2.5">
                        <SimurghMark size={36} />
                        <span className="font-black text-xl tracking-tight text-slate-900">
                            Simurgh <span className="text-cyan-600">AI</span>
                        </span>
                    </div>
                </div>

                <div className="bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden">
                    <div className="bg-slate-900 px-8 py-7">
                        <h1 className="text-2xl font-black text-white mb-1">Welcome back</h1>
                        <p className="text-slate-400 text-sm">Sign in to your workspace</p>
                    </div>

                    <form onSubmit={handleSubmit} className="px-8 py-6 space-y-4">
                        {/* GitHub OAuth */}
                        <button
                            type="button"
                            onClick={handleGitHubLogin}
                            className="w-full flex items-center justify-center gap-3 bg-slate-900 hover:bg-black text-white font-bold py-3 rounded-xl transition-all"
                        >
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
                            </svg>
                            Continue with GitHub
                        </button>

                        <div className="flex items-center gap-3">
                            <div className="flex-1 h-px bg-slate-200" />
                            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">or</span>
                            <div className="flex-1 h-px bg-slate-200" />
                        </div>

                        {registered && (
                            <div className="bg-emerald-50 text-emerald-700 p-3 rounded-xl text-sm flex items-center gap-2 border border-emerald-100">
                                <CheckCircle size={16} /> Account created — you can log in now.
                            </div>
                        )}
                        {oauthError && (
                            <div className="bg-red-50 text-red-600 p-3 rounded-xl text-sm flex items-center gap-2 border border-red-100">
                                <AlertCircle size={16} /> GitHub sign-in failed. Please try again or use email.
                            </div>
                        )}
                        {error && (
                            <div className="bg-red-50 text-red-600 p-3 rounded-xl text-sm flex items-center gap-2 border border-red-100">
                                <AlertCircle size={16} /> {error}
                            </div>
                        )}

                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Email Address</label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                                <input
                                    required type="email" placeholder="name@company.com"
                                    className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 focus:bg-white outline-none transition-all"
                                    value={formData.email}
                                    onChange={e => setFormData({ ...formData, email: e.target.value })}
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Password</label>
                            <div className="relative">
                                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                                <input
                                    required type="password" placeholder="••••••••"
                                    className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 focus:bg-white outline-none transition-all"
                                    value={formData.password}
                                    onChange={e => setFormData({ ...formData, password: e.target.value })}
                                />
                            </div>
                        </div>

                        <div className="pt-1 text-right">
                            <button type="button" onClick={() => navigate('/forgot-password')}
                                className="text-xs font-bold text-cyan-600 hover:text-cyan-800 transition-colors">
                                Forgot password?
                            </button>
                        </div>

                        <button type="submit" disabled={loading}
                            className="w-full bg-cyan-600 text-white font-bold py-3 rounded-xl hover:bg-cyan-700 transition-all flex items-center justify-center gap-2 shadow-lg shadow-cyan-200 disabled:opacity-60">
                            {loading
                                ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                : <><LogIn size={18} /> Sign In</>
                            }
                        </button>
                    </form>

                    <div className="bg-slate-50 px-8 py-4 border-t border-slate-100 text-center">
                        <p className="text-sm text-slate-600">
                            Don't have an account?{' '}
                            <button onClick={() => navigate('/register')}
                                className="font-bold text-cyan-600 hover:text-cyan-800 transition-colors">
                                Create one
                            </button>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};