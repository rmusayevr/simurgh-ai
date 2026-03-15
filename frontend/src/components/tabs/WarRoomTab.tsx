import React, { useCallback, useState } from 'react';
import {
    ArrowLeft, Target, Trash2, FileText, Plus, Loader2,
    Gavel, Zap, AlertCircle, ChevronRight, FileSearch,
    Pencil, Check, X, MessageSquare
} from 'lucide-react';
import type { Proposal, UserProfile } from '../../types';
import { ProposalStatus } from '../../types';
import { hasPermission, type ProjectRole } from '../../config/permissions';
import { api } from '../../api/client';
import { ConfirmModal } from '../modals/ConfirmModal';
import { HintTooltip } from '../onboarding/HintTooltip';
import { DebateTranscript } from '../DebateTranscript';
import { useDebatePoller } from '../../hooks/useDebatePoller';

interface WarRoomTabProps {
    activeDraft: Proposal | null;
    docCount: number;
    stakeholders: UserProfile[];
    currentUser: UserProfile | null;
    userRole: ProjectRole;
    projectOwnerId: number | null;
    isUploading: boolean;
    loading: boolean;
    handleUploadFile: (files: FileList | null) => void;
    handleDeleteDoc: (id: number) => void;
    handleCancelDraft: () => void;
    onStartNew: () => void;
    onExecuted: () => void;
}

