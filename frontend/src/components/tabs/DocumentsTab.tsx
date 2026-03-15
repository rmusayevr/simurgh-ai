import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Upload, FileText, CheckCircle, Loader2, Users, UserPlus,
    Mail, Shield, Trash2, AlertCircle,
} from 'lucide-react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { ConfirmModal } from '../modals/ConfirmModal';
import type { DocumentsTabProps, HistoricalDocument, Project, ProjectRole } from '../../types';

// ─── Types ────────────────────────────────────────────────────────────────────

interface IndexingStatus {
    document_id: number;
    status: 'pending' | 'processing' | 'ready' | 'failed';
    total_chunks: number;
    vector_indexed: number;
    fts_indexed: number;
}

interface TeamMember {
    id: number;
    full_name: string | null;
    email?: string;
    avatar_url?: string | null;
    project_role: ProjectRole;
}

interface FeedbackState {
    isOpen: boolean;
    title: string;
    message: string;
    type: 'info' | 'success' | 'danger';
}

interface FastAPIValidationError {
    loc: (string | number)[];
    msg: string;
    type?: string;
}

interface APIErrorResponse {
    error?: string;
    detail?: string | FastAPIValidationError[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Basic email format validation — catches obviously invalid input before hitting the API. */
const isValidEmail = (email: string): boolean =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

/**
 * Extract a human-readable error message from an Axios error response.
 * Handles both our custom { error, detail } shape and raw FastAPI 422 bodies.
 */
const extractErrorMessage = (err: unknown): string => {
    if (typeof err !== 'object' || err === null || !('response' in err)) {
        return 'An unexpected error occurred. Please try again.';
    }

    const response = (err as { response?: { data?: APIErrorResponse } }).response;
    const data = response?.data;

    if (!data) return 'An unexpected error occurred. Please try again.';

    if (typeof data.detail === 'string') return data.detail;
    if (typeof data.error === 'string') return data.error;

    if (Array.isArray(data.detail)) {
        const msgs = data.detail.map((e) => {
            const field = Array.isArray(e.loc)
                ? e.loc.filter((p) => !['body', 'query', 'path'].includes(String(p))).join(' → ')
                : '';

            return field ? `${field}: ${e.msg}` : e.msg;
        });

        return msgs.join('; ');
    }

    return 'Make sure the user is registered in the system.';
};

// ─── Status badge ─────────────────────────────────────────────────────────────
const IndexingBadge = ({ status }: { status: IndexingStatus | undefined }) => {
    if (!status) {
        return (
            <span className="flex items-center gap-1 text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded text-[10px]">
                <Loader2 size={9} className="animate-spin" /> Checking...
            </span>
        );
    }
    switch (status.status) {
        case 'ready':
            return (
                <span className="flex items-center gap-1 text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded text-[10px]" title="Full-Text & Vector Search Active">
                    <CheckCircle size={9} /> Hybrid Ready
                </span>
            );
        case 'processing':
            return (
                <span className="flex items-center gap-1 text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded text-[10px] animate-pulse">
                    <Loader2 size={9} className="animate-spin" /> Indexing ({status.vector_indexed}/{status.total_chunks})
                </span>
            );
        case 'pending':
            return (
                <span className="flex items-center gap-1 text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded text-[10px]">
                    <Loader2 size={9} className="animate-spin" /> Queued
                </span>
            );
        default:
            return (
                <span className="flex items-center gap-1 text-red-500 bg-red-50 px-1.5 py-0.5 rounded text-[10px]" title="Processing Failed">
                    <AlertCircle size={9} /> Failed
                </span>
            );
    }
};

// ─── Main component ───────────────────────────────────────────────────────────
export const DocumentsTab: React.FC<DocumentsTabProps> = ({ projectId }) => {
    const { user } = useAuth();

    const [documents, setDocuments] = useState<HistoricalDocument[]>([]);
    const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
    const [projectOwnerId, setProjectOwnerId] = useState<number | null>(null);
    const [statusMap, setStatusMap] = useState<Record<number, IndexingStatus>>({});

    const [inviteEmail, setInviteEmail] = useState('');
    const [selectedRole, setSelectedRole] = useState<'EDITOR' | 'VIEWER'>('VIEWER');
    const [isInviting, setIsInviting] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [docToDelete, setDocToDelete] = useState<number | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);

    const [feedback, setFeedback] = useState<FeedbackState>({
        isOpen: false, title: '', message: '', type: 'info',
    });

    const showFeedback = useCallback((title: string, message: string, type: FeedbackState['type'] = 'info') => {
        setFeedback({ isOpen: true, title, message, type });
    }, []);

    // ─── Derived permissions ────────────────────────────────────────────────────
    const isOwner = user?.id === projectOwnerId || user?.role === 'ADMIN';

    const canManageDocs = useMemo(() => {
        if (!user) return false;
        if (user.role === 'ADMIN' || user.id === projectOwnerId) return true;
        const member = teamMembers.find(m => m.id === user.id);
        return member?.project_role === 'EDITOR' || member?.project_role === 'ADMIN';
    }, [user, projectOwnerId, teamMembers]);

    const displayedMembers = useMemo(() => {
        if (!user) return teamMembers;
        return [...teamMembers].sort((a, b) => {
            if (a.id === user.id) return -1;
            if (b.id === user.id) return 1;
            return 0;
        });
    }, [teamMembers, user]);

    // ─── Data loading ────────────────────────────────────────────────────────────
    const fetchProjectData = useCallback(async () => {
        try {
            const res = await api.get<Project>(`/projects/${projectId}`);
            const project = res.data;

            setDocuments(project.historical_documents ?? []);
            setProjectOwnerId(project.owner_id);

            const members: TeamMember[] = (project.stakeholder_links ?? []).map(link => ({
                id: link.user.id,
                full_name: link.user.full_name,
                avatar_url: link.user.avatar_url,
                project_role: link.role,
            }));

            // Ensure owner is always in the list
            if (project.owner && !members.some(m => m.id === project.owner_id)) {
                members.push({
                    id: project.owner_id,
                    full_name: project.owner.full_name,
                    avatar_url: project.owner.avatar_url,
                    project_role: 'OWNER',
                });
            }

            setTeamMembers(members);
        } catch {
            // Silently fail — parent already loaded the project; this is supplemental
        }
    }, [projectId]);

    useEffect(() => { fetchProjectData(); }, [fetchProjectData]);

    // ─── Indexing status polling ─────────────────────────────────────────────────
    const fetchStatus = useCallback(async (docId: number) => {
        try {
            // Correct URL: /documents/{doc_id}/search-status (router prefix is /documents)
            const res = await api.get<IndexingStatus>(`/documents/${docId}/search-status`);
            setStatusMap(prev => ({ ...prev, [docId]: res.data }));
        } catch {
            setStatusMap(prev => ({ ...prev, [docId]: { document_id: docId, status: 'failed', total_chunks: 0, vector_indexed: 0, fts_indexed: 0 } }));
        }
    }, []);

    // Initial status fetch for all documents
    useEffect(() => {
        documents.forEach(doc => fetchStatus(doc.id));
    }, [documents, fetchStatus]);

    // Poll documents that are still processing
    useEffect(() => {
        const pending = documents.filter(doc => {
            const s = statusMap[doc.id]?.status;
            return s === 'processing' || s === 'pending';
        });

        if (pending.length === 0) return;

        const interval = setInterval(() => {
            pending.forEach(doc => fetchStatus(doc.id));
        }, 3000);

        return () => clearInterval(interval);
    }, [statusMap, documents, fetchStatus]);

    // ─── File upload ─────────────────────────────────────────────────────────────
    const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setIsUploading(true);
        const formData = new FormData();
        formData.append('file', file);

        try {
            await api.post<HistoricalDocument>(
                `/documents/projects/${projectId}/documents`,
                formData,
                { headers: { 'Content-Type': 'multipart/form-data' } }
            );
            await fetchProjectData();
        } catch {
            showFeedback('Upload Failed', 'Failed to upload document. Please try again.', 'danger');
        } finally {
            setIsUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    }, [projectId, fetchProjectData, showFeedback]);

