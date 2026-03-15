import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, publicApi } from '../api/client';
import { UserPlus, Mail, Lock, User, Briefcase, AlertCircle, ShieldCheck, Info } from 'lucide-react';
import { SimurghMark } from '../components/SimurghMark';

export const Register = () => {
    const navigate = useNavigate();
    const [formData, setFormData] = useState({ email: '', password: '', confirm_password: '', full_name: '', job_title: '' });
    const [termsAccepted, setTermsAccepted] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [registrationsOpen, setRegistrationsOpen] = useState<boolean | null>(null);

    useEffect(() => {
        publicApi.getSystemStatus()
            .then(res => setRegistrationsOpen(res.data.allow_registrations ?? true))
            .catch(() => setRegistrationsOpen(true));
    }, []);

    const passwordRules = [
        { key: 'length', label: 'At least 8 characters', test: (p: string) => p.length >= 8 },
        { key: 'uppercase', label: 'One uppercase letter', test: (p: string) => /[A-Z]/.test(p) },
        { key: 'number', label: 'One number', test: (p: string) => /[0-9]/.test(p) },
        { key: 'special', label: 'One special character (!@#$%^&*)', test: (p: string) => /[!@#$%^&*(),.?":{}|<>]/.test(p) },
    ];

    const passedRules = passwordRules.filter(r => r.test(formData.password));
    const strength = passedRules.length;
    const passwordValid = strength === passwordRules.length;
    const strengthColor = strength <= 2 ? 'bg-red-400' : strength === 3 ? 'bg-amber-400' : 'bg-emerald-500';

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (!passwordValid) { setError('Password does not meet the requirements.'); return; }
        if (formData.password !== formData.confirm_password) { setError('Passwords do not match.'); return; }
        if (!termsAccepted) { setError('You must accept the Terms of Service and Privacy Policy to register.'); return; }
        setLoading(true);
        try {
            const { data } = await api.post('/auth/register', {
                email: formData.email, password: formData.password,
                confirm_password: formData.confirm_password, full_name: formData.full_name,
                job_title: formData.job_title, terms_accepted: termsAccepted,
            });
            const autoActivated = data?.message?.toLowerCase().includes('you can log in');
            if (autoActivated) {
                navigate('/login?registered=1');
            } else {
                navigate(`/email-sent?mode=sent&email=${encodeURIComponent(formData.email)}`);
            }
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } } };
            const msg = error?.response?.data?.detail || 'Registration failed.';
            setError(typeof msg === 'string' ? msg : 'Please check your inputs and try again.');
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
                        <h1 className="text-2xl font-black text-white mb-1">Create your account</h1>
                        <p className="text-slate-400 text-sm">Join technical leaders making better architectural decisions</p>
                    </div>

                    {registrationsOpen === false && (
                        <div className="mx-6 mt-6 bg-blue-50 text-blue-700 p-4 rounded-xl text-sm flex items-start gap-3 border border-blue-100">
                            <Info size={16} className="mt-0.5 shrink-0" />
                            <div>
                                <p className="font-semibold mb-1">Registrations are currently closed</p>
                                <p>New accounts are not being accepted at this time. Please contact the administrator or check back later.</p>
                            </div>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="px-8 py-6 space-y-4">
                        {error && (
                            <div className="bg-red-50 text-red-600 p-3 rounded-xl text-sm flex items-center gap-2 border border-red-100">
                                <AlertCircle size={16} /> {error}
                            </div>
                        )}

                        <div className="grid grid-cols-2 gap-4">
                            <div className="col-span-2 sm:col-span-1">
                                <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Full Name <span className="text-red-400">*</span></label>
                                <div className="relative">
                                    <User className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                    <input required type="text" placeholder="Jane Smith"
                                        className="w-full pl-9 pr-3 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 focus:bg-white outline-none transition-all text-sm"
                                        value={formData.full_name}
                                        onChange={e => setFormData({ ...formData, full_name: e.target.value })} />
                                </div>
                            </div>
                            <div className="col-span-2 sm:col-span-1">
                                <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Job Title</label>
                                <div className="relative">
                                    <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                    <input type="text" placeholder="Solutions Architect"
                                        className="w-full pl-9 pr-3 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 focus:bg-white outline-none transition-all text-sm"
                                        value={formData.job_title}
                                        onChange={e => setFormData({ ...formData, job_title: e.target.value })} />
                                </div>
                            </div>
                        </div>

                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Email Address <span className="text-red-400">*</span></label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                <input required type="email" placeholder="name@company.com"
                                    className="w-full pl-9 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 focus:bg-white outline-none transition-all text-sm"
                                    value={formData.email}
                                    onChange={e => setFormData({ ...formData, email: e.target.value })} />
                            </div>
                        </div>

                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Password <span className="text-red-400">*</span></label>
                            <div className="relative">
                                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                <input required type="password" placeholder="••••••••"
                                    className="w-full pl-9 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 focus:bg-white outline-none transition-all text-sm"
                                    value={formData.password}
                                    onChange={e => setFormData({ ...formData, password: e.target.value })} />
                            </div>
                            {formData.password.length > 0 && (
                                <div className="mt-2 space-y-1.5">
                                    <div className="flex gap-1 h-1.5">
                                        {[1, 2, 3, 4].map(step => (
                                            <div key={step} className={`flex-1 rounded-full transition-all duration-300 ${step <= strength ? strengthColor : 'bg-slate-200'}`} />
                                        ))}
                                    </div>
                                    <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 pt-1">
                                        {passwordRules.map(rule => {
                                            const passed = rule.test(formData.password);
                                            return (
                                                <p key={rule.key} className={`text-[10px] font-medium flex items-center gap-1 transition-colors ${passed ? 'text-emerald-600' : 'text-slate-400'}`}>
                                                    <span>{passed ? '✓' : '○'}</span> {rule.label}
                                                </p>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}
                        </div>

                        <div>
                            <label className="block text-xs font-bold text-slate-500 uppercase mb-1">Confirm Password <span className="text-red-400">*</span></label>
                            <div className="relative">
                                <ShieldCheck
                                    className={`absolute left-3 top-1/2 -translate-y-1/2 transition-colors ${formData.confirm_password && formData.password === formData.confirm_password ? 'text-emerald-500' : 'text-slate-400'}`}
                                    size={16} />
                                <input required type="password" placeholder="••••••••"
                                    className="w-full pl-9 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 focus:bg-white outline-none transition-all text-sm"
                                    value={formData.confirm_password}
                                    onChange={e => setFormData({ ...formData, confirm_password: e.target.value })} />
                            </div>
                        </div>

                        <div className="flex items-start gap-3 pt-1">
                            <input id="terms" type="checkbox" checked={termsAccepted}
                                onChange={e => setTermsAccepted(e.target.checked)}
                                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500 cursor-pointer" />
                            <label htmlFor="terms" className="text-xs text-slate-500 leading-relaxed cursor-pointer">
                                I agree to the{' '}
                                <a href="/terms" target="_blank" rel="noopener noreferrer" className="font-bold text-cyan-600 hover:underline">Terms of Service</a>
                                {' '}and{' '}
                                <a href="/privacy" target="_blank" rel="noopener noreferrer" className="font-bold text-cyan-600 hover:underline">Privacy Policy</a>
                            </label>
                        </div>

                        <button type="submit"
                            disabled={loading || !termsAccepted || registrationsOpen === false || (formData.password.length > 0 && !passwordValid)}
                            className="w-full bg-cyan-600 text-white font-bold py-3 rounded-xl hover:bg-cyan-700 transition-all flex items-center justify-center gap-2 shadow-lg shadow-cyan-200 disabled:opacity-50 disabled:cursor-not-allowed">
                            {loading
                                ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                : <><UserPlus size={18} /> Create Account</>
                            }
                        </button>
                    </form>

                    <div className="bg-slate-50 px-8 py-4 border-t border-slate-100 text-center">
                        <p className="text-sm text-slate-600">
                            Already have an account?{' '}
                            <button onClick={() => navigate('/login')}
                                className="font-bold text-cyan-600 hover:text-cyan-800 transition-colors">
                                Sign in
                            </button>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};