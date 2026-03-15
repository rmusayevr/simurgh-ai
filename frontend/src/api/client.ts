import axios, { type InternalAxiosRequestConfig } from 'axios';
import { jwtDecode } from 'jwt-decode';
import { TokenStorage } from '../utils/tokenStorage';
import type {
    AdminUser,
    DebateResult,
    Proposal,
    PromptTemplate,
    ProposalStatus,
    AdminProject,
    VerificationData,
    StartDebatePayload,
    ParticipantCreate,
    ParticipantRead,
    QuestionnaireCreate,
    QuestionnaireRead,
    QuestionnaireListRead,
    QuestionnaireExportSummary,
    PersonaCodingCreate,
    PersonaCoding,
    PersonaCodingSummary,
    ExitSurveyCreate,
    ExitSurveyRead,
    ThematicTheme,
} from '../types';

// ─── Base URL ─────────────────────────────────────────────────────────────────
const baseURL = import.meta.env.PROD
    ? '/api/v1'
    : 'http://localhost:8000/api/v1';

// ─── Axios instance ───────────────────────────────────────────────────────────
export const api = axios.create({
    baseURL,
    headers: { 'Content-Type': 'application/json' },
});

// ─── Token refresh state ──────────────────────────────────────────────────────
// Single in-flight refresh promise shared across all concurrent 401 retries.
// Any request that arrives while a refresh is in progress waits on this promise
// instead of firing its own POST /auth/refresh — eliminating the thundering-herd
// problem that caused 31 simultaneous refresh calls and a 429.

type QueueEntry = { resolve: (token: string) => void; reject: (err: unknown) => void };

let refreshPromise: Promise<string> | null = null;
let failedQueue: QueueEntry[] = [];

const processQueue = (error: unknown, token: string | null = null): void => {
    failedQueue.forEach((entry) => {
        if (error) entry.reject(error);
        else entry.resolve(token!);
    });
    failedQueue = [];
};

// How many seconds before JWT expiry we proactively refresh.
// This must be less than the access token TTL but large enough to cover typical
// request latency. 30 s is conservative — adjust if ACCESS_TOKEN_EXPIRE_MINUTES
// is very short (e.g. 1 min).
const TOKEN_EXPIRY_BUFFER_SECONDS = 30;

const isTokenExpiredOrExpiring = (token: string): boolean => {
    try {
        const { exp } = jwtDecode<{ exp: number }>(token);
        if (typeof exp !== 'number') return false;
        const nowSeconds = Date.now() / 1000;
        const secondsRemaining = exp - nowSeconds;
        if (secondsRemaining < TOKEN_EXPIRY_BUFFER_SECONDS) {
            console.debug('[auth] Token expiring soon, proactive refresh triggered', {
                exp, nowSeconds, secondsRemaining, buffer: TOKEN_EXPIRY_BUFFER_SECONDS
            });
            return true;
        }
        return false;
    } catch (e) {
        console.warn('[auth] Failed to decode token for expiry check', e);
        return false;
    }
};

/**
 * Exchange the stored refresh token for a new access token.
 * Returns the new access token string.
 * Reuses an in-flight refresh if one is already running (deduplication).
 */
const refreshAccessToken = (): Promise<string> => {
    if (refreshPromise) return refreshPromise;

    refreshPromise = (async (): Promise<string> => {
        try {
            const refreshToken = TokenStorage.getRefresh();
            if (!refreshToken) throw new Error('No refresh token stored');

            const { data } = await axios.post<{ access_token: string; refresh_token: string }>(
                `${baseURL}/auth/refresh`,
                { refresh_token: refreshToken }
            );

            TokenStorage.setTokens(data.access_token, data.refresh_token);
            processQueue(null, data.access_token);
            return data.access_token;
        } catch (err) {
            processQueue(err, null);
            TokenStorage.clear();
            if (!['/login', '/study'].includes(window.location.pathname)) {
                window.location.href = '/login';
            }
            throw err;
        } finally {
            // Only clear the shared promise after it settles so late arrivals
            // still coalesce onto this attempt rather than firing a new one.
            refreshPromise = null;
        }
    })();

    return refreshPromise;
};

