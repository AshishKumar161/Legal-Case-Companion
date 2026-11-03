import { apiClient } from "./client";
import { ConsultationItem } from "@/types";

export interface ConsultationListParams {
  status?: string;
  skip?: number;
  limit?: number;
}

export interface VideoJoinInfoResponse {
  consultation_id: string;
  meeting_id: string;
  room_id: string;
  provider: string;
  status: string;
  participant_user_id: string;
  participant_name: string;
  participant_role: string;
  scheduled_start: string;
  scheduled_end: string;
  started_at?: string | null;
  consultation_status?: string | null;
  token: string;
  ice_servers: Record<string, unknown>[];
  is_live: boolean;
}

export interface VideoRoomAccessStatusResponse {
  consultation_id: string;
  meeting_id?: string | null;
  room_id?: string | null;
  consultation_status: string;
  is_authorized: boolean;
  can_join: boolean;
  scheduled_at_utc: string;
  current_server_time_utc: string;
  earliest_join_time_utc: string;
  latest_join_time_utc: string;
  scheduled_at_ist: string;
  earliest_join_ist: string;
  time_until_open_seconds?: number | null;
  reason_blocked?: string | null;
  participant_name?: string | null;
  participant_role?: string | null;
  other_party_name?: string | null;
  lawyer_online: boolean;
  time_bypass_allowed: boolean;
}

export const consultationsApi = {
  list: async (params?: ConsultationListParams): Promise<ConsultationItem[]> => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    const query = searchParams.toString();
    return apiClient.get<ConsultationItem[]>(`/api/v1/consultations${query ? `?${query}` : ""}`);
  },

  getById: async (id: string): Promise<ConsultationItem> => {
    return apiClient.get<ConsultationItem>(`/api/v1/consultations/${id}`);
  },

  getAccessStatus: async (id: string, bypassTimeWindow: boolean = false): Promise<VideoRoomAccessStatusResponse> => {
    return apiClient.get<VideoRoomAccessStatusResponse>(
      `/api/v1/consultations/${id}/video/access-status${bypassTimeWindow ? "?bypass_time=true" : ""}`
    );
  },

  joinVideoMeeting: async (id: string, bypassTimeWindow: boolean = false): Promise<VideoJoinInfoResponse> => {
    return apiClient.get<VideoJoinInfoResponse>(
      `/api/v1/consultations/${id}/video/join${bypassTimeWindow ? "?bypass_time=true" : ""}`
    );
  },

  reconnectVideoMeeting: async (id: string): Promise<VideoJoinInfoResponse> => {
    return apiClient.post<VideoJoinInfoResponse>(`/api/v1/consultations/${id}/video/reconnect`, {});
  },

  schedule: async (
    id: string,
    payload: { scheduled_at: string; lawyer_notes?: string }
  ): Promise<ConsultationItem> => {
    return apiClient.post<ConsultationItem>(`/api/v1/consultations/${id}/schedule`, payload);
  },

  reschedule: async (
    id: string,
    payload: { new_time: string; reason: string }
  ): Promise<ConsultationItem> => {
    return apiClient.post<ConsultationItem>(`/api/v1/consultations/${id}/reschedule`, payload);
  },

  cancel: async (id: string, payload: { reason: string }): Promise<ConsultationItem> => {
    return apiClient.post<ConsultationItem>(`/api/v1/consultations/${id}/cancel`, payload);
  },

  complete: async (id: string): Promise<ConsultationItem> => {
    return apiClient.post<ConsultationItem>(`/api/v1/consultations/${id}/complete`, {});
  },

  getRecordings: async (id: string): Promise<unknown[]> => {
    return apiClient.get(`/api/v1/consultations/${id}/recordings`);
  },
};
