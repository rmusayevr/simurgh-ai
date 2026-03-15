/**
 * Centralized React Query key factory.
 *
 * Keeping all keys in one place gives us two important guarantees:
 *
 * 1. No typos — importing a key is a compile-time check; typing the same
 *    string in two files is a silent runtime bug.
 *
 * 2. Precise invalidation — the hierarchical tuple structure lets us
 *    invalidate at any level of specificity:
 *
 *      queryClient.invalidateQueries({ queryKey: queryKeys.projects.all })
 *        → invalidates ALL project queries (list + individual)
 *
 *      queryClient.invalidateQueries({ queryKey: queryKeys.projects.detail(42) })
 *        → invalidates only project 42
 *
 *      queryClient.invalidateQueries({ queryKey: queryKeys.stakeholders.byProject(42) })
 *        → invalidates only stakeholders for project 42
 *
 * Pattern: each entity has an `all` root tuple and factory functions for
 * scoped sub-keys.  This follows the "query key factories" pattern from the
 * TkDodo / TanStack Query documentation.
 */

export const queryKeys = {
    // ── Projects ──────────────────────────────────────────────────────────────
    projects: {
        /** Root key — invalidate to bust all project caches. */
        all: ['projects'] as const,
        /** List with optional filters (e.g. { include_archived: true }). */
        list: (filters?: Record<string, unknown>) =>
            ['projects', 'list', filters] as const,
        /** Single project by ID. */
        detail: (id: string | number) =>
            ['projects', 'detail', String(id)] as const,
    },

    // ── Stakeholders ──────────────────────────────────────────────────────────
    stakeholders: {
        all: ['stakeholders'] as const,
        /** All stakeholders for a given project. */
        byProject: (projectId: string | number) =>
            ['stakeholders', 'project', String(projectId)] as const,
    },
} as const;