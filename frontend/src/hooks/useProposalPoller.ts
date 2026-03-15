import { useEffect } from 'react';
import { api } from '../api/client';
import { ProposalStatus } from '../types';
import type { Proposal } from '../types';

interface UseProposalPollerProps {
    proposalId: number | null;
    status: string | null;
    onCompleted: (proposal: Proposal) => void;
    onFailed: (proposal: Proposal) => void;
}

/**
 * Polls GET /proposals/{id} every 5s while status is PROCESSING.
 * Stops automatically on COMPLETED or FAILED.
 * 404s during commit phase are silently ignored.
 *
 * 5s interval (12 rpm) keeps well within the 200 rpm authenticated
 * rate limit while still delivering results within 5s of completion.
 */
export function useProposalPoller({
    proposalId,
    status,
    onCompleted,
    onFailed,
}: UseProposalPollerProps): void {
    useEffect(() => {
        if (!proposalId || status !== ProposalStatus.PROCESSING) return;

        const interval = setInterval(async () => {
            try {
                const res = await api.get<Proposal>(`/proposals/${proposalId}`);
                const updated = res.data;

                if (updated.status === ProposalStatus.COMPLETED) {
                    clearInterval(interval);
                    onCompleted(updated);
                } else if (updated.status === ProposalStatus.FAILED) {
                    clearInterval(interval);
                    onFailed(updated);
                }
            } catch {
                // 404 while Celery task is committing to DB — safe to continue polling
            }
        }, 5000);

        return () => clearInterval(interval);
    }, [proposalId, status, onCompleted, onFailed]);
}