// ─── Request interceptor: proactive token refresh ─────────────────────────────
// Checks expiry BEFORE the request leaves the browser. If the token is about to
// expire (within TOKEN_EXPIRY_BUFFER_SECONDS), refreshes it first. This prevents
// the reactive 401 → refresh → retry cycle for the common case of a token that
// simply aged out, and dramatically reduces calls to /auth/refresh under load.
api.interceptors.request.use(
    async (config: InternalAxiosRequestConfig) => {
        // Skip auth endpoints — they either don't need a token or supply their own.
        const isAuthEndpoint = config.url?.includes('/auth/');
        if (isAuthEndpoint) return config;

        const token = TokenStorage.getAccess();
        if (!token) return config;

        // Refresh proactively if the token is expiring soon.
        if (isTokenExpiredOrExpiring(token)) {
            try {
                const freshToken = await refreshAccessToken();
                config.headers.Authorization = `Bearer ${freshToken}`;
                return config;
            } catch {
                // refreshAccessToken already cleared tokens and redirected.
                // Return the config as-is; the request will 401 and be caught below.
                return config;
            }
        }

        config.headers.Authorization = `Bearer ${token}`;
        return config;
    },
    (error: unknown) => Promise.reject(error)
);

// ─── Response interceptor: reactive 401 handler ───────────────────────────────
// Handles the edge case where a token expired between the proactive check and the
// server processing the request (e.g. clock skew, long-running upload). Under
// normal conditions the request interceptor above prevents most 401s from ever
// reaching this handler.
api.interceptors.response.use(
    (response) => response,
    async (error: unknown) => {
        if (!axios.isAxiosError(error)) return Promise.reject(error);

        const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

        // Maintenance mode — surface immediately, no retry.
        if (error.response?.status === 503) return Promise.reject(error);

        // A failed refresh itself — break the loop immediately.
        if (originalRequest.url?.includes('/auth/refresh')) return Promise.reject(error);

        // Not a 401, or we already retried once — pass through.
        if (error.response?.status !== 401 || originalRequest._retry) return Promise.reject(error);

        // On auth pages the 401 IS the answer (wrong password, etc.) — don't refresh.
        if (['/login', '/study'].includes(window.location.pathname)) return Promise.reject(error);

        originalRequest._retry = true;

        try {
            // refreshAccessToken() deduplicates: if a refresh is already in
            // flight every concurrent caller awaits the same promise.
            const freshToken = await refreshAccessToken();
            originalRequest.headers.Authorization = `Bearer ${freshToken}`;
            return api(originalRequest);
        } catch (refreshError) {
            return Promise.reject(refreshError);
        }
    }
);


