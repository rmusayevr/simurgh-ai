import React, { useState } from 'react';
import {
    CheckCircle, Search, UserCheck, UserX, Fingerprint,
    UserPlus, X, Loader2, AlertCircle, Copy, Eye, EyeOff,
    Trash2
} from 'lucide-react';
import { adminApi } from '../../api/client';
import { ConfirmModal } from '../modals/ConfirmModal';
import type { AdminUser, UserRole } from '../../types';
import { useAuth } from '../../context/AuthContext';

// ─── Create Participant Modal ─────────────────────────────────────────────────

function CreateParticipantModal({
    onClose,
    onCreated,
}: {
    onClose: () => void;
    onCreated: () => void;
}) {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('Study2026!');
    const [fullName, setFullName] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState<{ email: string; password: string } | null>(null);

    const handleCreate = async () => {
        if (!email.trim() || !password.trim()) {
            setError('Email and password are required.');
            return;
        }
        setLoading(true);
        setError('');
        try {
            await adminApi.createParticipant({
                email: email.trim(),
                password,
                full_name: fullName.trim() || undefined,
            });
            setSuccess({ email: email.trim(), password });
            onCreated();
        } catch (err: unknown) {
            const error = err as { response?: { data?: { detail?: string } } };
            const detail = error?.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : 'Failed to create account.');
        } finally {
            setLoading(false);
        }
    };

    const copyToClipboard = (text: string) => navigator.clipboard.writeText(text);

    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">

                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-cyan-100 rounded-lg flex items-center justify-center">
                            <UserPlus size={15} className="text-cyan-600" />
                        </div>
                        <div>
                            <h3 className="font-black text-slate-900 text-sm">Create Participant</h3>
                            <p className="text-[11px] text-slate-400">Account is immediately active — no email verification needed</p>
                        </div>
                    </div>
                    <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-200 transition-colors">
                        <X size={15} className="text-slate-500" />
                    </button>
                </div>

                <div className="px-6 py-5 space-y-4">
                    {!success ? (
                        <>
                            {/* Email */}
                            <div>
                                <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-1.5">
                                    Email <span className="text-red-400">*</span>
                                </label>
                                <input
                                    type="email"
                                    value={email}
                                    onChange={e => setEmail(e.target.value)}
                                    placeholder="p01@study.local"
                                    className="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
                                />
                                <p className="text-[11px] text-slate-400 mt-1">
                                    Suggested format: <span className="font-mono">p01@study.local</span>, <span className="font-mono">p02@study.local</span>…
                                </p>
                            </div>

                            {/* Full name */}
                            <div>
                                <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-1.5">
                                    Full Name <span className="text-slate-300">(optional)</span>
                                </label>
                                <input
                                    type="text"
                                    value={fullName}
                                    onChange={e => setFullName(e.target.value)}
                                    placeholder="Participant 01"
                                    className="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
                                />
                            </div>

                            {/* Password */}
                            <div>
                                <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-1.5">
                                    Password <span className="text-red-400">*</span>
                                </label>
                                <div className="relative">
                                    <input
                                        type={showPassword ? 'text' : 'password'}
                                        value={password}
                                        onChange={e => setPassword(e.target.value)}
                                        className="w-full px-3.5 py-2.5 pr-10 border border-slate-200 rounded-xl text-sm text-slate-900 font-mono focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(v => !v)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                                    >
                                        {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                                    </button>
                                </div>
                                <p className="text-[11px] text-slate-400 mt-1">
                                    Minimum 6 characters. Share this with the participant in your invitation email.
                                </p>
                            </div>

                            {error && (
                                <div className="flex items-start gap-2 bg-red-50 border border-red-100 text-red-700 rounded-xl px-3.5 py-3">
                                    <AlertCircle size={14} className="shrink-0 mt-0.5" />
                                    <p className="text-xs">{error}</p>
                                </div>
                            )}

                            <div className="flex gap-3 pt-1">
                                <button
                                    onClick={onClose}
                                    className="flex-1 py-2.5 border border-slate-200 text-slate-600 rounded-xl text-sm font-bold hover:bg-slate-50 transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleCreate}
                                    disabled={loading}
                                    className="flex-1 py-2.5 bg-cyan-600 hover:bg-cyan-700 disabled:bg-cyan-300 text-white rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-colors"
                                >
                                    {loading
                                        ? <><Loader2 size={14} className="animate-spin" /> Creating…</>
                                        : <><UserPlus size={14} /> Create Account</>}
                                </button>
                            </div>
                        </>
                    ) : (
                        /* Success state — show credentials to copy */
                        <div className="space-y-4">
                            <div className="flex items-center gap-2 text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-xl px-4 py-3">
                                <CheckCircle size={16} className="shrink-0" />
                                <p className="text-sm font-bold">Account created successfully</p>
                            </div>

                            <p className="text-xs text-slate-500">
                                Copy these credentials and send them to the participant in your invitation email.
                            </p>

                            {/* Credentials box */}
                            <div className="bg-slate-900 rounded-xl p-4 space-y-3 font-mono text-sm">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-0.5">Study URL</p>
                                        <p className="text-emerald-400">{window.location.origin}/study</p>
                                    </div>
                                    <button
                                        onClick={() => copyToClipboard(`${window.location.origin}/study`)}
                                        className="p-1.5 rounded-lg hover:bg-slate-700 transition-colors"
                                    >
                                        <Copy size={12} className="text-slate-400" />
                                    </button>
                                </div>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-0.5">Email</p>
                                        <p className="text-white">{success.email}</p>
                                    </div>
                                    <button
                                        onClick={() => copyToClipboard(success.email)}
                                        className="p-1.5 rounded-lg hover:bg-slate-700 transition-colors"
                                    >
                                        <Copy size={12} className="text-slate-400" />
                                    </button>
                                </div>
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-[10px] text-slate-500 uppercase tracking-widest mb-0.5">Password</p>
                                        <p className="text-white">{success.password}</p>
                                    </div>
                                    <button
                                        onClick={() => copyToClipboard(success.password)}
                                        className="p-1.5 rounded-lg hover:bg-slate-700 transition-colors"
                                    >
                                        <Copy size={12} className="text-slate-400" />
                                    </button>
                                </div>
                            </div>

                            <button
                                onClick={onClose}
                                className="w-full py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-sm font-bold transition-colors"
                            >
                                Done
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface AdminUsersProps {
    users: AdminUser[];
    searchTerm: string;
    setSearchTerm: (val: string) => void;
    onToggleStatus: (user: AdminUser) => Promise<void>;
    onDelete: (user: AdminUser) => Promise<void>;
    onRefresh: () => void;
}

export const AdminUsers: React.FC<AdminUsersProps> = ({
    users,
    searchTerm,
    setSearchTerm,
    onToggleStatus,
    onDelete,
    onRefresh,
}) => {
    const { user: currentUser } = useAuth();
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [confirmConfig, setConfirmConfig] = useState<{
        isOpen: boolean;
        title: string;
        message: string;
        type: 'danger' | 'info';
        onConfirm: () => void;
    }>({
        isOpen: false,
        title: '',
        message: '',
        type: 'info',
        onConfirm: () => { },
    });

    const closeConfirm = () => setConfirmConfig(prev => ({ ...prev, isOpen: false }));

    const requestToggleBan = (user: AdminUser) => {
        setConfirmConfig({
            isOpen: true,
            title: user.is_active ? 'Restrict Account?' : 'Restore Account?',
            message: user.is_active
                ? `Revoking access for ${user.email} will prevent them from starting new missions.`
                : `Allow ${user.email} to access the platform again?`,
            type: user.is_active ? 'danger' : 'info',
            onConfirm: async () => {
                await onToggleStatus(user);
                closeConfirm();
            },
        });
    };

    const requestDelete = (user: AdminUser) => {
        setConfirmConfig({
            isOpen: true,
            title: 'Permanently Delete User?',
            message: `This will permanently delete ${user.email} and ALL their projects, proposals, and data. This cannot be undone.`,
            type: 'danger',
            onConfirm: async () => {
                await onDelete(user);
                closeConfirm();
            },
        });
    };

    const handleRoleUpdate = (user: AdminUser, newRole: string) => {
        setConfirmConfig({
            isOpen: true,
            title: 'Update User Role?',
            message: `Change ${user.email}'s role to ${newRole.toUpperCase()}?`,
            type: 'info',
            onConfirm: async () => {
                try {
                    await adminApi.updateUser(user.id, { role: newRole as UserRole });
                    onRefresh();
                    closeConfirm();
                } catch {
                    alert('Access Denied: You cannot change roles.');
                }
            },
        });
    };

    return (
        <>
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden animate-in fade-in">

                {/* Header */}
                <div className="p-6 border-b border-slate-100 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-slate-50/30">
                    <div>
                        <h3 className="font-bold text-slate-800 text-lg">User Management</h3>
                        <p className="text-xs text-slate-500 font-medium uppercase tracking-widest mt-0.5">
                            {users.length} Registered Identities
                        </p>
                    </div>
                    <div className="flex items-center gap-3 w-full md:w-auto">
                        <div className="relative group flex-1 md:flex-none">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-cyan-500 transition-colors" size={16} />
                            <input
                                type="text"
                                placeholder="Search by name or email..."
                                value={searchTerm}
                                onChange={e => setSearchTerm(e.target.value)}
                                className="pl-9 pr-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-cyan-500 focus:border-cyan-500 outline-none w-full md:w-72 bg-white transition-all shadow-sm"
                            />
                        </div>
                        <button
                            onClick={() => setShowCreateModal(true)}
                            className="flex items-center gap-2 px-4 py-2.5 bg-cyan-600 hover:bg-cyan-700 text-white rounded-xl text-sm font-bold transition-colors shadow-sm shrink-0"
                        >
                            <UserPlus size={15} /> Create Participant
                        </button>
                    </div>
                </div>

                {/* Table */}
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                        <thead className="bg-slate-50 text-slate-400 uppercase text-[10px] font-black tracking-widest border-b border-slate-100">
                            <tr>
                                <th className="px-6 py-4">Identity</th>
                                <th className="px-6 py-4 text-center">Security Status</th>
                                <th className="px-6 py-4 text-center">System Role</th>
                                <th className="px-6 py-4 text-right">Administrative Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {users.map(user => {
                                const isSelf = user.id === currentUser?.id;
                                return (
                                    <tr key={user.id} className="hover:bg-slate-50/80 transition-all group">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className={`relative w-9 h-9 rounded-full flex items-center justify-center font-bold text-xs ring-2 ring-offset-2 ${user.is_superuser
                                                    ? 'bg-cyan-600 text-white ring-cyan-100'
                                                    : 'bg-slate-100 text-slate-600 ring-slate-50'
                                                    }`}>
                                                    {user.full_name?.charAt(0) || user.email.charAt(0).toUpperCase()}
                                                    {isSelf && (
                                                        <span className="absolute -top-1 -right-1 bg-emerald-500 text-[8px] px-1 rounded-full ring-2 ring-white">
                                                            YOU
                                                        </span>
                                                    )}
                                                </div>
                                                <div>
                                                    <p className="font-bold text-slate-900 leading-tight">
                                                        {user.full_name || 'Incognito User'}
                                                    </p>
                                                    <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                                                        <Fingerprint size={10} /> {user.email}
                                                    </p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex justify-center">
                                                {user.is_active ? (
                                                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black uppercase bg-emerald-50 text-emerald-600 border border-emerald-100">
                                                        <CheckCircle size={12} /> Authorized
                                                    </span>
                                                ) : (
                                                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black uppercase bg-red-50 text-red-600 border border-red-100">
                                                        <UserX size={12} /> Restricted
                                                    </span>
                                                )}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex justify-center">
                                                <select
                                                    value={user.role || (user.is_superuser ? 'ADMIN' : 'USER')}
                                                    onChange={e => handleRoleUpdate(user, e.target.value)}
                                                    disabled={isSelf}
                                                    className={`text-[10px] font-black uppercase rounded-lg px-2.5 py-1.5 border transition-all outline-none ${isSelf
                                                        ? 'bg-slate-50 text-slate-400 border-slate-100 cursor-not-allowed'
                                                        : user.role === 'ADMIN' || user.is_superuser
                                                            ? 'bg-cyan-50 text-cyan-700 border-cyan-100 cursor-pointer'
                                                            : 'bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200 cursor-pointer'
                                                        }`}
                                                >
                                                    <option value="USER">Standard User</option>
                                                    <option value="MANAGER">Manager</option>
                                                    <option value="ADMIN">System Admin</option>
                                                </select>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                {!isSelf && (
                                                    <>
                                                        <button
                                                            onClick={() => requestToggleBan(user)}
                                                            className={`p-2 rounded-lg transition-colors ${user.is_active
                                                                ? 'text-slate-400 hover:text-amber-600 hover:bg-amber-50'
                                                                : 'text-emerald-600 bg-emerald-50'
                                                                }`}
                                                            title={user.is_active ? 'Restrict Access' : 'Grant Access'}
                                                        >
                                                            {user.is_active ? <UserX size={18} /> : <UserCheck size={18} />}
                                                        </button>
                                                        <button
                                                            onClick={() => requestDelete(user)}
                                                            className="p-2 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                                                            title="Permanently Delete User"
                                                        >
                                                            <Trash2 size={18} />
                                                        </button>
                                                    </>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {showCreateModal && (
                <CreateParticipantModal
                    onClose={() => setShowCreateModal(false)}
                    onCreated={() => {
                        onRefresh();
                    }}
                />
            )}

            <ConfirmModal
                isOpen={confirmConfig.isOpen}
                title={confirmConfig.title}
                message={confirmConfig.message}
                type={confirmConfig.type}
                onClose={closeConfirm}
                onConfirm={confirmConfig.onConfirm}
            />
        </>
    );
};