import React, { useState, useEffect } from 'react';
import { User, Lock, Save, Briefcase, Camera, AlertCircle, CheckCircle2, Download, Trash2, ShieldAlert, Link2, Link2Off, ExternalLink } from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useSearchParams } from 'react-router-dom';

export const Settings = () => {
    const { user, refreshProfile, logout } = useAuth();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'integrations' | 'data'>(() => {
        return searchParams.get('tab') === 'integrations' ? 'integrations' : 'profile';
    });

    // Auto-load Atlassian status and show feedback when returning from connect flow
    useEffect(() => {
        if (searchParams.get('tab') === 'integrations') {
            loadAtlassianStatus();
            if (searchParams.get('connected') === '1') {
                setMsg({ type: 'success', text: 'Atlassian account connected successfully.' });
            } else if (searchParams.get('error') === '1') {
                const msg = searchParams.get('msg');
                setMsg({ type: 'error', text: msg ? `Connection failed: ${msg}` : 'Failed to connect Atlassian account. Please try again.' });
            }
            // Clean up URL params
            navigate('/settings', { replace: true });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

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

    // Atlassian connection state
    const [atlassianStatus, setAtlassianStatus] = useState<{
        connected: boolean;
        site_name?: string;
        site_url?: string;
    } | null>(null);
    const [atlassianLoading, setAtlassianLoading] = useState(false);

    const loadAtlassianStatus = async () => {
        try {
            const res = await api.get('/auth/atlassian/status');
            setAtlassianStatus(res.data);
        } catch {
            setAtlassianStatus({ connected: false });
        }
    };

    const handleAtlassianDisconnect = async () => {
        setAtlassianLoading(true);
        try {
            await api.delete('/auth/atlassian/disconnect');
            setAtlassianStatus({ connected: false });
        } catch {
            setMsg({ type: 'error', text: 'Failed to disconnect Atlassian account.' });
        } finally {
            setAtlassianLoading(false);
        }
    };

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

    const switchTab = (tab: 'profile' | 'security' | 'integrations' | 'data') => {
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
                            { id: 'integrations', label: 'Integrations', icon: <Link2 size={18} /> },
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

                        {/* ── Integrations Tab ── */}
                        {activeTab === 'integrations' && (
                            <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 space-y-6" onMouseEnter={loadAtlassianStatus}>
                                <div>
                                    <h2 className="text-lg font-black text-slate-900 mb-1">Integrations</h2>
                                    <p className="text-sm text-slate-500">Connect third-party services to unlock Jira and Confluence export.</p>
                                </div>

                                {/* Atlassian card */}
                                <div className="border border-slate-200 rounded-2xl overflow-hidden">
                                    <div className="flex items-center justify-between px-6 py-5 bg-slate-50/50">
                                        <div className="flex items-center gap-4">
                                            <div className="w-10 h-10 rounded-xl bg-[#0052CC] flex items-center justify-center shrink-0">
                                                <svg width="20" height="20" viewBox="0 0 32 32" fill="none">
                                                    <path d="M15.271 13.219c-.379-.484-1.044-.452-1.44.065L8.073 21.7a.906.906 0 0 0 .729 1.453h6.891a.906.906 0 0 0 .74-.384c1.609-2.31 1.036-7.474-.162-9.55z" fill="#2684FF" />
                                                    <path d="M15.938 3.26C13.108 7.484 13.264 12.72 15.31 16.7l3.332 6.073a.907.907 0 0 0 .794.477h6.891a.906.906 0 0 0 .73-1.452C26.35 21 16.826 4.633 16.826 4.633c-.213-.368-.619-.574-1.021-.514a.906.906 0 0 0-.867.141z" fill="#2684FF" />
                                                </svg>
                                            </div>
                                            <div>
                                                <p className="font-bold text-slate-900">Atlassian</p>
                                                <p className="text-xs text-slate-500">Jira + Confluence export</p>
                                            </div>
                                        </div>

                                        {atlassianStatus === null ? (
                                            <button
                                                onClick={loadAtlassianStatus}
                                                className="text-xs font-bold text-cyan-600 hover:text-cyan-700"
                                            >
                                                Check status
                                            </button>
                                        ) : atlassianStatus.connected ? (
                                            <div className="flex items-center gap-3">
                                                <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-600 bg-emerald-50 border border-emerald-100 px-3 py-1.5 rounded-lg">
                                                    <Link2 size={12} /> Connected
                                                </span>
                                                <button
                                                    onClick={handleAtlassianDisconnect}
                                                    disabled={atlassianLoading}
                                                    className="flex items-center gap-1.5 text-xs font-bold text-red-500 hover:text-red-700 transition-colors disabled:opacity-50"
                                                >
                                                    <Link2Off size={12} />
                                                    {atlassianLoading ? 'Disconnecting...' : 'Disconnect'}
                                                </button>
                                            </div>
                                        ) : (
                                            <button
                                                onClick={async () => {
                                                    try {
                                                        const res = await api.get<{ url: string }>('/auth/atlassian/connect');
                                                        window.location.href = res.data.url;
                                                    } catch {
                                                        setMsg({ type: 'error', text: 'Failed to initiate Atlassian connection.' });
                                                    }
                                                }}
                                                className="flex items-center gap-2 px-4 py-2 bg-[#0052CC] hover:bg-[#0747A6] text-white text-xs font-bold rounded-lg transition-colors"
                                            >
                                                <Link2 size={12} /> Connect
                                            </button>
                                        )}
                                    </div>

                                    {atlassianStatus?.connected && atlassianStatus.site_name && (
                                        <div className="px-6 py-4 border-t border-slate-100 flex items-center gap-2 text-xs text-slate-500">
                                            <span>Connected to</span>
                                            <a
                                                href={atlassianStatus.site_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="font-bold text-slate-700 hover:text-cyan-600 flex items-center gap-1"
                                            >
                                                {atlassianStatus.site_name}
                                                <ExternalLink size={11} />
                                            </a>
                                        </div>
                                    )}
                                </div>
                            </div>
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