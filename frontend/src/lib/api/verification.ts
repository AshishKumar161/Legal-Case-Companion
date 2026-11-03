import { apiClient } from "./client";
import { VerificationQueueItem, AdvocateVerificationDetail } from "@/types";

export interface VerificationSubmitPayload {
  enrollment_number: string;
  state_bar_council: string;
  year_of_enrollment?: number;
}

export const verificationApi = {
  getQueue: async (): Promise<VerificationQueueItem[]> => {
    return apiClient.get<VerificationQueueItem[]>("/api/v1/admin/verification/queue");
  },

  getDetail: async (verificationId: string): Promise<AdvocateVerificationDetail> => {
    return apiClient.get<AdvocateVerificationDetail>(
      `/api/v1/admin/verification/${verificationId}`
    );
  },

  review: async (
    verificationId: string,
    action: "approve" | "reject",
    rejectionReason?: string
  ): Promise<{ status: string; message: string }> => {
    return apiClient.post(`/api/v1/admin/verification/${verificationId}/review`, {
      action,
      rejection_reason: rejectionReason,
    });
  },

  submitEnrollment: async (payload: VerificationSubmitPayload): Promise<{ status: string }> => {
    return apiClient.post("/api/v1/lawyers/me/verification", payload);
  },
};
