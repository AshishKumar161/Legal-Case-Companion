import { apiClient } from "./client";
import { PaymentIntentResponse } from "@/types";

export const paymentsApi = {
  createIntent: async (
    consultationId: string,
    idempotencyKey?: string
  ): Promise<PaymentIntentResponse> => {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey;
    }
    return apiClient.post<PaymentIntentResponse>(
      `/api/v1/consultations/${consultationId}/payment-intent`,
      {},
      { headers }
    );
  },

  testPay: async (consultationId: string): Promise<{ status: string; message: string }> => {
    return apiClient.post(`/api/v1/consultations/${consultationId}/pay-test`, {});
  },
};
