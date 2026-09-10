import {
  getSessionAccessToken,
  setSessionAccessToken,
  getSessionRefreshToken,
  setSessionRefreshToken,
  clearTabSession,
  getTabSessionId,
} from "./session";

const BASE_URL =
  typeof window !== "undefined"
    ? ""
    : process.env.BACKEND_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://127.0.0.1:8000";

interface RequestOptions extends RequestInit {
  requireAuth?: boolean;
  _retry?: boolean;
  responseType?: "json" | "blob";
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
        msg = "Unable to connect to the Legal Case Companion server. Check that the backend is running.";
      } else if (status === 401) {
        msg = "Session expired or authentication required. Please sign in.";
      } else if (status === 403) {
        msg = "You do not have permission to perform this action.";
      } else if (status === 404) {
        msg = "The requested resource was not found.";
      } else if (status === 409) {
        msg = "A conflict occurred with existing records.";
      } else if (status === 422) {
        msg = "The request contains invalid or incomplete fields.";
      } else if (status === 429) {
        msg = "Too many requests. Please wait a moment before trying again.";
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

export class NetworkError extends ApiError {
  constructor(message = "Unable to reach the Legal Case Companion server. Please check your network connection.") {
    super(0, { error: { code: "NETWORK_ERROR", message } });
    this.name = "NetworkError";
  }
}

export class AuthenticationError extends ApiError {
  constructor(message = "Session expired or authentication required. Please sign in again.") {
    super(401, { error: { code: "UNAUTHORIZED", message } });
    this.name = "AuthenticationError";
  }
}

export class AuthorizationError extends ApiError {
  constructor(message = "You do not have permission to perform this action.") {
    super(403, { error: { code: "FORBIDDEN", message } });
    this.name = "AuthorizationError";
  }
}

export class NotFoundError extends ApiError {
  constructor(message = "The requested resource could not be found.") {
    super(404, { error: { code: "NOT_FOUND", message } });
    this.name = "NotFoundError";
  }
}

export class ConflictError extends ApiError {
  constructor(message = "A conflict occurred with existing records.") {
    super(409, { error: { code: "CONFLICT", message } });
    this.name = "ConflictError";
  }
}

export class ValidationError extends ApiError {
  constructor(message = "The request contains invalid or incomplete fields.", details?: unknown) {
    super(422, { error: { code: "VALIDATION_ERROR", message, details } });
    this.name = "ValidationError";
  }
}

export class RateLimitError extends ApiError {
  constructor(message = "Too many requests. Please wait a moment before trying again.") {
    super(429, { error: { code: "RATE_LIMITED", message } });
    this.name = "RateLimitError";
  }
}

export class ServerError extends ApiError {
  constructor(status = 500, message = "Something went wrong on the server. Please try again.") {
    super(status, { error: { code: "SERVER_ERROR", message } });
    this.name = "ServerError";
  }
}

export function createSpecificApiError(status: number, data: unknown): ApiError {
  const raw = data as RawErrorPayload | undefined;
  const msg = raw?.error?.message || raw?.message;
  if (status === 0) return new NetworkError(msg);
  if (status === 401) return new AuthenticationError(msg);
  if (status === 403) return new AuthorizationError(msg);
  if (status === 404) return new NotFoundError(msg);
  if (status === 409) return new ConflictError(msg);
  if (status === 422) return new ValidationError(msg, raw?.error?.details);
  if (status === 429) return new RateLimitError(msg);
  if (status >= 500) return new ServerError(status, msg);
  return new ApiError(status, data);
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
    console.warn("Fetch network failure on", targetUrl, err);
    throw new NetworkError(
      "Unable to reach the Legal Case Companion service. Please verify your connection or check that the server is running."
    );
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
            reject(new AuthenticationError("Session expired. Please sign in again."));
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
    throw createSpecificApiError(response.status, errorData);
  }

  if (response.status === 204) return null;
  if (options.responseType === "blob") {
    return response.blob();
  }

  return response.json();
}

export const apiClient = {
  get: <T = any>(url: string, options?: RequestOptions): Promise<T> =>
    fetchWithAuth(url, { ...options, method: "GET" }) as Promise<T>,
  post: <T = any>(url: string, body?: unknown, options?: RequestOptions): Promise<T> =>
    fetchWithAuth(url, {
      ...options,
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }) as Promise<T>,
  patch: <T = any>(url: string, body?: unknown, options?: RequestOptions): Promise<T> =>
    fetchWithAuth(url, {
      ...options,
      method: "PATCH",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }) as Promise<T>,
  put: <T = any>(url: string, body?: unknown, options?: RequestOptions): Promise<T> =>
    fetchWithAuth(url, {
      ...options,
      method: "PUT",
      body: body instanceof FormData ? body : JSON.stringify(body),
    }) as Promise<T>,
  delete: <T = any>(url: string, options?: RequestOptions): Promise<T> =>
    fetchWithAuth(url, { ...options, method: "DELETE" }) as Promise<T>,
  blob: (url: string, options?: RequestOptions): Promise<Blob> =>
    fetchWithAuth(url, { ...options, method: options?.method || "GET", responseType: "blob" }) as Promise<Blob>,
};

