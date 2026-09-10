/**
 * Tab-Scoped Session Management for Legal Case Companion.
 *
 * ARCHITECTURAL GUARANTEE:
 * sessionStorage is physically partitioned per browser tab by modern browsers.
 * By storing the session identifier and access token strictly in tab-scoped sessionStorage,
 * independent browser tabs (e.g. Tab A as CLIENT and Tab B as LAWYER) remain completely
 * isolated. Operations in Tab B (login, refresh, logout) can NEVER read, overwrite,
 * or invalidate Tab A's credentials.
 */

const SESSION_ID_KEY = "lcc_session_id";
const ACCESS_TOKEN_KEY = "lcc_access_token";
const REFRESH_TOKEN_KEY = "lcc_refresh_token";

/**
 * Returns or generates a unique UUID for the current browser tab session.
 */
export function getTabSessionId(): string {
  if (typeof window === "undefined") return "ssr-session";
  try {
    let sessionId = sessionStorage.getItem(SESSION_ID_KEY);
    if (!sessionId) {
      sessionId =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `lcc-tab-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      sessionStorage.setItem(SESSION_ID_KEY, sessionId);
    }
    return sessionId;
  } catch (err) {
    console.warn("[LCC-Session] Unable to access sessionStorage for session id:", err);
    return "ephemeral-session";
  }
}

/**
 * Returns the access token scoped strictly to the current browser tab.
 */
export function getSessionAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return sessionStorage.getItem(ACCESS_TOKEN_KEY);
  } catch (err) {
    console.warn("[LCC-Session] Unable to read access token from sessionStorage:", err);
    return null;
  }
}

function _purgeLegacyLocalStorageKeys(): void {
  try {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token");
  } catch {
    // Ignore storage access errors in restricted iframe/sandbox contexts
  }
}

/**
 * Stores the access token in the current browser tab's sessionStorage.
 * Also purges any legacy browser-wide tokens from localStorage to prevent cross-contamination.
 */
export function setSessionAccessToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    getTabSessionId(); // Ensure tab session id is initialized
    sessionStorage.setItem(ACCESS_TOKEN_KEY, token);
    _purgeLegacyLocalStorageKeys();
  } catch (err) {
    console.warn("[LCC-Session] Unable to save access token to sessionStorage:", err);
  }
}

/**
 * Returns the refresh token scoped strictly to the current browser tab.
 */
export function getSessionRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return sessionStorage.getItem(REFRESH_TOKEN_KEY);
  } catch (err) {
    console.warn("[LCC-Session] Unable to read refresh token from sessionStorage:", err);
    return null;
  }
}

/**
 * Stores the refresh token in the current browser tab's sessionStorage.
 */
export function setSessionRefreshToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
  } catch (err) {
    console.warn("[LCC-Session] Unable to save refresh token to sessionStorage:", err);
  }
}

/**
 * Clears the access token from the current browser tab's sessionStorage.
 * Does not mutate credentials in any other browser tab.
 */
export function clearSessionAccessToken(): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(ACCESS_TOKEN_KEY);
    _purgeLegacyLocalStorageKeys();
  } catch (err) {
    console.warn("[LCC-Session] Unable to clear access token from sessionStorage:", err);
  }
}

/**
 * Clears the refresh token from the current browser tab's sessionStorage.
 */
export function clearSessionRefreshToken(): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch (err) {
    console.warn("[LCC-Session] Unable to clear refresh token from sessionStorage:", err);
  }
}

/**
 * Completely clears all tab-scoped credentials for the current tab.
 */
export function clearTabSession(): void {
  clearSessionAccessToken();
  clearSessionRefreshToken();
}

/**
 * Clean up legacy global localStorage keys on application startup.
 */
export function purgeLegacyGlobalStorage(): void {
  if (typeof window === "undefined") return;
  _purgeLegacyLocalStorageKeys();
}