    // ─── Document delete ──────────────────────────────────────────────────────────
    const executeDelete = useCallback(async () => {
        if (!docToDelete) return;
        try {
            await api.delete(`/documents/${docToDelete}`);
            setDocuments(prev => prev.filter(d => d.id !== docToDelete));
            setStatusMap(prev => { const next = { ...prev }; delete next[docToDelete]; return next; });
        } catch {
            showFeedback('Delete Failed', 'Failed to delete document. Please try again.', 'danger');
        } finally {
            setDocToDelete(null);
        }
    }, [docToDelete, showFeedback]);

    // ─── Member invite ────────────────────────────────────────────────────────────
    const handleInvite = useCallback(async () => {
        const email = inviteEmail.trim();
        if (!email) return;

        if (!isValidEmail(email)) {
            showFeedback(
                'Invalid Email',
                `"${email}" is not a valid email address. Please enter a valid email like user@example.com`,
                'danger',
            );
            return;
        }

        if (teamMembers.some(m => m.email === email)) {
            showFeedback('Already a Member', `${email} is already part of the Mission Council.`, 'info');
            return;
        }

        setIsInviting(true);
        try {
            await api.post(`/projects/${projectId}/members`, { email, role: selectedRole });
            setInviteEmail('');
            await fetchProjectData();
            showFeedback('Member Added', `${email} has been added as a ${selectedRole}.`, 'success');
        } catch (err: unknown) {
            const message = extractErrorMessage(err);
            showFeedback('Invite Failed', message, 'danger');
        } finally {
            setIsInviting(false);
        }
    }, [inviteEmail, selectedRole, teamMembers, projectId, fetchProjectData, showFeedback]);

