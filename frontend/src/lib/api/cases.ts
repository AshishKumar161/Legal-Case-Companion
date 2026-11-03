import { apiClient } from "./client";
import {
  CaseItem,
  CaseWorkspaceResponse,
  TimelineEventItem,
  CaseTaskItem,
  CaseDeadlineItem,
  CaseHearingItem,
  CaseNoteItem,
  MatterBriefItem,
} from "@/types";

export interface CaseListParams {
  skip?: number;
  limit?: number;
  status?: string;
  search?: string;
}

export interface CaseCreatePayload {
  title: string;
  description?: string;
  status?: string;
}

export const casesApi = {
  list: async (params?: CaseListParams): Promise<{ items: CaseItem[]; total: number }> => {
    const searchParams = new URLSearchParams();
    if (params?.skip !== undefined) searchParams.set("skip", String(params.skip));
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.status) searchParams.set("status", params.status);
    if (params?.search) searchParams.set("search", params.search);
    const query = searchParams.toString();
    return apiClient.get(`/api/v1/cases${query ? `?${query}` : ""}`);
  },

  getWorkspace: async (caseId: string): Promise<CaseWorkspaceResponse> => {
    return apiClient.get<CaseWorkspaceResponse>(`/api/v1/cases/${caseId}/workspace`);
  },

  getById: async (caseId: string): Promise<CaseItem> => {
    return apiClient.get<CaseItem>(`/api/v1/cases/${caseId}`);
  },

  create: async (payload: CaseCreatePayload): Promise<CaseItem> => {
    return apiClient.post<CaseItem>("/api/v1/cases", payload);
  },

  update: async (caseId: string, payload: Partial<CaseCreatePayload>): Promise<CaseItem> => {
    return apiClient.patch<CaseItem>(`/api/v1/cases/${caseId}`, payload);
  },

  getTimeline: async (caseId: string): Promise<TimelineEventItem[]> => {
    return apiClient.get<TimelineEventItem[]>(`/api/v1/cases/${caseId}/timeline`);
  },

  getBrief: async (caseId: string): Promise<MatterBriefItem> => {
    return apiClient.get<MatterBriefItem>(`/api/v1/cases/${caseId}/brief`);
  },

  getTasks: async (caseId: string): Promise<CaseTaskItem[]> => {
    return apiClient.get<CaseTaskItem[]>(`/api/v1/cases/${caseId}/tasks`);
  },

  getDeadlines: async (caseId: string): Promise<CaseDeadlineItem[]> => {
    return apiClient.get<CaseDeadlineItem[]>(`/api/v1/cases/${caseId}/deadlines`);
  },

  getHearings: async (caseId: string): Promise<CaseHearingItem[]> => {
    return apiClient.get<CaseHearingItem[]>(`/api/v1/cases/${caseId}/hearings`);
  },

  getNotes: async (caseId: string): Promise<CaseNoteItem[]> => {
    return apiClient.get<CaseNoteItem[]>(`/api/v1/cases/${caseId}/notes`);
  },

  downloadReport: async (caseId: string, format: "markdown" | "json" = "markdown"): Promise<Blob> => {
    return apiClient.blob(`/api/v1/cases/${caseId}/report?format=${format}&download=true`);
  },
};
