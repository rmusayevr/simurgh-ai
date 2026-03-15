import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { ProposalStatus } from '../types';
import { hasPermission } from '../config/permissions';
import type { Proposal, ProposalListItem } from '../types';
import type { ProjectRole } from '../config/permissions';

interface UseProjectMissionsResult {
    loading: boolean;
    loadError: boolean;
    activeMissions: Proposal[];
    history: ProposalListItem[];
    historicalDocCount: number;
    currentRole: ProjectRole;
    canCreate: boolean;
    // Setters exposed for optimistic updates in MissionPage / GeneratorTab
    setActiveMissions: React.Dispatch<React.SetStateAction<Proposal[]>>;
    setHistory: React.Dispatch<React.SetStateAction<ProposalListItem[]>>;
    refetch: () => Promise<void>;
    handleCreateDraft: (task: string) => Promise<Proposal | null>;
    handleDeleteMission: (missionId: number) => Promise<void>;
    handleUploadFile: (missionId: number, fileList: FileList) => Promise<void>;
    handleDeleteDoc: (missionId: number, docId: number) => Promise<void>;
    handleRetry: (missionId: number) => Promise<void>;
    onMissionExecuted: (missionId: number) => void;
    onMissionCompleted: (completed: Proposal) => void;
    onMissionFailed: (updated: Proposal) => void;
}

export function useProjectMissions(projectId: string): UseProjectMissionsResult {
    const { user } = useAuth();

    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState(false);
    const [projectOwnerId, setProjectOwnerId] = useState<number | null>(null);
    const [historicalDocCount, setHistoricalDocCount] = useState(0);
    const [activeMissions, setActiveMissions] = useState<Proposal[]>([]);
    const [history, setHistory] = useState<ProposalListItem[]>([]);

    const currentRole: ProjectRole = useMemo(() => {
        if (!user || !projectOwnerId) return 'VIEWER';
        return user.id === projectOwnerId ? 'OWNER' : 'VIEWER';
    }, [user, projectOwnerId]);

    const canCreate = hasPermission(currentRole, 'EDIT_CONTENT');

    // ── Fetch ──────────────────────────────────────────────────────────────────
    const refetch = useCallback(async () => {
        setLoading(true);
        setLoadError(false);
        try {
            const [projRes, docsRes, activeRes, histRes] = await Promise.all([
                api.get<{ owner_id: number }>(`/projects/${projectId}`),
                api.get<unknown[]>(`/projects/${projectId}/documents`),
                api.get<Proposal[]>(`/proposals/project/${projectId}/active`),
                api.get<ProposalListItem[]>(`/proposals/project/${projectId}`),
            ]);
            setProjectOwnerId(projRes.data.owner_id);
            setHistoricalDocCount(docsRes.data.length);
            setActiveMissions(activeRes.data);
            const seen = new Set<number>();
            setHistory(histRes.data.filter(
                (p: ProposalListItem) => {
                    if (seen.has(p.id)) return false;
                    seen.add(p.id);
                    return p.status === ProposalStatus.COMPLETED || p.status === ProposalStatus.FAILED;
                }
            ));
        } catch {
            setLoadError(true);
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => { refetch(); }, [refetch]);

    // ── Create draft ───────────────────────────────────────────────────────────
    const handleCreateDraft = useCallback(async (task: string): Promise<Proposal | null> => {
        const description = task.trim();
        if (!description) return null;
        const res = await api.post<Proposal>('/proposals/draft', {
            project_id: Number(projectId),
            task_description: description,
        });
        setActiveMissions((prev: Proposal[]) => [res.data, ...prev]);
        return res.data;
    }, [projectId]);

    // ── Delete mission ─────────────────────────────────────────────────────────
    const handleDeleteMission = useCallback(async (missionId: number) => {
        await api.delete(`/proposals/${missionId}`);
        setActiveMissions((prev: Proposal[]) => prev.filter((m: Proposal) => m.id !== missionId));
    }, []);

    // ── Upload task document ───────────────────────────────────────────────────
    const handleUploadFile = useCallback(async (missionId: number, fileList: FileList) => {
        const uploads = Array.from(fileList).map(async file => {
            const formData = new FormData();
            formData.append('file', file);
            const res = await api.post<Proposal>(
                `/proposals/${missionId}/documents`,
                formData,
                { headers: { 'Content-Type': undefined } }
            );
            return res.data;
        });
        const results = await Promise.all(uploads);
        const latest = results[results.length - 1];
        if (latest) {
            setActiveMissions((prev: Proposal[]) => prev.map((m: Proposal) => m.id === missionId ? latest : m));
        }
    }, []);

    // ── Delete task document (optimistic) ─────────────────────────────────────
    const handleDeleteDoc = useCallback(async (missionId: number, docId: number) => {
        setActiveMissions((prev: Proposal[]) => prev.map((m: Proposal) =>
            m.id === missionId
                ? { ...m, task_documents: m.task_documents?.filter(d => d.id !== docId) }
                : m
        ));
        try {
            await api.delete(`/proposals/${missionId}/documents/${docId}`);
        } catch {
            refetch();
        }
    }, [refetch]);

    // ── Retry failed ───────────────────────────────────────────────────────────
    const handleRetry = useCallback(async (missionId: number) => {
        await api.post(`/proposals/${missionId}/retry`, {});
        setActiveMissions((prev: Proposal[]) => prev.map((m: Proposal) =>
            m.id === missionId ? { ...m, status: ProposalStatus.PROCESSING } : m
        ));
    }, []);

    // ── Optimistic status flip after execute ───────────────────────────────────
    // Called by MissionPage immediately after POST /execute succeeds so the
    // poller (which watches activeDraft.status) activates without a round-trip.
    const onMissionExecuted = useCallback((missionId: number) => {
        setActiveMissions((prev: Proposal[]) => prev.map((m: Proposal) =>
            m.id === missionId ? { ...m, status: ProposalStatus.PROCESSING } : m
        ));
    }, []);

    // ── Poller callbacks ───────────────────────────────────────────────────────
    const onMissionCompleted = useCallback((completed: Proposal) => {
        setActiveMissions((prev: Proposal[]) => prev.filter((m: Proposal) => m.id !== completed.id));
        setHistory((prev: ProposalListItem[]) => {
            if (prev.some(p => p.id === completed.id)) return prev;
            return [completed as unknown as ProposalListItem, ...prev];
        });
    }, []);

    const onMissionFailed = useCallback((updated: Proposal) => {
        setActiveMissions((prev: Proposal[]) => prev.map((m: Proposal) => m.id === updated.id ? updated : m));
    }, []);

    return {
        loading, loadError,
        activeMissions, history, historicalDocCount,
        currentRole, canCreate,
        setActiveMissions, setHistory,
        refetch,
        handleCreateDraft,
        handleDeleteMission,
        handleUploadFile,
        handleDeleteDoc,
        handleRetry,
        onMissionExecuted,
        onMissionCompleted,
        onMissionFailed,
    };
}