    const handleInviteKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Enter') handleInvite();
    }, [handleInvite]);

    // ─── Render ───────────────────────────────────────────────────────────────────
    return (
        <div className="space-y-8 max-w-4xl mx-auto animate-in fade-in duration-300">

            {/* ── Mission Council (team members) ──────────────────────────────────── */}
            <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-6 border-b border-slate-100 flex items-center gap-3 bg-slate-50/50">
                    <div className="p-2 bg-cyan-50 text-cyan-600 rounded-lg">
                        <Users size={20} />
                    </div>
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">The Mission Council</h3>
                        <p className="text-xs text-slate-500">Invite registered users to collaborate on this project.</p>
                    </div>
                </div>

                <div className="p-6 grid gap-6 md:grid-cols-2">
                    {/* Invite form — owner/admin only */}
                    {isOwner ? (
                        <div className="flex flex-col gap-3">
                            <label className="text-xs font-bold text-slate-500 uppercase">Add New Member</label>
                            <div className="flex gap-2">
                                <div className="relative flex-[2]">
                                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                    <input
                                        type="email"
                                        placeholder="user@example.com"
                                        value={inviteEmail}
                                        onChange={e => setInviteEmail(e.target.value)}
                                        onKeyDown={handleInviteKeyDown}
                                        className="w-full pl-9 pr-4 py-2 rounded-xl border border-slate-200 focus:ring-2 focus:ring-cyan-500 outline-none text-sm"
                                    />
                                </div>
                                <select
                                    value={selectedRole}
                                    onChange={e => setSelectedRole(e.target.value as 'EDITOR' | 'VIEWER')}
                                    className="flex-1 px-3 py-2 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-cyan-500 outline-none bg-white font-medium"
                                >
                                    <option value="VIEWER">Viewer</option>
                                    <option value="EDITOR">Editor</option>
                                </select>
                                <button
                                    onClick={handleInvite}
                                    disabled={isInviting || !inviteEmail.trim()}
                                    className="bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2 rounded-xl font-bold text-xs flex items-center gap-2 disabled:bg-slate-300 transition-colors shadow-sm"
                                >
                                    {isInviting
                                        ? <Loader2 className="animate-spin" size={16} />
                                        : <UserPlus size={16} />}
                                    Invite
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col justify-center h-full text-slate-400 text-sm italic bg-slate-50 rounded-xl p-4 border border-dashed border-slate-200">
                            <p>Only the Project Owner or Admin can invite new members.</p>
                        </div>
                    )}

                    {/* Member list */}
                    <div>
                        <label className="text-xs font-bold text-slate-500 uppercase mb-2 block">
                            Current Members ({displayedMembers.length})
                        </label>
                        <div className="space-y-2 max-h-[160px] overflow-y-auto pr-1">
                            {displayedMembers.map(member => {
                                const isMe = member.id === user?.id;
                                const isProjectOwner = member.id === projectOwnerId;
                                const initial = member.full_name?.charAt(0)?.toUpperCase() ?? '?';

                                return (
                                    <div
                                        key={member.id}
                                        className={`flex items-center justify-between p-2 rounded-lg border ${isMe ? 'bg-cyan-50 border-cyan-100' : 'bg-slate-50 border-slate-100'
                                            }`}
                                    >
                                        <div className="flex items-center gap-2 min-w-0">
                                            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${isMe ? 'bg-cyan-200 text-cyan-700' : 'bg-slate-200 text-slate-500'
                                                }`}>
                                                {initial}
                                            </div>
                                            <div className="min-w-0">
                                                <p className="text-xs font-bold text-slate-700 truncate">
                                                    {member.full_name ?? 'Unknown'}
                                                    {isMe && <span className="text-cyan-500 font-normal ml-1">(You)</span>}
                                                </p>
                                            </div>
                                        </div>
                                        <span className={`shrink-0 text-[10px] font-medium px-2 py-0.5 rounded border ${isProjectOwner
                                            ? 'bg-amber-50 text-amber-700 border-amber-100'
                                            : 'bg-white text-slate-500 border-slate-100'
                                            }`}>
                                            {isProjectOwner ? 'Owner' : member.project_role}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </div>
            </section>

            {/* ── Project Wisdom (documents) ───────────────────────────────────────── */}
            <section>
                <div className="flex justify-between items-end border-b border-slate-200 pb-4 mb-4">
                    <div>
                        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                            <Shield className="text-cyan-600" size={20} /> Project Wisdom
                        </h2>
                        <p className="text-slate-500 text-sm">Upload past PRDs, tech specs, or architecture docs.</p>
                    </div>

                    {canManageDocs && (
                        <div>
                            <input
                                ref={fileInputRef}
                                type="file"
                                id="file-upload"
                                className="hidden"
                                accept=".pdf"
                                onChange={handleFileUpload}
                                disabled={isUploading}
                            />
                            <label
                                htmlFor="file-upload"
                                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium cursor-pointer transition shadow-sm text-sm ${isUploading
                                    ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                                    : 'bg-slate-900 hover:bg-black text-white hover:shadow-md'
                                    }`}
                            >
                                {isUploading
                                    ? <><Loader2 className="animate-spin" size={16} /> Processing...</>
                                    : <><Upload size={16} /> Upload PDF</>}
                            </label>
                        </div>
                    )}
                </div>

                <div className="grid grid-cols-1 gap-3">
                    {documents.length === 0 ? (
                        <div className="text-center py-12 bg-slate-50 rounded-xl border-2 border-dashed border-slate-200 text-slate-400">
                            <FileText size={40} className="mx-auto mb-3 opacity-20" />
                            <p className="text-sm font-medium">No documents yet.</p>
                            {canManageDocs && (
                                <p className="text-xs mt-1">Upload a PDF above to give the AI council context.</p>
                            )}
                        </div>
                    ) : (
                        documents.map(doc => (
                            <div
                                key={doc.id}
                                className="flex items-center justify-between p-4 bg-white border border-slate-200 rounded-xl hover:border-cyan-300 hover:shadow-sm transition-all group"
                            >
                                <div className="flex items-center gap-4 min-w-0">
                                    <div className="shrink-0 p-2.5 bg-cyan-50 text-cyan-600 rounded-lg">
                                        <FileText size={18} />
                                    </div>
                                    <div className="min-w-0">
                                        <p className="font-bold text-slate-800 text-sm truncate">{doc.filename}</p>
                                        <div className="flex items-center gap-3 text-xs text-slate-400 mt-0.5">
                                            <span>{new Date(doc.upload_date).toLocaleDateString()}</span>
                                            {doc.chunk_count > 0 && (
                                                <span>{doc.chunk_count} chunks</span>
                                            )}
                                            <IndexingBadge status={statusMap[doc.id]} />
                                        </div>
                                    </div>
                                </div>

                                {canManageDocs && (
                                    <button
                                        onClick={() => setDocToDelete(doc.id)}
                                        className="shrink-0 ml-4 text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
                                        title="Delete document"
                                        aria-label={`Delete ${doc.filename}`}
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                )}
                            </div>
                        ))
                    )}
                </div>
            </section>

            {/* Delete confirmation */}
            <ConfirmModal
                isOpen={!!docToDelete}
                title="Delete Document?"
                message="This action cannot be undone. This document will be permanently removed from the project knowledge base."
                type="danger"
                onClose={() => setDocToDelete(null)}
                onConfirm={executeDelete}
            />

            {/* Feedback modal */}
            <ConfirmModal
                isOpen={feedback.isOpen}
                title={feedback.title}
                message={feedback.message}
                type={feedback.type}
                onClose={() => setFeedback(prev => ({ ...prev, isOpen: false }))}
                onConfirm={() => setFeedback(prev => ({ ...prev, isOpen: false }))}
            />
        </div>
    );
};