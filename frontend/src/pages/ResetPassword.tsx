import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Lock, AlertCircle, CheckCircle2, ArrowRight, ShieldCheck } from 'lucide-react';
import { api } from '../api/client';

export const ResetPassword = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const token = searchParams.get('token');

    const [password, setPassword] = useState('');
    const [confirm, setConfirm] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);

    // Reusing your strength logic for consistency
    const getPasswordStrength = (pass: string) => {
        let score = 0;
        if (pass.length >= 8) score++;
        if (/[A-Z]/.test(pass)) score++;
        if (/[0-9]/.test(pass)) score++;
        if (/[!@#$%^&*(),.?":{}|<>]/.test(pass)) score++;
        return score;
    };

    const strength = getPasswordStrength(password);

    if (!token) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
                <div className="bg-white p-8 rounded-3xl shadow-xl border border-slate-100 max-w-md text-center">
                    <div className="w-12 h-12 bg-red-100 text-red-600 rounded-full flex items-center justify-center mx-auto mb-4">
                        <AlertCircle size={24} />
                    </div>
                    <h3 className="font-bold text-slate-900 mb-2">Invalid Link</h3>
                    <p className="text-sm text-slate-500 mb-6 leading-relaxed">
                        This password reset link is invalid or has expired. For security reasons, recovery links are only valid for 24 hours.
                    </p>
                    <button
                        onClick={() => navigate('/forgot-password')}
                        className="w-full bg-slate-900 text-white font-bold py-3 rounded-xl hover:bg-slate-800 transition-all"
                    >
                        Request New Link
                    </button>
                </div>
            </div>
        );
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (password !== confirm) {
            setError("Passwords do not match");
            return;
        }
        if (strength < 4) {
            setError("Password is too weak. Please follow the complexity requirements.");
            return;
        }

        setLoading(true);
        setError('');

        try {
            await api.post('/auth/reset-password', {
                token: token,
                new_password: password,
                confirm_new_password: confirm
            });
            setSuccess(true);
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } } };
            setError(error?.response?.data?.detail || "Failed to reset password. Link may be expired.");
            setLoading(false);
        }
    };

    if (success) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
                <div className="w-full max-w-md bg-white rounded-3xl shadow-xl border border-slate-100 p-10 text-center animate-in zoom-in-95 duration-300">
                    <div className="w-20 h-20 bg-emerald-100 text-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-inner rotate-3">
                        <CheckCircle2 size={40} />
                    </div>
                    <h2 className="text-3xl font-black text-slate-900 mb-3 tracking-tight">Access Restored</h2>
                    <p className="text-slate-500 mb-8 leading-relaxed">
                        Your credentials have been updated. You can now return to Simurgh AI and continue your work.
                    </p>
                    <button
                        onClick={() => navigate('/login')}
                        className="w-full bg-cyan-600 text-white font-bold py-4 rounded-xl hover:bg-cyan-700 transition-all flex items-center justify-center gap-2 shadow-lg shadow-cyan-200"
                    >
                        Sign In Now <ArrowRight size={18} />
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-white rounded-3xl shadow-xl border border-slate-100 p-8">
                <div className="text-center mb-8">
                    <div className="inline-flex p-3 rounded-2xl bg-cyan-50 text-cyan-600 mb-4">
                        <Lock size={28} />
                    </div>
                    <h2 className="text-2xl font-black text-slate-900 tracking-tight">Set New Password</h2>
                    <p className="text-sm text-slate-400 mt-1">Ensure your new password is secure</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                    {error && (
                        <div className="bg-red-50 text-red-600 p-3 rounded-xl text-sm flex items-center gap-2 border border-red-100 animate-in slide-in-from-top-2">
                            <AlertCircle size={16} /> {error}
                        </div>
                    )}

                    <div>
                        <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5 ml-1">New Credentials</label>
                        <div className="relative">
                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-300" size={18} />
                            <input
                                required
                                type="password"
                                placeholder="Enter secure password"
                                className="w-full pl-10 pr-4 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-2 focus:ring-cyan-500 outline-none transition-all"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                            />
                        </div>

                        {/* Password Strength Meter */}
                        {password.length > 0 && (
                            <div className="mt-3 px-1">
                                <div className="flex gap-1.5 h-1">
                                    {[1, 2, 3, 4].map((step) => (
                                        <div
                                            key={step}
                                            className={`flex-1 rounded-full transition-all duration-500 ${step <= strength
                                                ? (strength <= 2 ? 'bg-red-400' : strength === 3 ? 'bg-amber-400' : 'bg-emerald-500')
                                                : 'bg-slate-200'
                                                }`}
                                        />
                                    ))}
                                </div>
                                <p className="text-[10px] mt-2 text-slate-400 font-bold flex items-center gap-1">
                                    {strength < 4 ? (
                                        <>Requires: Uppercase, Number, & Symbol</>
                                    ) : (
                                        <span className="text-emerald-600 flex items-center gap-1">
                                            <ShieldCheck size={10} /> Secure Password
                                        </span>
                                    )}
                                </p>
                            </div>
                        )}
                    </div>

                    <div>
                        <label className="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1.5 ml-1">Repeat Password</label>
                        <div className="relative">
                            <ShieldCheck className={`absolute left-3 top-1/2 -translate-y-1/2 transition-colors ${password === confirm && confirm !== '' ? 'text-emerald-500' : 'text-slate-300'}`} size={18} />
                            <input
                                required
                                type="password"
                                placeholder="Verify your password"
                                className="w-full pl-10 pr-4 py-3.5 bg-slate-50 border border-slate-200 rounded-2xl focus:ring-2 focus:ring-cyan-500 outline-none transition-all"
                                value={confirm}
                                onChange={e => setConfirm(e.target.value)}
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-slate-900 text-white font-black py-4 rounded-2xl hover:bg-cyan-600 transition-all disabled:opacity-50 shadow-lg shadow-slate-200 mt-4"
                    >
                        {loading ? (
                            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin mx-auto" />
                        ) : (
                            'Update Identity'
                        )}
                    </button>
                </form>
            </div>
        </div>
    );
};