// ─── Admin API ────────────────────────────────────────────────────────────────
export const adminApi = {
    // ─── System & Health ───
    getLogs: (lines = 100) =>
        api.get<{ logs: string[] }>('/admin/logs', { params: { lines } }),

    getWorkerHealth: () =>
        api.get<{ status: 'online' | 'offline' }>('/admin/health/worker'),

    getStats: () =>
        api.get<Record<string, unknown>>('/admin/health').then((r) => r.data),

    // ─── Users ───
    getUsers: (skip = 0, limit = 100) =>
        api.get<AdminUser[]>('/admin/users', { params: { skip, limit } }),

    createParticipant: (data: { email: string; password: string; full_name?: string }) =>
        api.post('/admin/users', data),
    updateUser: (userId: number, data: Partial<AdminUser>) =>
        api.patch<AdminUser>(`/admin/users/${userId}`, data),

    toggleUserStatus: (userId: number, isActive: boolean) =>
        api.patch<AdminUser>(`/admin/users/${userId}`, { is_active: isActive }),
    deleteUser: (userId: number) =>
        api.delete<void>(`/admin/users/${userId}`),

    // ─── Projects ───
    getProjects: (skip = 0, limit = 100) =>
        api.get<AdminProject[]>('/admin/projects', { params: { skip, limit } }),

    deleteProject: (projectId: number) =>
        api.delete<void>(`/admin/projects/${projectId}`),

    // ─── Proposals ───
    getProposals: (skip = 0, limit = 100) =>
        api.get<Proposal[]>('/admin/proposals', { params: { skip, limit } }),

    updateProposalStatus: (proposalId: number, status: ProposalStatus) =>
        api.patch<Proposal>(`/admin/proposals/${proposalId}/status`, null, {
            params: { status },
        }),

    deleteProposal: (proposalId: number) =>
        api.delete<void>(`/admin/proposals/${proposalId}`),

    // ─── System Config & Analytics ───
    getSettings: () =>
        api.get<Record<string, unknown>>('/admin/settings'),

    updateSettings: (settings: Record<string, unknown>) =>
        api.patch<Record<string, unknown>>('/admin/settings', settings),

    getVerification: () =>
        api.get<VerificationData>('/admin/rag/verification').then(r => r.data),

    getAnalytics: () =>
        api.get<Record<string, unknown>>('/admin/analytics'),
} as const;

// ─── Prompt API ───────────────────────────────────────────────────────────────
export const promptApi = {
    getTemplates: () =>
        api.get<PromptTemplate[]>('/admin/prompts'),

    updateTemplate: (id: number, data: Partial<PromptTemplate>) =>
        api.patch<PromptTemplate>(`/admin/prompts/${id}`, data),
} as const;

// ─── Public API ───────────────────────────────────────────────────────────────
export interface SystemStatus {
    maintenance_mode: boolean;
    allow_registrations: boolean;
    email_enabled: boolean;
    thesis_mode: boolean;
    status: string;
    version: string;
}

export const publicApi = {
    getSystemStatus: () =>
        api.get<SystemStatus>('/public/status'),
} as const;

// ─── Debate API ───────────────────────────────────────────────────────────────
export const debateApi = {
    startDebate: (proposalId: number, payload: StartDebatePayload) =>
        api.post<DebateResult>(`/debates/proposals/${proposalId}/start_debate`, payload)
            .then(r => r.data),

    getLatestDebate: (proposalId: number) =>
        api.get<DebateResult>(`/debates/proposals/${proposalId}/history`)
            .then(r => r.data),

    synthesizeProposals: (debateId: string) =>
        api.post<DebateResult>(`/debates/${debateId}/synthesize`)
            .then(r => r.data),
} as const;

// ─── Experiment API  (prefix: /experiments) ───────────────────────────────────

export const experimentApi = {
    /** POST /experiments/register — register user as research participant */
    register: (data: ParticipantCreate) =>
        api.post<ParticipantRead>('/experiments/register', data)
            .then(r => r.data),

    /** GET /experiments/participant/me — get own participant record (resume on refresh) */
    getMyParticipant: () =>
        api.get<ParticipantRead>('/experiments/participant/me')
            .then(r => r.data),
} as const;

// ─── Evaluation API  (prefix: /evaluation) ────────────────────────────────────

