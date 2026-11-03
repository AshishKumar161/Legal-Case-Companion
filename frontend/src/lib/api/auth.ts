import { apiClient, performTokenRefresh } from "./client";
import { UserItem } from "@/types";

export interface LoginPayload {
  email: string;
  password?: string;
  grant_type?: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserItem;
}

export interface RegisterPayload {
  email: string;
  password?: string;
  full_name?: string;
  role: "CLIENT" | "LAWYER";
  phone?: string;
}

export const authApi = {
  login: async (payload: LoginPayload): Promise<LoginResponse> => {
    return apiClient.post<LoginResponse>("/api/v1/auth/login", payload, { requireAuth: false });
  },

  register: async (payload: RegisterPayload): Promise<LoginResponse> => {
    return apiClient.post<LoginResponse>("/api/v1/auth/register", payload, { requireAuth: false });
  },

  logout: async (refreshToken?: string): Promise<void> => {
    return apiClient.post("/api/v1/auth/logout", { refresh_token: refreshToken });
  },

  getMe: async (): Promise<UserItem> => {
    return apiClient.get<UserItem>("/api/v1/auth/me");
  },

  refreshSession: async (): Promise<string | null> => {
    return performTokenRefresh();
  },

  forgotPassword: async (email: string): Promise<{ message: string }> => {
    return apiClient.post("/api/v1/auth/forgot-password", { email }, { requireAuth: false });
  },

  resetPassword: async (token: string, newPassword: string): Promise<{ message: string }> => {
    return apiClient.post("/api/v1/auth/reset-password", { token, new_password: newPassword }, { requireAuth: false });
  },

  verifyEmail: async (token: string): Promise<{ message: string }> => {
    return apiClient.post("/api/v1/auth/verify-email", { token }, { requireAuth: false });
  },

  googleCallback: async (code: string, state: string): Promise<LoginResponse> => {
    return apiClient.post<LoginResponse>(
      "/api/v1/auth/google/callback",
      { code, state },
      { requireAuth: false }
    );
  },
};
