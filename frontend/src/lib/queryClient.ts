/**
 * Shared React Query client.
 *
 * Exported as a singleton so the same cache is shared across the whole app.
 * All defaults here can be overridden per-query via the `useQuery` options.
 *
 * Key decisions:
 *   staleTime: 60s  — data is considered fresh for 60 seconds.  This prevents
 *                     refetches on every tab focus for data that rarely changes
 *                     (project list, stakeholders, etc.).  Set to 0 on individual
 *                     queries where real-time accuracy is critical.
 *
 *   retry: 1        — retry once on network errors before showing an error state.
 *                     The Axios interceptor already handles 401 / token refresh,
 *                     so retrying twice would be redundant for auth failures.
 *
 *   refetchOnWindowFocus: true  — default React Query behaviour; kept as-is.
 *                                 Overridden to false for long-running AI tasks
 *                                 (proposals, debates) that are polled explicitly.
 */

import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 60_000,   // 1 minute
            retry: 1,
        },
    },
});