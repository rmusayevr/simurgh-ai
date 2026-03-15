import React, { useState, useEffect } from 'react';
import { User, Lock, Save, Briefcase, Camera, AlertCircle, CheckCircle2, Download, Trash2, ShieldAlert } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export const Settings = () => {
    const { user, refreshProfile, logout } = useAuth();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'data'>('profile');

    // Profile State
    const [profileForm, setProfileForm] = useState({
        full_name: '',
        job_title: '',
        avatar_url: ''
    });

    // Password State
    const [passwordForm, setPasswordForm] = useState({
        current_password: '',
        new_password: '',
        confirm_password: ''
    });

    // Delete account state
    const [deletePassword, setDeletePassword] = useState('');
    const [deleteConfirmText, setDeleteConfirmText] = useState('');
    const [showDeleteSection, setShowDeleteSection] = useState(false);

    const [loading, setLoading] = useState(false);
    const [exportLoading, setExportLoading] = useState(false);
    const [msg, setMsg] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    useEffect(() => {
        if (user) {
            setProfileForm({
                full_name: user.full_name || '',
                job_title: user.job_title || '',
                avatar_url: user.avatar_url || ''
            });
        }
    }, [user]);

    const handleProfileUpdate = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setMsg(null);
        try {
            await api.patch('/auth/me', profileForm);
            await refreshProfile();
            setMsg({ type: 'success', text: 'Profile updated successfully' });
        } catch {
            setMsg({ type: 'error', text: 'Failed to update profile' });
        } finally {
            setLoading(false);
        }
    };

    const validatePassword = (p: string) => {
        if (p.length < 8) return 'Password must be at least 8 characters.';
        if (!/[A-Z]/.test(p)) return 'Password must contain at least one uppercase letter.';
        if (!/[0-9]/.test(p)) return 'Password must contain at least one number.';
        if (!/[!@#$%^&*(),.?":{}|<>]/.test(p)) return 'Password must contain at least one special character (!@#$%^&*).';
        return null;
    };

    const handlePasswordChange = async (e: React.ChangeEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (passwordForm.new_password !== passwordForm.confirm_password) {
            setMsg({ type: 'error', text: "New passwords do not match" });
            return;
        }
        const pwError = validatePassword(passwordForm.new_password);
        if (pwError) {
            setMsg({ type: 'error', text: pwError });
            return;
        }

        setLoading(true);
        setMsg(null);
        try {
            await api.post('/auth/me/change-password', {
                current_password: passwordForm.current_password,
                new_password: passwordForm.new_password,
                confirm_new_password: passwordForm.confirm_password
            });
            setMsg({ type: 'success', text: 'Password changed successfully' });
            setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
        } catch (err: unknown) {
            const errorData = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
            const errorText = Array.isArray(errorData)
                ? errorData[0].msg
                : errorData || "Failed to change password";
            setMsg({ type: 'error', text: errorText });
        } finally {
            setLoading(false);
        }
    };

    const handleExportData = async () => {
        setExportLoading(true);
        setMsg(null);
        try {
            const response = await api.get('/auth/me/export', { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/json' }));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'my-data-export.json');
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch {
            setMsg({ type: 'error', text: 'Failed to export data. Please try again.' });
        } finally {
            setExportLoading(false);
        }
    };

    const handleDeleteAccount = async () => {
        if (deleteConfirmText !== 'DELETE') {
            setMsg({ type: 'error', text: 'Please type DELETE to confirm.' });
            return;
        }
        if (!deletePassword) {
            setMsg({ type: 'error', text: 'Please enter your current password.' });
            return;
        }

        setLoading(true);
        setMsg(null);
        try {
            await api.delete('/auth/me', { data: { password: deletePassword } });
            logout();
            navigate('/login');
        } catch (err: unknown) {
            const errorData = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
            setMsg({ type: 'error', text: errorData || 'Account deletion failed. Check your password and try again.' });
        } finally {
            setLoading(false);
        }
    };

    const switchTab = (tab: 'profile' | 'security' | 'data') => {
        setActiveTab(tab);
        setMsg(null);
        setShowDeleteSection(false);
        setDeletePassword('');
        setDeleteConfirmText('');
    };

    return (
        <div className="min-h-screen bg-slate-50">
            <div className="max-w-4xl mx-auto px-6 py-12 animate-in fade-in slide-in-from-bottom-4">
                <h1 className="text-3xl font-black text-slate-900 mb-8">Account Settings</h1>

                <div className="flex flex-col md:flex-row gap-8">
                    {/* Sidebar */}
                    <div className="w-full md:w-64 space-y-2">
                        {([
                            { id: 'profile', label: 'Profile', icon: <User size={18} /> },
                            { id: 'security', label: 'Security', icon: <Lock size={18} /> },
                            { id: 'data', label: 'Data & Privacy', icon: <ShieldAlert size={18} /> },
                        ] as const).map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => switchTab(tab.id)}
                                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-bold transition-all ${activeTab === tab.id
                                    ? 'bg-cyan-600 text-white shadow-lg shadow-cyan-200'
                                    : 'bg-white text-slate-600 hover:bg-slate-100'
                                    }`}
                            >
                                {tab.icon} {tab.label}
                            </button>
                        ))}
                    </div>

                    {/* Content Area */}
                    <div className="flex-1 bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
                        {msg && (
                            <div className={`mb-6 p-4 rounded-xl flex items-center gap-3 text-sm font-bold ${msg.type === 'success' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                                }`}>
                                {msg.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
                                {msg.text}
                            </div>
                        )}

                        {/* ── Profile Tab ── */}
                        {activeTab === 'profile' && (
                            <form onSubmit={handleProfileUpdate} className="space-y-6">
                                <div className="flex items-center gap-6 mb-8">
                                    <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center text-slate-300 border-2 border-slate-200 overflow-hidden">
                                        {profileForm.avatar_url ? (
                                            <img src={profileForm.avatar_url} alt="Avatar" className="w-full h-full object-cover" />
                                        ) : (
                                            <User size={32} />
                                        )}
                                    </div>
                                    <div className="flex-1">
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Avatar URL</label>
                                        <div className="relative">
                                            <Camera className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                                            <input
                                                type="text"
                                                placeholder="https://..."
                                                className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 outline-none text-sm"
                                                value={profileForm.avatar_url}
                                                onChange={e => setProfileForm({ ...profileForm, avatar_url: e.target.value })}
                                            />
                                        </div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 gap-6">
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Full Name</label>
                                        <div className="relative">
                                            <User className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                                            <input
                                                type="text"
                                                className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 outline-none"
                                                value={profileForm.full_name}
                                                onChange={e => setProfileForm({ ...profileForm, full_name: e.target.value })}
                                            />
                                        </div>
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Job Title</label>
                                        <div className="relative">
                                            <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                                            <input
                                                type="text"
                                                className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 outline-none"
                                                value={profileForm.job_title}
                                                onChange={e => setProfileForm({ ...profileForm, job_title: e.target.value })}
                                            />
                                        </div>
                                    </div>
                                </div>

                                <div className="pt-4 flex justify-end">
                                    <button
                                        type="submit"
                                        disabled={loading}
                                        className="bg-slate-900 text-white px-6 py-3 rounded-xl font-bold hover:bg-slate-800 transition-all flex items-center gap-2"
                                    >
                                        <Save size={18} /> Save Changes
                                    </button>
                                </div>
                            </form>
                        )}

                        {/* ── Security Tab ── */}
                        {activeTab === 'security' && (
                            <form onSubmit={handlePasswordChange} className="space-y-6">
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Current Password</label>
                                    <input
                                        type="password"
                                        required
                                        className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 outline-none"
                                        value={passwordForm.current_password}
                                        onChange={e => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
                                    />
                                </div>
                                <hr className="border-slate-100" />
                                <div className="grid md:grid-cols-2 gap-6">
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-2">New Password</label>
                                        <input
                                            type="password"
                                            required
                                            minLength={8}
                                            className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 outline-none"
                                            value={passwordForm.new_password}
                                            onChange={e => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Confirm New Password</label>
                                        <input
                                            type="password"
                                            required
                                            minLength={8}
                                            className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-cyan-500 outline-none"
                                            value={passwordForm.confirm_password}
                                            onChange={e => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                                        />
                                    </div>
                                </div>
                                <div className="pt-4 flex justify-end">
                                    <button
                                        type="submit"
                                        disabled={loading}
                                        className="bg-slate-900 text-white px-6 py-3 rounded-xl font-bold hover:bg-slate-800 transition-all flex items-center gap-2"
                                    >
                                        <Lock size={18} /> Update Password
                                    </button>
                                </div>
                            </form>
                        )}

                        {/* ── Data & Privacy Tab ── */}
                        {activeTab === 'data' && (
                            <div className="space-y-8">

                                {/* Export section */}
                                <div>
                                    <h2 className="text-lg font-black text-slate-900 mb-1">Export Your Data</h2>
                                    <p className="text-sm text-slate-500 mb-4">
                                        Download a copy of all personal data we hold about you — your profile,
                                        account history, and projects — as a JSON file.
                                    </p>
                                    <button
                                        onClick={handleExportData}
                                        disabled={exportLoading}
                                        className="flex items-center gap-2 px-5 py-3 bg-cyan-600 text-white font-bold rounded-xl hover:bg-cyan-700 transition-all disabled:opacity-60"
                                    >
                                        {exportLoading ? (
                                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                        ) : (
                                            <Download size={16} />
                                        )}
                                        {exportLoading ? 'Preparing export…' : 'Download My Data'}
                                    </button>
                                </div>

                                <hr className="border-slate-100" />

                                {/* Delete section */}
                                <div>
                                    <h2 className="text-lg font-black text-slate-900 mb-1">Delete Account</h2>
                                    <p className="text-sm text-slate-500 mb-4">
                                        Permanently delete your account and all associated data. This action
                                        cannot be undone.
                                    </p>

                                    {!showDeleteSection ? (
                                        <button
                                            onClick={() => setShowDeleteSection(true)}
                                            className="flex items-center gap-2 px-5 py-3 border-2 border-red-200 text-red-600 font-bold rounded-xl hover:bg-red-50 transition-all"
                                        >
                                            <Trash2 size={16} /> Delete My Account
                                        </button>
                                    ) : (
                                        <div className="border-2 border-red-200 rounded-2xl p-6 space-y-4 bg-red-50">
                                            <div className="flex items-start gap-3 text-red-700 text-sm">
                                                <AlertCircle size={18} className="mt-0.5 shrink-0" />
                                                <p>
                                                    This will permanently delete your account, all your projects,
                                                    and all associated data. You will be logged out immediately.
                                                    <strong className="block mt-1">This cannot be undone.</strong>
                                                </p>
                                            </div>

                                            <div>
                                                <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
                                                    Current Password
                                                </label>
                                                <input
                                                    type="password"
                                                    placeholder="Enter your password to confirm"
                                                    className="w-full px-4 py-3 bg-white border border-red-200 rounded-xl focus:ring-2 focus:ring-red-400 outline-none text-sm"
                                                    value={deletePassword}
                                                    onChange={e => setDeletePassword(e.target.value)}
                                                />
                                            </div>

                                            <div>
                                                <label className="block text-xs font-bold text-slate-500 uppercase mb-2">
                                                    Type <span className="text-red-600">DELETE</span> to confirm
                                                </label>
                                                <input
                                                    type="text"
                                                    placeholder="DELETE"
                                                    className="w-full px-4 py-3 bg-white border border-red-200 rounded-xl focus:ring-2 focus:ring-red-400 outline-none text-sm font-mono"
                                                    value={deleteConfirmText}
                                                    onChange={e => setDeleteConfirmText(e.target.value)}
                                                />
                                            </div>

                                            <div className="flex gap-3 pt-2">
                                                <button
                                                    onClick={handleDeleteAccount}
                                                    disabled={loading || deleteConfirmText !== 'DELETE' || !deletePassword}
                                                    className="flex items-center gap-2 px-5 py-3 bg-red-600 text-white font-bold rounded-xl hover:bg-red-700 transition-all disabled:opacity-50"
                                                >
                                                    {loading ? (
                                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                                    ) : (
                                                        <Trash2 size={16} />
                                                    )}
                                                    {loading ? 'Deleting…' : 'Permanently Delete Account'}
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        setShowDeleteSection(false);
                                                        setDeletePassword('');
                                                        setDeleteConfirmText('');
                                                        setMsg(null);
                                                    }}
                                                    className="px-5 py-3 border border-slate-200 text-slate-600 font-bold rounded-xl hover:bg-white transition-all"
                                                >
                                                    Cancel
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};