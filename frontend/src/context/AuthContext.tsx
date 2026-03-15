import React, {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useRef,
    useState,
} from 'react';
import { jwtDecode } from 'jwt-decode';
import { api } from '../api/client';
import { TokenStorage } from '../utils/tokenStorage';
import type { AuthContextType, JwtPayload, UserProfile } from '../types';

/** How many seconds before expiry we proactively refresh. */
const REFRESH_BUFFER_SECONDS = 30;

const isTokenExpiredOrExpiring = (token: string): boolean => {
    try {
        const { exp } = jwtDecode<JwtPayload>(token);
        return exp < Date.now() / 1000 + REFRESH_BUFFER_SECONDS;
    } catch {
        return true; // Treat malformed token as expired
    }
};

// ─── Context ──────────────────────────────────────────────────────────────────
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ─── Provider ─────────────────────────────────────────────────────────────────
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<UserProfile | null>(null);
    const [loading, setLoading] = useState(true);

    // Prevent double-init in React StrictMode
    const initRan = useRef(false);

    // ── Fetch profile — accepts an explicit token so the caller is never
    //    dependent on the storage state at the moment the request fires.
    //    When called from login() the fresh token is passed directly,
    //    avoiding a race where initAuth()'s logout() clears storage between
    //    TokenStorage.setTokens() and the axios request interceptor reading it.
    const fetchProfile = useCallback(async (accessToken?: string): Promise<void> => {
        const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined;
        const res = await api.get<UserProfile>('/auth/me', { headers });
        setUser(res.data);
    }, []);

    // ── Logout: revoke server-side token, then clear local state ──────────────
    const logout = useCallback((): void => {
        const refreshToken = TokenStorage.getRefresh();

        // Fire-and-forget: revoke server-side. Backend requires auth header (current
        // access token is still valid at this point, so the interceptor handles it).
        if (refreshToken) {
            api
                .post<void>('/auth/logout', { refresh_token: refreshToken })
                .catch(() => {
                    // Ignore — we clear local state regardless
                });
        }

        TokenStorage.clear();
        setUser(null);
    }, []);

    // ── Login: exchange credentials for tokens, then load profile ─────────────
    const login = useCallback(async (username: string, password: string): Promise<void> => {
        const params = new URLSearchParams();
        params.append('username', username);
        params.append('password', password);

        const res = await api.post<{ access_token: string; refresh_token: string }>(
            '/auth/token',
            params,
            { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
        );

        const { access_token, refresh_token } = res.data;
        TokenStorage.setTokens(access_token, refresh_token);

        // Pass the token explicitly — do not rely on TokenStorage being readable
        // at request time. initAuth() running concurrently could call logout()
        // and clear storage between our setTokens() call and the axios interceptor
        // reading it, causing /auth/me to fire with no Authorization header.
        await fetchProfile(access_token);
    }, [fetchProfile]);

    // ── Initialise: restore session on mount ──────────────────────────────────
    useEffect(() => {
        if (initRan.current) return;
        initRan.current = true;

        const initAuth = async (): Promise<void> => {
            const accessToken = TokenStorage.getAccess();
            const refreshToken = TokenStorage.getRefresh();

            // No tokens → not logged in
            if (!accessToken || !refreshToken) {
                setLoading(false);
                return;
            }

            try {
                // Proactively refresh if the access token is about to expire.
                // The axios interceptor handles mid-session 401s, but on cold load
                // we need to check before making the first authenticated request.
                let tokenToUse = accessToken;
                if (isTokenExpiredOrExpiring(accessToken)) {
                    const refreshRes = await api.post<{ access_token: string; refresh_token: string }>(
                        '/auth/refresh',
                        { refresh_token: refreshToken }
                    );
                    tokenToUse = refreshRes.data.access_token;
                    TokenStorage.setTokens(tokenToUse, refreshRes.data.refresh_token);
                }

                // Pass token explicitly for same reason as login() above.
                await fetchProfile(tokenToUse);
            } catch {
                // Session could not be restored (expired refresh token, revoked, etc.).
                // Only clear storage if login() hasn't already taken over — i.e. if
                // the tokens in storage are still the stale ones we started with.
                // If they've changed it means a concurrent login() succeeded and we
                // must not wipe its freshly-stored tokens.
                const currentAccess = TokenStorage.getAccess();
                if (currentAccess === accessToken) {
                    TokenStorage.clear();
                    setUser(null);
                }
            } finally {
                setLoading(false);
            }
        };

        initAuth();
    }, [fetchProfile, logout]);

    return (
        <AuthContext.Provider
            value={{
                isAuthenticated: !!user,
                user,
                loading,
                login,
                logout,
                refreshProfile: () => fetchProfile(),
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};

// ─── Hook ─────────────────────────────────────────────────────────────────────
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = (): AuthContextType => {
    const context = useContext(AuthContext);
    if (!context) throw new Error('useAuth must be used within AuthProvider');
    return context;
};