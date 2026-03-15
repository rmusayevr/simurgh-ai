/**
 * Canonical token storage helpers.
 *
 * Single source of truth for reading and writing the JWT pair that lives in
 * localStorage.  Import from here — never re-implement these helpers inline.
 *
 * Why a plain object instead of a class?
 *   The methods are stateless and have no setup cost, so there is nothing to
 *   instantiate.  The `as const` assertion makes every method readonly at the
 *   type level, preventing accidental reassignment.
 *
 * Why localStorage and not sessionStorage or cookies?
 *   The app targets a research / internal tool audience where tokens must
 *   survive a page refresh but do not need the XSS protection of httpOnly
 *   cookies.  If the threat model changes, this is the only file to update.
 *
 * Key names are intentionally plain strings rather than constants exported
 * separately — there is no value in making the raw key names part of the
 * public API, and centralising access here is the protection we need.
 */

export const TokenStorage = {
    /** Read the current access token, or null if absent. */
    getAccess: (): string | null => localStorage.getItem('access_token'),

    /** Read the current refresh token, or null if absent. */
    getRefresh: (): string | null => localStorage.getItem('refresh_token'),

    /** Persist both tokens atomically (best-effort — localStorage is synchronous). */
    setTokens: (access: string, refresh: string): void => {
        localStorage.setItem('access_token', access);
        localStorage.setItem('refresh_token', refresh);
    },

    /** Remove both tokens — call on logout or auth failure. */
    clear: (): void => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    },
} as const;