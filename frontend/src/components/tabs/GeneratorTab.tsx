import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Loader2, AlertCircle } from 'lucide-react';

import { ProposalStatus } from '../../types';
import type { GeneratorTabProps, Proposal } from '../../types';

import { useProjectMissions } from '../../hooks/useProjectMissions';
import { useProposalPoller } from '../../hooks/useProposalPoller';

import { ConfirmModal } from './../modals/ConfirmModal';
import { GeneratorNavigation } from './../GeneratorNavigation';
import { HistoryTab } from './../tabs/HistoryTab';
import { NewMissionTab } from './../tabs/NewMissionTab';
import { MissionLobby } from './../tabs/MissionLobby';

// ─── Types ────────────────────────────────────────────────────────────────────

type TabView = 'new' | 'active' | 'history';

interface ConfirmState {
    isOpen: boolean;
    title: string;
    message: string;
    type: 'danger' | 'info';
    onConfirm: () => void;
}

const CLOSED_CONFIRM: ConfirmState = {
    isOpen: false, title: '', message: '', type: 'info', onConfirm: () => { },
};

// ─── Derive generator sub-tab from URL path ───────────────────────────────────
const getGeneratorTabFromPath = (pathname: string): TabView => {
    if (pathname.endsWith('/new')) return 'new';
    if (pathname.endsWith('/history')) return 'history';
    return 'active';
};

// ─── Component ────────────────────────────────────────────────────────────────

export const GeneratorTab: React.FC<GeneratorTabProps> = ({ projectId }) => {
    const navigate = useNavigate();
    const location = useLocation();

    // ── Data + mission actions ─────────────────────────────────────────────────
    const {
        loading, loadError,
        canCreate,
        activeMissions,
        history,
        handleCreateDraft,
        onMissionCompleted,
        onMissionFailed,
        refetch,
    } = useProjectMissions(projectId);

    // ── Navigation — driven by URL sub-path ────────────────────────────────────
    const activeMainTab = getGeneratorTabFromPath(location.pathname);

    const setActiveMainTab = useCallback((tab: TabView) => {
        navigate(`/project/${projectId}/generator/${tab}`, { replace: true });
    }, [navigate, projectId]);

    // ── New session form ───────────────────────────────────────────────────────
    const [task, setTask] = useState('');
    const [creating, setCreating] = useState(false);
    const [confirmState, setConfirmState] = useState<ConfirmState>(CLOSED_CONFIRM);

    // ── Auto-redirect to New Session when project has no activity ───────────────
    useEffect(() => {
        if (loading) return;
        if (activeMainTab === 'active' && activeMissions.length === 0 && history.length === 0) {
            setActiveMainTab('new');
        }
    }, [loading, activeMainTab, activeMissions.length, history.length, setActiveMainTab]);

    // ── Lobby-level poller: keeps badge counts accurate ───────────────────────
    const processingMission = activeMissions.find((m: Proposal) => m.status === ProposalStatus.PROCESSING) ?? null;

    useProposalPoller({
        proposalId: processingMission?.id ?? null,
        status: processingMission?.status ?? null,
        onCompleted: (completed: Proposal) => {
            onMissionCompleted(completed);
            // Note: onMissionCompleted already adds to history — do NOT call setHistory again here
            navigate(`/project/${projectId}/proposal/${completed.id}`);
        },
        onFailed: onMissionFailed,
    });

    // ── Create mission ─────────────────────────────────────────────────────────
    const handleCreate = useCallback(async () => {
        const description = task.trim() || `Untitled session — ${new Date().toLocaleDateString()}`;
        setCreating(true);
        try {
            const draft = await handleCreateDraft(description);
            if (draft) navigate(`/project/${projectId}/mission/${draft.id}`);
        } catch {
            setConfirmState({
                isOpen: true,
                title: 'Error',
                message: 'Failed to create session. Please try again.',
                type: 'danger',
                onConfirm: () => { },
            });
        } finally {
            setCreating(false);
            setTask('');
        }
    }, [task, projectId, handleCreateDraft, navigate]);

    // ── Loading / error ────────────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-slate-400">
                <Loader2 className="animate-spin mb-2" size={32} />
                <p className="text-sm font-medium">Loading sessions...</p>
            </div>
        );
    }

    if (loadError) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-slate-400 gap-4">
                <AlertCircle size={32} />
                <p className="text-sm font-medium">Failed to load sessions.</p>
                <button onClick={refetch} className="text-cyan-600 font-bold hover:underline text-sm">Retry</button>
            </div>
        );
    }

    // ── Render ─────────────────────────────────────────────────────────────────
    return (
        <div className="pb-20">
            <GeneratorNavigation
                activeTab={activeMainTab}
                setActiveTab={setActiveMainTab}
                activeCount={activeMissions.length}
                historyCount={history.length}
                canCreate={canCreate}
            />

            {activeMainTab === 'new' && canCreate && (
                <NewMissionTab
                    task={task}
                    setTask={setTask}
                    handleCreateDraft={handleCreate}
                    loading={creating}
                />
            )}

            {activeMainTab === 'active' && (
                <MissionLobby
                    missions={activeMissions}
                    onSelect={(m: Proposal) => navigate(`/project/${projectId}/mission/${m.id}`)}
                    onCreateNew={() => setActiveMainTab('new')}
                    canCreate={canCreate}
                />
            )}

            {activeMainTab === 'history' && (
                <HistoryTab
                    history={history}
                />
            )}

            <ConfirmModal
                isOpen={confirmState.isOpen}
                title={confirmState.title}
                message={confirmState.message}
                type={confirmState.type}
                onClose={() => setConfirmState(CLOSED_CONFIRM)}
                onConfirm={() => {
                    confirmState.onConfirm();
                    setConfirmState(CLOSED_CONFIRM);
                }}
            />
        </div>
    );
};