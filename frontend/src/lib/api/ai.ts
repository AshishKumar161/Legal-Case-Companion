import { apiClient } from "./client";
import { CaseAssistantQueryResponse, RetrievedLegalAuthorityItem } from "@/types";

export interface CopilotQueryPayload {
  prompt: string;
  session_id?: string;
  include_citations?: boolean;
}

export interface LegalAuthoritySearchParams {
  query: string;
  top_k?: number;
  search_mode?: "HYBRID" | "KEYWORD" | "SEMANTIC";
}

export const aiApi = {
  queryAssistant: async (
    caseId: string,
    payload: CopilotQueryPayload
  ): Promise<CaseAssistantQueryResponse> => {
    return apiClient.post<CaseAssistantQueryResponse>(
      `/api/v1/cases/${caseId}/assistant/query`,
      payload
    );
  },

  searchLegalAuthorities: async (
    params: LegalAuthoritySearchParams
  ): Promise<{ results: RetrievedLegalAuthorityItem[]; total?: number }> => {
    return apiClient.post("/api/v1/legal-authorities/search", {
      query: params.query.trim(),
      top_k: params.top_k || 8,
      search_mode: params.search_mode || "HYBRID",
    });
  },
};
