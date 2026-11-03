import { apiClient } from "./client";
import { DocumentItem } from "@/types";

export interface PresignedUploadResponse {
  upload_url: string;
  document_id: string;
  object_key: string;
  expires_in: number;
}

export interface DocumentUploadInitPayload {
  filename: string;
  content_type: string;
  size_bytes: number;
  category?: string;
  description?: string;
}

export const documentsApi = {
  list: async (caseId?: string): Promise<DocumentItem[]> => {
    const query = caseId ? `?case_id=${encodeURIComponent(caseId)}` : "";
    return apiClient.get<DocumentItem[]>(`/api/v1/documents${query}`);
  },

  getById: async (documentId: string): Promise<DocumentItem> => {
    return apiClient.get<DocumentItem>(`/api/v1/documents/${documentId}`);
  },

  initiateUpload: async (
    caseId: string,
    payload: DocumentUploadInitPayload
  ): Promise<PresignedUploadResponse> => {
    return apiClient.post<PresignedUploadResponse>(`/api/v1/cases/${caseId}/documents/upload-init`, payload);
  },

  completeUpload: async (caseId: string, documentId: string): Promise<DocumentItem> => {
    return apiClient.post<DocumentItem>(`/api/v1/cases/${caseId}/documents/${documentId}/upload-complete`, {});
  },

  delete: async (documentId: string): Promise<void> => {
    return apiClient.delete(`/api/v1/documents/${documentId}`);
  },

  uploadConsultationDocument: async (
    consultationId: string,
    formData: FormData
  ): Promise<{ id: string; filename: string; file_url: string; [key: string]: unknown }> => {
    return apiClient.post(`/api/v1/consultations/${consultationId}/documents`, formData);
  },
};