export const evaluationApi = {
    /** POST /evaluation/responses — participant submits questionnaire */
    submitResponse: (data: QuestionnaireCreate) =>
        api.post<QuestionnaireRead>('/evaluation/responses', data)
            .then(r => r.data),

    /** GET /evaluation/responses — researcher list view */
    listResponses: (params?: { scenario_id?: number; valid_only?: boolean }) =>
        api.get<QuestionnaireListRead[]>('/evaluation/responses', { params })
            .then(r => r.data),

    /** GET /evaluation/responses/{id} */
    getResponse: (responseId: string) =>
        api.get<QuestionnaireRead>(`/evaluation/responses/${responseId}`)
            .then(r => r.data),

    /** PATCH /evaluation/responses/{id} — flag / add quality note */
    updateResponse: (responseId: string, data: { is_valid?: boolean; quality_note?: string }) =>
        api.patch<QuestionnaireRead>(`/evaluation/responses/${responseId}`, data)
            .then(r => r.data),

    /** POST /evaluation/responses/{id}/flag */
    flagInvalid: (responseId: string, reason: string) =>
        api.post<{ success: boolean; message: string }>(
            `/evaluation/responses/${responseId}/flag`,
            null,
            { params: { reason } }
        ).then(r => r.data),

    /** GET /evaluation/statistics?scenario_id= — summary stats for Chapter 5 */
    getStatistics: (scenarioId?: number) =>
        api.get<Record<string, unknown>>('/evaluation/statistics', {
            params: scenarioId ? { scenario_id: scenarioId } : undefined,
        }).then(r => r.data),

    /** GET /evaluation/export — full export for SPSS/R */
    exportResponses: (validOnly = true) =>
        api.get<QuestionnaireExportSummary>('/evaluation/export', {
            params: { valid_only: validOnly },
        }).then(r => r.data),
} as const;

// ─── Thesis API  (prefix: /thesis) ────────────────────────────────────────────