export const WarRoomTab: React.FC<WarRoomTabProps> = ({
    activeDraft,
    isUploading,
    userRole,
    handleUploadFile,
    handleDeleteDoc,
    handleCancelDraft,
    onStartNew,
    onExecuted,
}) => {
    const canConvene = hasPermission(userRole, 'CONVENE_COUNCIL');
    const canUpload = hasPermission(userRole, 'EDIT_CONTENT');

    const [isExecuting, setIsExecuting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    // Editable objective
    const [isEditingObjective, setIsEditingObjective] = useState(false);
    const [editedObjective, setEditedObjective] = useState('');
    const [isSavingObjective, setIsSavingObjective] = useState(false);
    const [objectiveError, setObjectiveError] = useState<string | null>(null);
    const [localTaskDescription, setLocalTaskDescription] = useState<string | null>(null);

    const displayedDescription = localTaskDescription ?? activeDraft?.task_description ?? '';

    const handleStartEditObjective = useCallback(() => {
        setEditedObjective(displayedDescription);
        setObjectiveError(null);
        setIsEditingObjective(true);
    }, [displayedDescription]);

    const handleCancelEditObjective = useCallback(() => {
        setIsEditingObjective(false);
        setEditedObjective('');
        setObjectiveError(null);
    }, []);

    const handleSaveObjective = useCallback(async () => {
        if (!activeDraft) return;
        const trimmed = editedObjective.trim();
        if (trimmed.length < 10) {
            setObjectiveError('Objective must be at least 10 characters.');
            return;
        }
        setIsSavingObjective(true);
        setObjectiveError(null);
        try {
            await api.patch(`/proposals/${activeDraft.id}/draft`, { task_description: trimmed });
            setLocalTaskDescription(trimmed);
            setIsEditingObjective(false);
        } catch {
            setObjectiveError('Failed to save. Please try again.');
        } finally {
            setIsSavingObjective(false);
        }
    }, [activeDraft, editedObjective]);

    const handleConveneCouncil = useCallback(async () => {
        if (!activeDraft) return;
        setError(null);
        setIsExecuting(true);
        try {
            await api.post(`/proposals/${activeDraft.id}/execute`, {});
            onExecuted();
        } catch (err: unknown) {
            const error = err as { response?: { status?: number; data?: { detail?: string } } };
            const status = error?.response?.status;
            const detail = error?.response?.data?.detail;
            setError(
                status === 422
                    ? 'Validation error. Please check your inputs and try again.'
                    : detail ? `Error: ${detail}` : 'Failed to start the debate. Please try again.'
            );
            setIsExecuting(false);
        }
    }, [activeDraft, onExecuted]);

    // ── Live debate transcript ───────────────────────────────────────────────────
    // Hook must be called unconditionally (Rules of Hooks) — the hook itself
    // handles the null proposalId and non-PROCESSING status cases gracefully.
    const debateStatus = activeDraft && (activeDraft.status === ProposalStatus.PROCESSING || isExecuting)
        ? ProposalStatus.PROCESSING
        : null;

    const {
        turns,
        consensusReached,
        totalTurns,
        initialLoading: debateInitialLoading,
        isComplete: debateComplete,
        error: debateError,
    } = useDebatePoller({
        proposalId: activeDraft?.id ?? null,
        status: debateStatus,
    });

    if (!activeDraft) {
        return (
            <div className="flex flex-col items-center justify-center py-24 bg-slate-50 rounded-[2rem] border-2 border-dashed border-slate-200 animate-in fade-in duration-300">
                <div className="w-20 h-20 bg-white border border-slate-100 shadow-sm text-slate-400 rounded-full flex items-center justify-center mb-6">
                    <Zap size={32} />
                </div>
                <h3 className="text-xl font-bold text-slate-800 mb-2">No Active Session</h3>
                <p className="text-slate-500 mb-8 max-w-sm text-center">No debate session is currently selected. Start a new session to begin.</p>
                <button onClick={onStartNew} className="px-6 py-3 bg-cyan-600 text-white rounded-xl font-bold hover:bg-cyan-700 transition-colors shadow-sm flex items-center gap-2">
                    Start a New Session <ChevronRight size={18} />
                </button>
            </div>
        );
    }

    if (activeDraft.status === ProposalStatus.PROCESSING || isExecuting) {
        return (
            <div className="bg-white rounded-3xl border border-slate-200 shadow-sm animate-in fade-in duration-300 overflow-hidden">
                {/* Header */}
                <div className="px-8 pt-7 pb-5 border-b border-slate-100">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-xl bg-cyan-50 flex items-center justify-center">
                                <MessageSquare size={18} className="text-cyan-600" />
                            </div>
                            <div>
                                <h3 className="text-base font-black text-slate-900">The Council is Deliberating</h3>
                                <p className="text-xs text-slate-400 mt-0.5">
                                    {debateComplete
                                        ? 'Debate complete — generating proposals...'
                                        : 'Generating proposals typically takes 1–2 minutes'}
                                </p>
                            </div>
                        </div>
                        {/* Live indicator */}
                        {!debateComplete && (
                            <div className="flex items-center gap-2 text-xs font-bold text-cyan-600">
                                <span className="w-2 h-2 bg-cyan-500 rounded-full animate-pulse" />
                                Live
                            </div>
                        )}
                        {debateComplete && (
                            <div className="flex items-center gap-2 text-xs font-bold text-emerald-600">
                                <span className="w-2 h-2 bg-emerald-500 rounded-full" />
                                Debate complete
                            </div>
                        )}
                    </div>

                    {/* Progress bar */}
                    {totalTurns > 0 && (
                        <div className="mt-4">
                            <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1.5">
                                <span>Debate progress</span>
                                <span>{turns.length} / {totalTurns} turns</span>
                            </div>
                            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-cyan-500 rounded-full transition-all duration-500"
                                    style={{ width: `${Math.round((turns.length / totalTurns) * 100)}%` }}
                                />
                            </div>
                        </div>
                    )}
                </div>

                {/* Transcript scroll area */}
                <div className="px-8 py-6 max-h-[520px] overflow-y-auto">
                    <DebateTranscript
                        turns={turns}
                        consensusReached={consensusReached}
                        totalTurns={totalTurns}
                        initialLoading={debateInitialLoading}
                        isComplete={debateComplete}
                        error={debateError}
                        live={true}
                    />
                </div>

                {/* Footer — objective reminder */}
                <div className="px-8 py-4 border-t border-slate-100 bg-slate-50/50">
                    <p className="text-[11px] text-slate-400">
                        <span className="font-bold text-slate-500">Objective: </span>
                        {activeDraft.task_description}
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            <div className="flex items-center justify-between">
                <button
                    onClick={onStartNew}
                    className="flex items-center gap-2 text-slate-400 hover:text-slate-800 font-bold text-xs uppercase tracking-wide transition-colors bg-white px-4 py-2 rounded-full border border-slate-200 shadow-sm"
                >
                    <ArrowLeft size={14} /> Session Control
                </button>
            </div>

            {error && (
                <div className="flex items-center gap-4 p-5 bg-red-50 border border-red-200 rounded-2xl text-red-800 animate-in slide-in-from-top-2">
                    <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center shrink-0">
                        <AlertCircle size={20} className="text-red-600" />
                    </div>
                    <div>
                        <p className="font-bold text-sm mb-0.5">Generation Error</p>
                        <p className="text-sm text-red-600/90">{error}</p>
                    </div>
                </div>
            )}

            <div className="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-8 animate-in slide-in-from-bottom-4 duration-500">

                    {/* ── Session Objective (editable) ─────────────────────── */}
                    <div className="mb-10">
                        <div className="flex items-center justify-between mb-4">
                            <h4 className="flex items-center gap-2 text-xs font-black text-slate-400 uppercase tracking-widest">
                                <Target size={14} /> Session Objective
                            </h4>
                            {canUpload && !isEditingObjective && (
                                <button
                                    onClick={handleStartEditObjective}
                                    className="flex items-center gap-1.5 text-xs font-bold text-slate-400 hover:text-cyan-600 transition-colors px-3 py-1.5 rounded-lg hover:bg-cyan-50"
                                >
                                    <Pencil size={12} /> Edit
                                </button>
                            )}
                        </div>

                        {isEditingObjective ? (
                            <div className="space-y-3">
                                <textarea
                                    className="w-full px-5 py-4 text-base rounded-2xl border border-cyan-300 focus:ring-4 focus:ring-cyan-500/10 focus:border-cyan-500 outline-none h-40 resize-none bg-cyan-50/30 focus:bg-white transition"
                                    value={editedObjective}
                                    onChange={e => setEditedObjective(e.target.value)}
                                    disabled={isSavingObjective}
                                    autoFocus
                                />
                                {objectiveError && (
                                    <p className="text-xs text-red-500 font-medium">{objectiveError}</p>
                                )}
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={handleSaveObjective}
                                        disabled={isSavingObjective}
                                        className="flex items-center gap-1.5 px-4 py-2 bg-cyan-600 text-white text-sm font-bold rounded-xl hover:bg-cyan-700 transition disabled:opacity-50"
                                    >
                                        {isSavingObjective ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                                        Save
                                    </button>
                                    <button
                                        onClick={handleCancelEditObjective}
                                        disabled={isSavingObjective}
                                        className="flex items-center gap-1.5 px-4 py-2 text-slate-500 text-sm font-bold rounded-xl hover:bg-slate-100 transition"
                                    >
                                        <X size={14} /> Cancel
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="bg-cyan-50/50 p-6 rounded-2xl border border-cyan-100">
                                <p className="text-lg text-slate-800 font-medium leading-relaxed">{displayedDescription}</p>
                            </div>
                        )}
                    </div>

                    {/* ── Context Documents ────────────────────────────────── */}
                    <div className="mb-10">
                        <h4 className="flex items-center gap-2 text-xs font-black text-slate-400 uppercase tracking-widest mb-4">
                            <FileSearch size={14} /> Context Documents
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {activeDraft.task_documents?.map(doc => (
                                <div key={doc.id} className="bg-white p-4 rounded-2xl border border-slate-200 flex justify-between items-center group shadow-sm hover:shadow-md hover:border-cyan-300 transition-all">
                                    <div className="flex items-center gap-4 overflow-hidden">
                                        <div className="w-10 h-10 bg-slate-50 border border-slate-100 text-slate-500 rounded-xl flex items-center justify-center shrink-0">
                                            <FileText size={18} />
                                        </div>
                                        <div className="truncate">
                                            <p className="text-sm font-bold text-slate-800 truncate">{doc.filename}</p>
                                            <p className="text-[11px] text-slate-400 font-medium">
                                                Uploaded by {doc.uploader?.full_name ?? 'Unknown'}
                                            </p>
                                        </div>
                                    </div>
                                    {canUpload && (
                                        <button
                                            onClick={() => handleDeleteDoc(doc.id)}
                                            className="w-8 h-8 flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-red-50 text-red-400 hover:text-red-600 rounded-lg transition-all shrink-0"
                                        >
                                            <Trash2 size={16} />
                                        </button>
                                    )}
                                </div>
                            ))}

                            {canUpload && (
                                <label className="flex flex-col items-center justify-center gap-2 p-6 rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50 hover:bg-cyan-50 hover:border-cyan-300 cursor-pointer transition-all group">
                                    {isUploading ? (
                                        <Loader2 size={24} className="animate-spin text-cyan-500 mb-1" />
                                    ) : (
                                        <div className="w-10 h-10 bg-white border border-slate-100 rounded-full flex items-center justify-center mb-1 group-hover:scale-110 transition-transform">
                                            <Plus size={20} className="text-slate-400 group-hover:text-cyan-600" />
                                        </div>
                                    )}
                                    <span className="text-sm font-bold text-slate-500 group-hover:text-cyan-700">
                                        {isUploading ? 'Uploading...' : 'Upload Document'}
                                    </span>
                                    {!isUploading && (
                                        <input
                                            type="file" multiple accept=".pdf" className="hidden"
                                            onChange={e => handleUploadFile(e.target.files)}
                                        />
                                    )}
                                </label>
                            )}
                        </div>
                    </div>

                    {/* ── Council Info Banner ──────────────────────────────── */}
                    <div className="mb-8 p-5 bg-slate-50 rounded-2xl border border-slate-200">
                        <p className="text-sm font-bold text-slate-700 mb-3">The Council of Agents will generate 3 distinct proposals:</p>
                        <div className="grid grid-cols-3 gap-3">
                            {[
                                { label: 'Legacy Keeper', desc: 'Stability & proven patterns', color: 'bg-amber-50 border-amber-100 text-amber-700' },
                                { label: 'Innovator', desc: 'Modern architecture & scale', color: 'bg-purple-50 border-purple-100 text-purple-700' },
                                { label: 'Mediator', desc: 'Balanced pragmatic approach', color: 'bg-blue-50 border-blue-100 text-blue-700' },
                            ].map(({ label, desc, color }) => (
                                <div key={label} className={`p-3 rounded-xl border ${color}`}>
                                    <p className="font-bold text-xs mb-1">{label}</p>
                                    <p className="text-xs opacity-75">{desc}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* ── Action Buttons ───────────────────────────────────── */}
                    <div className="pt-6 border-t border-slate-100 flex flex-col items-center gap-4">
                        <div className="flex items-center gap-2">
                            <p className="text-xs text-slate-400 font-bold uppercase tracking-widest">Ready to generate</p>
                            <HintTooltip
                                title="What happens next"
                                text="Three AI personas (Legacy Keeper, Innovator, Mediator) will debate your objective and each write a distinct architectural proposal. Takes 60–180 seconds."
                                side="top"
                                iconSize={13}
                            />
                        </div>
                        <button
                            onClick={handleConveneCouncil}
                            disabled={!canConvene || isExecuting || isEditingObjective}
                            className={`w-full max-w-md py-4 rounded-2xl font-black text-lg flex justify-center items-center gap-3 transition-all ${canConvene && !isExecuting && !isEditingObjective
                                ? 'bg-slate-900 text-white shadow-xl shadow-slate-900/20 hover:bg-black hover:-translate-y-0.5 active:translate-y-0'
                                : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                                }`}
                        >
                            {isExecuting ? <Loader2 className="animate-spin w-5 h-5" /> : <Gavel size={20} />}
                            {isExecuting ? 'Starting Debate...' : isEditingObjective ? 'Save objective first' : canConvene ? 'Start Debate' : 'Unauthorized'}
                        </button>

                        {canConvene && (
                            <>
                                <button
                                    onClick={() => setShowDeleteConfirm(true)}
                                    className="text-xs text-slate-400 hover:text-red-500 font-bold flex items-center gap-1.5 transition-colors"
                                >
                                    <Trash2 size={12} /> Delete Session Draft
                                </button>
                                <ConfirmModal
                                    isOpen={showDeleteConfirm}
                                    onClose={() => setShowDeleteConfirm(false)}
                                    onConfirm={() => { setShowDeleteConfirm(false); handleCancelDraft(); }}
                                    title="Delete Session Draft?"
                                    message="This action will wipe all related documents and objectives. This cannot be undone."
                                    type="danger"
                                />
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};