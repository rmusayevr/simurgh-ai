/**
 * SessionPage.tsx  (renamed from MissionPage)
 *
 * Wrapper page for an active debate session workspace (DebateSessionTab).
 *
 * Responsibilities:
 *  - Renders DebateSessionTab for DRAFT sessions (staging + start debate)
 *  - Polls proposal status every 3s while PROCESSING
 *  - On COMPLETED → navigates to ProposalDetailPage (/project/:id/proposal/:proposalId)
 *  - On FAILED → shows retry / discard UI
 */

import { useCallback, useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { ProposalStatus } from '../types';
import type { Proposal } from '../types';
import { useProjectMissions } from '../hooks/useProjectMissions';
import { useProposalPoller } from '../hooks/useProposalPoller';
import { WarRoomTab } from '../components/tabs/WarRoomTab';
import { ConfirmModal } from '../components/modals/ConfirmModal';

export const SessionPage = () => {
    const { id: projectId, missionId } = useParams<{ id: string; missionId: string }>();
    const navigate = useNavigate();
    const { user } = useAuth();

    const {
        loading,
        loadError,
        currentRole,
        historicalDocCount,
        activeMissions,
        handleUploadFile,
        handleDeleteDoc,
        handleRetry,
        handleDeleteMission,
        onMissionExecuted,
        onMissionCompleted,
        onMissionFailed,
    } = useProjectMissions(projectId!);

    const [isUploading, setIsUploading] = useState(false);
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [isNavigating, setIsNavigating] = useState(false);

    const activeDraft =
        activeMissions.find((m: Proposal) => m.id === Number(missionId)) ?? null;

    const activeDraftRef = useRef<Proposal | null>(activeDraft);
    useEffect(() => {
        if (activeDraft) activeDraftRef.current = activeDraft;
    }, [activeDraft]);

    // ── Poller: fires every 3s while PROCESSING ───────────────────────────────
    const onCompleted = useCallback(
        (completed: Proposal) => {
            setIsNavigating(true);
            onMissionCompleted(completed);
            navigate(`/project/${projectId}/proposal/${completed.id}`, {
                replace: true,
            });
        },
        [projectId, navigate, onMissionCompleted]
    );

    const onFailed = useCallback(
        (updated: Proposal) => {
            onMissionFailed(updated);
        },
        [onMissionFailed]
    );

    useProposalPoller({
        proposalId: activeDraft?.id ?? null,
        status: activeDraft?.status ?? null,
        onCompleted,
        onFailed,
    });

    // ── Upload wrapper (adds UI loading state) ────────────────────────────────
    const handleUpload = useCallback(
        async (fileList: FileList | null) => {
            if (!fileList || !activeDraft) return;
            setIsUploading(true);
            try {
                await handleUploadFile(activeDraft.id, fileList);
            } finally {
                setIsUploading(false);
            }
        },
        [activeDraft, handleUploadFile]
    );

    // ── Delete draft ──────────────────────────────────────────────────────────
    const handleCancelDraft = useCallback(() => {
        setConfirmOpen(true);
    }, []);

    const executeDelete = useCallback(async () => {
        if (!activeDraft) return;
        setConfirmOpen(false);
        await handleDeleteMission(activeDraft.id);
        navigate(`/project/${projectId}/generator/active`, { replace: true });
    }, [activeDraft, projectId, navigate, handleDeleteMission]);

    // ── Loading ───────────────────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <Loader2 size={40} className="animate-spin text-cyan-600" />
            </div>
        );
    }

    // ── Not found ─────────────────────────────────────────────────────────────
    if (!isNavigating && (loadError || !activeDraft)) {
        return (
            <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4">
                <AlertCircle size={40} className="text-slate-400" />
                <p className="text-slate-700 font-medium">
                    {loadError ? 'Failed to load session.' : 'Session not found or already completed.'}
                </p>
                <button
                    onClick={() => navigate(`/project/${projectId}/generator/active`)}
                    className="px-4 py-2 bg-cyan-600 text-white rounded-lg text-sm font-medium hover:bg-cyan-700 transition"
                >
                    Back to Sessions
                </button>
            </div>
        );
    }

    // ── Resolved draft: safe to use below (activeDraft may be null when isNavigating) ──
    const draft = activeDraft ?? activeDraftRef.current;
    if (!draft) return null;

    // ── Failed state ──────────────────────────────────────────────────────────
    if (draft.status === ProposalStatus.FAILED) {
        return (
            <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center py-20 text-center">
                <div className="bg-red-100 p-4 rounded-full mb-4">
                    <AlertCircle className="w-12 h-12 text-red-600" />
                </div>
                <h3 className="text-xl font-semibold text-slate-900 mb-2">
                    Generation Failed
                </h3>
                {draft.error_message && (
                    <p className="text-sm text-red-500 mb-4 max-w-md bg-red-50 border border-red-200 p-3 rounded-lg">
                        {draft.error_message}
                    </p>
                )}
                <p className="text-slate-500 max-w-md mb-8">
                    The Council of Agents encountered a critical error. Please retry or discard this draft.
                </p>
                <div className="flex gap-4">
                    <button
                        onClick={handleCancelDraft}
                        className="px-4 py-2 text-slate-500 hover:text-red-600 font-medium transition-colors"
                    >
                        Discard Draft
                    </button>
                    <button
                        onClick={() => handleRetry(draft.id)}
                        className="flex items-center gap-2 px-6 py-2 bg-red-600 text-white rounded-lg font-bold hover:bg-red-700 transition"
                    >
                        <RefreshCw className="w-4 h-4" />
                        Retry Generation
                    </button>
                </div>

                <ConfirmModal
                    isOpen={confirmOpen}
                    title="Discard Session?"
                    message="This will permanently delete the workspace and all uploaded documents. This action cannot be undone."
                    type="danger"
                    onClose={() => setConfirmOpen(false)}
                    onConfirm={executeDelete}
                />
            </div>
        );
    }

    // ── Debate Workspace (DRAFT or PROCESSING) ────────────────────────────────────────
    return (
        <div className="min-h-screen bg-slate-50 p-6 md:p-8">
            <WarRoomTab
                activeDraft={draft}
                docCount={historicalDocCount}
                stakeholders={[]}
                currentUser={user}
                userRole={currentRole}
                projectOwnerId={null}
                isUploading={isUploading}
                loading={false}
                handleUploadFile={handleUpload}
                handleDeleteDoc={(docId: number) =>
                    handleDeleteDoc(draft.id, docId)
                }
                handleCancelDraft={handleCancelDraft}
                onStartNew={() =>
                    navigate(`/project/${projectId}/generator/active`)
                }
                onExecuted={() => onMissionExecuted(draft.id)}
            />

            <ConfirmModal
                isOpen={confirmOpen}
                title="Discard Session?"
                message="This will permanently delete the workspace and all uploaded documents. This action cannot be undone."
                type="danger"
                onClose={() => setConfirmOpen(false)}
                onConfirm={executeDelete}
            />
        </div>
    );
};