export const thesisApi = {
    // ── Persona Coding (RQ2) ────────────────────────────────────────────────

    /** POST /thesis/persona-coding */
    submitCoding: (data: PersonaCodingCreate) =>
        api.post<PersonaCoding>('/thesis/persona-coding', data)
            .then(r => r.data),

    /** GET /thesis/persona-coding/verification-sample — fetch uncoded turns for manual coding */
    getVerificationSample: (batchSize = 10): Promise<import('../types').Transcript[]> =>
        api.get<import('../types').Transcript[]>('/thesis/persona-coding/verification-sample', {
            params: { batch_size: batchSize },
        }).then(r => r.data),

    /** POST /thesis/persona-coding/verification-submit — submit a verification coding */
    submitVerification: (data: PersonaCodingCreate): Promise<PersonaCoding> =>
        api.post<PersonaCoding>('/thesis/persona-coding/verification-submit', data)
            .then(r => r.data),

    /** GET /thesis/persona-coding/debate/{debate_id} */
    getDebateCodings: (debateId: string, coderId?: number) =>
        api.get<PersonaCoding[]>(`/thesis/persona-coding/debate/${debateId}`, {
            params: coderId ? { coder_id: coderId } : undefined,
        }).then(r => r.data),

    /** PATCH /thesis/persona-coding/{coding_id} */
    updateCoding: (codingId: string, data: Partial<PersonaCodingCreate>) =>
        api.patch<PersonaCoding>(`/thesis/persona-coding/${codingId}`, data)
            .then(r => r.data),

    /** DELETE /thesis/persona-coding/{coding_id} */
    deleteCoding: (codingId: string) =>
        api.delete(`/thesis/persona-coding/${codingId}`),

    /** GET /thesis/persona-coding/debate/{debate_id}/summary — RQ2 report */
    getDebateCodingSummary: (debateId: string) =>
        api.get<PersonaCodingSummary>(`/thesis/persona-coding/debate/${debateId}/summary`)
            .then(r => r.data),

    /** POST /thesis/persona-coding/debate/{debate_id}/write-scores */
    writeConsistencyScores: (debateId: string) =>
        api.post<{ success: boolean; debate_id: string; scores: Record<string, number> }>(
            `/thesis/persona-coding/debate/${debateId}/write-scores`
        ).then(r => r.data),

    // ── Exports ─────────────────────────────────────────────────────────────

    /** GET /thesis/export/persona-codings → CSV download */
    downloadPersonaCodings: async (debateId?: string) => {
        const response = await api.get('/thesis/export/persona-codings', {
            params: debateId ? { debate_id: debateId } : undefined,
            responseType: 'blob',
        });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        link.setAttribute('download', `persona_codings_${date}.csv`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
    },

    /** GET /thesis/export/thesis-data → ZIP download (all CSVs) */
    downloadThesisZip: async () => {
        const response = await api.get('/thesis/export/thesis-data', {
            responseType: 'blob',
        });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        link.setAttribute('download', `thesis_data_${date}.zip`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
    },

    getTrustMetrics: () =>
        evaluationApi.getStatistics().then(stats => stats),

    getConsensusMetrics: () =>
        evaluationApi.getStatistics().then(stats => stats),

    exportData: () => thesisApi.downloadThesisZip(),

    /** POST /thesis/thematic-analysis — run LLM-assisted theme extraction on exit survey responses */
    runThematicAnalysis: (field: 'what_worked_well' | 'what_could_improve' | 'additional_comments') =>
        api.post<{ field: string; response_count: number; themes: ThematicTheme[] }>(
            `/thesis/thematic-analysis?field=${field}`
        ).then(res => res.data),
} as const;

// ─── Exit Survey API ──────────────────────────────────────────────────────────

export const exitSurveyApi = {
    /** POST /experiment/exit-survey — submit post-experiment exit survey */
    submit: (data: ExitSurveyCreate) =>
        api.post<ExitSurveyRead>('/experiment/exit-survey', data)
            .then(r => r.data),

    /** GET /experiment/exit-survey/me — check if already submitted (idempotency) */
    getMy: () =>
        api.get<ExitSurveyRead>('/experiment/exit-survey/me')
            .then(r => r.data),
} as const;

// ─── Experiment Data API (admin only) ────────────────────────────────────────
// Add this block to frontend/src/api/client.ts alongside the other API objects.
// Prefix: /admin/experiment-data  (all endpoints require superuser JWT)

export const experimentDataApi = {
    /** GET /admin/experiment-data/overview */
    getOverview: () =>
        api.get<unknown>('/experiment-data/overview').then(r => r.data),

    /** GET /experiment-data/participants */
    getParticipants: (opts?: { completed_only?: boolean; condition_order?: string }) =>
        api.get<ParticipantRead[]>('/experiment-data/participants', { params: opts }).then(r => r.data),

    /** GET /experiment-data/participants/{id} */
    getParticipantDetail: (id: number) =>
        api.get<ParticipantRead>(`/experiment-data/participants/${id}`).then(r => r.data),

    /** GET /experiment-data/questionnaires */
    getQuestionnaires: (opts?: {
        condition?: 'BASELINE' | 'MULTIAGENT';
        scenario_id?: number;
        valid_only?: boolean;
        include_open_ended?: boolean;
    }) =>
        api.get<QuestionnaireListRead[]>('/experiment-data/questionnaires', { params: opts }).then(r => r.data),

    /** GET /experiment-data/debates */
    getDebates: (opts?: { consensus_only?: boolean; include_turns?: boolean }) =>
        api.get<DebateResult[]>('/experiment-data/debates', { params: opts }).then(r => r.data),

    /** GET /experiment-data/exit-surveys */
    getExitSurveys: () =>
        api.get<ExitSurveyRead[]>('/experiment-data/exit-surveys').then(r => r.data),

    /** GET /experiment-data/rq-summary */
    getRQSummary: () =>
        api.get<QuestionnaireExportSummary>('/experiment-data/rq-summary').then(r => r.data),

    /** DELETE /experiment-data/reset?confirm=CONFIRM_RESET */
    resetAllData: (keepParticipants = false) =>
        api.delete<unknown>('/experiment-data/reset', {
            params: { confirm: 'CONFIRM_RESET', keep_participants: keepParticipants },
        }).then(r => r.data),

    /** DELETE /experiment-data/participant/{id} */
    deleteParticipant: (id: number) =>
        api.delete<unknown>(`/experiment-data/participant/${id}`).then(r => r.data),

    /** PATCH /experiment-data/participant/{id}/invalidate?reason=... */
    invalidateParticipant: (id: number, reason: string) =>
        api.patch<unknown>(
            `/experiment-data/participant/${id}/invalidate`,
            null,
            { params: { reason } }
        ).then(r => r.data),
} as const;