import {
  getSessionAccessToken,
  setSessionAccessToken,
  getSessionRefreshToken,
  setSessionRefreshToken,
  clearTabSession,
  getTabSessionId,
} from "./session";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined"
    ? ""
    : process.env.NODE_ENV === "production"
    ? ""
    : "http://127.0.0.1:8000");

interface RequestOptions extends RequestInit {
  requireAuth?: boolean;
  _retry?: boolean;
}

interface RawErrorPayload {
  message?: string;
  detail?: string | unknown;
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
}

export class ApiError extends Error {
  public code?: string;
  public details?: unknown;
  public status: number;

  constructor(status: number, data: unknown) {
    const raw = data as RawErrorPayload | undefined;
    let msg =
      raw?.error?.message ||
      raw?.message ||
      (typeof raw?.detail === "string"
        ? raw.detail
        : raw?.detail
        ? JSON.stringify(raw.detail)
        : "");

    if (!msg) {
      if (status === 0) {
        msg = "Unable to reach the Legal Case Companion server. Check that the backend is running.";
      } else if (status === 401) {
        msg = "Invalid email or password.";
      } else if (status === 403) {
        msg = "You do not have permission to perform this action.";
      } else if (status === 404) {
        msg = "The requested resource was not found.";
      } else if (status === 409) {
        msg = "An account with this information already exists.";
      } else if (status === 422) {
        msg = "Please check the entered information.";
      } else if (status === 429) {
        msg = "Too many attempts. Please wait and try again.";
      } else if (status >= 500) {
        msg = "Something went wrong on the server. Please try again.";
      } else {
        msg = `API Error: ${status}`;
      }
    }

    super(msg);
    this.name = "ApiError";
    this.status = status;
    this.code = raw?.error?.code;
    this.details = raw?.error?.details;
  }
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

let isRefreshing = false;
let refreshSubscribers: ((token: string | null) => void)[] = [];

function onRefreshed(token: string | null) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

export async function performTokenRefresh(): Promise<string | null> {
  try {
    const csrfToken = getCookie("csrf_token");
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (csrfToken) {
      headers["X-CSRF-Token"] = csrfToken;
    }

    const refreshToken = getSessionRefreshToken();
    const payload = refreshToken ? { refresh_token: refreshToken } : {};

    const res = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers,
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      return null;
    }

    const data = await res.json();
    if (data?.access_token) {
      setSessionAccessToken(data.access_token);
      if (data?.refresh_token) {
        setSessionRefreshToken(data.refresh_token);
      }
      return data.access_token;
    }
    return null;
  } catch (err) {
    console.warn("Token refresh failed:", err);
    return null;
  }
}

async function fetchWithAuth(url: string, options: RequestOptions = {}): Promise<any> {
  const { requireAuth = true, _retry = false, ...fetchOptions } = options;
  const headers = new Headers(fetchOptions.headers);

  fetchOptions.credentials = "include";

  if (typeof window !== "undefined") {
    if (requireAuth) {
      const token = getSessionAccessToken();
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
    }

    const csrfToken = getCookie("csrf_token");
    const method = (fetchOptions.method || "GET").toUpperCase();
    if (csrfToken && !["GET", "HEAD", "OPTIONS"].includes(method)) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  if (fetchOptions.body && !headers.has("Content-Type") && !(fetchOptions.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const targetUrl = url.startsWith("http://") || url.startsWith("https://") ? url : `${BASE_URL}${url}`;

  let response: Response;
  try {
    response = await fetch(targetUrl, {
      ...fetchOptions,
      headers,
    });
  } catch (err: unknown) {
    console.error("Fetch network failure:", err);
    throw new ApiError(0, {
      error: {
        code: "NETWORK_ERROR",
        message: "Unable to reach the Legal Case Companion server. Check that the backend is running.",
      },
    });
  }

  // Handle 401 Automatic Token Refresh and Retry
  if (
    response.status === 401 &&
    requireAuth &&
    !_retry &&
    !url.includes("/api/v1/auth/login") &&
    !url.includes("/api/v1/auth/refresh") &&
    typeof window !== "undefined"
  ) {
    if (!isRefreshing) {
      isRefreshing = true;
      const newToken = await performTokenRefresh();
      isRefreshing = false;
      onRefreshed(newToken);

      if (newToken) {
        return fetchWithAuth(url, { ...options, _retry: true });
      } else {
        clearTabSession();
        const sessionId = getTabSessionId();
        window.dispatchEvent(
          new CustomEvent(`lcc:session-expired:${sessionId}`, { detail: { sessionId } })
        );
        window.dispatchEvent(
          new CustomEvent("lcc:session-expired", { detail: { sessionId } })
        );
      }
    } else {
      // Queue concurrent requests while token is actively refreshing
      return new Promise((resolve, reject) => {
        refreshSubscribers.push((newToken: string | null) => {
          if (newToken) {
            resolve(fetchWithAuth(url, { ...options, _retry: true }));
          } else {
            reject(new ApiError(401, { message: "Session expired" }));
          }
        });
      });
    }
  }

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      errorData = { message: "An unexpected error occurred" };
    }
    throw new ApiError(response.status, errorData);
  }

  if (response.status === 204) return null;

  return response.json();
}

export const apiClient = {
  get: (url: string, options?: RequestOptions) =>
    fetchWithAuth(url, { ...options, method: "GET" }),
  post: (url: string, body: unknown, options?: RequestOptions) =>
    fetchWithAuth(url, {
      ...options,
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),
  patch: (url: string, body: unknown, options?: RequestOptions) =>
    fetchWithAuth(url, {
      ...options,
      method: "PATCH",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),
  put: (url: string, body: unknown, options?: RequestOptions) =>
    fetchWithAuth(url, {
      ...options,
      method: "PUT",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }),
  delete: (url: string, options?: RequestOptions) =>
    fetchWithAuth(url, { ...options, method: "DELETE" }),
};

