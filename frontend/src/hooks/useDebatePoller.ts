import { useState, useEffect, useRef, useCallback } from 'react';
import { debateApi } from '../api/client';
import { ProposalStatus } from '../types';
import type { DebateTurn } from '../types';

interface UseDebatePollerProps {
    /** Proposal ID to poll debate history for. Pass null to disable. */
    proposalId: number | null;
    /** Current proposal status — polling only runs while PROCESSING. */
    status: string | null;
    /** Called once when the debate completes (consensus_reached or all turns done). */
    onComplete?: (turns: DebateTurn[], consensusReached: boolean) => void;
}

interface UseDebatePollerResult {
    /** Accumulated debate turns in arrival order. */
    turns: DebateTurn[];
    /** Whether the council reached consensus. */
    consensusReached: boolean;
    /** Total turns expected (from the API response). */
    totalTurns: number;
    /** True while the first fetch is in flight (before any turns arrive). */
    initialLoading: boolean;
    /** True if the debate is fully complete. */
    isComplete: boolean;
    /** Any error message from the latest failed poll. */
    error: string | null;
}

/**
 * Polls GET /debates/proposals/{id}/history every 3s while proposal
 * status is PROCESSING. Accumulates turns as they arrive and stops
 * automatically when the debate is complete.
 *
 * Key decisions:
 *   - 3s interval — tighter than the proposal poller (5s) because debate
 *     turns arrive quickly and the live feed feels stale at 5s.
 *   - Merges turns by turn_number so duplicate polls are idempotent.
 *   - Stops polling as soon as the history endpoint returns a completed
 *     session (completed_at is set) regardless of proposal status.
 *   - 404s during the first few seconds are expected while the Celery task
 *     is starting — silently ignored.
 *   - Uses a ref for the interval ID so cleanup is always correct even if
 *     the component re-renders during an in-flight fetch.
 */
export function useDebatePoller({
    proposalId,
    status,
    onComplete,
}: UseDebatePollerProps): UseDebatePollerResult {
    const [turns, setTurns] = useState<DebateTurn[]>([]);
    const [consensusReached, setConsensusReached] = useState(false);
    const [totalTurns, setTotalTurns] = useState(0);
    const [initialLoading, setInitialLoading] = useState(false);
    const [isComplete, setIsComplete] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Stable ref so the interval callback always has the latest onComplete
    const onCompleteRef = useRef(onComplete);
    useEffect(() => { onCompleteRef.current = onComplete; }, [onComplete]);

    // Track whether we have completed to avoid calling onComplete twice
    const completedRef = useRef(false);

    const reset = useCallback(() => {
        setTurns([]);
        setConsensusReached(false);
        setTotalTurns(0);
        setInitialLoading(false);
        setIsComplete(false);
        setError(null);
        completedRef.current = false;
    }, []);

    useEffect(() => {
        // Only poll when processing
        if (!proposalId || status !== ProposalStatus.PROCESSING) {
            // If we were polling and now status changed away from PROCESSING
            // (e.g. completed externally), keep the turns but stop polling
            return;
        }

        reset();
        setInitialLoading(true);

        const intervalId = setInterval(async () => {
            try {
                const data = await debateApi.getLatestDebate(proposalId);

                setError(null);
                setInitialLoading(false);

                if (data.debate_history?.length) {
                    // Merge by turn_number — idempotent on duplicate polls
                    setTurns(prev => {
                        const existing = new Set(prev.map(t => t.turn_number));
                        const newTurns = data.debate_history.filter(
                            t => !existing.has(t.turn_number)
                        );
                        return newTurns.length > 0
                            ? [...prev, ...newTurns].sort((a, b) => a.turn_number - b.turn_number)
                            : prev;
                    });
                }

                setTotalTurns(data.total_turns ?? 0);
                setConsensusReached(data.consensus_reached ?? false);

                // Debate is complete when completed_at is set on the session
                const debateComplete = !!data.completed_at;
                if (debateComplete && !completedRef.current) {
                    completedRef.current = true;
                    setIsComplete(true);
                    clearInterval(intervalId);
                    onCompleteRef.current?.(
                        data.debate_history ?? [],
                        data.consensus_reached ?? false
                    );
                }
            } catch (err: unknown) {
                const status = (err as { response?: { status?: number } })?.response?.status;
                // 404 while Celery is still starting — safe to continue polling
                if (status === 404) {
                    return;
                }
                setInitialLoading(false);
                setError('Failed to fetch debate history');
            }
        }, 3000);

        // Fire immediately so the first turn appears without waiting 3s
        (async () => {
            try {
                const data = await debateApi.getLatestDebate(proposalId);
                setError(null);
                setInitialLoading(false);
                if (data.debate_history?.length) {
                    setTurns(
                        [...data.debate_history].sort((a, b) => a.turn_number - b.turn_number)
                    );
                }
                setTotalTurns(data.total_turns ?? 0);
                setConsensusReached(data.consensus_reached ?? false);

                if (!!data.completed_at && !completedRef.current) {
                    completedRef.current = true;
                    setIsComplete(true);
                    clearInterval(intervalId);
                    onCompleteRef.current?.(
                        data.debate_history ?? [],
                        data.consensus_reached ?? false
                    );
                }
            } catch {
                // 404 on initial fetch — debate not started yet, interval will retry
                setInitialLoading(false);
            }
        })();

        return () => clearInterval(intervalId);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [proposalId, status]);

    return { turns, consensusReached, totalTurns, initialLoading, isComplete, error };
}