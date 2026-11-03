/**
 * Privacy-Preserving Funnel Telemetry for LCC
 *
 * Adheres to Section 29 Data Minimization:
 * - NO legal notice contents
 * - NO raw case descriptions
 * - NO private documents
 * - NO sensitive personally identifiable information (PII)
 */

export type FunnelEventType =
  | "discovery_started"
  | "intent_selected"
  | "filters_applied"
  | "results_shown"
  | "profile_opened"
  | "slot_selected"
  | "checkout_started"
  | "payment_success"
  | "booking_completed"
  | "court_search_started"
  | "court_search_completed"
  | "court_result_opened"
  | "case_followed"
  | "hearing_opened"
  | "order_opened";

export interface FunnelEventPayload {
  intent?: string;
  location?: string;
  court_category?: string;
  language?: string;
  budget_range?: string;
  urgency?: string;
  results_count?: number;
  lawyer_id?: string;
  has_case_link?: boolean;
  step?: number;
}

export function trackFunnelEvent(event: FunnelEventType, payload?: FunnelEventPayload): void {
  if (typeof window === "undefined") return;

  try {
    const sanitizedPayload = payload ? { ...payload } : {};

    // Explicit redaction safeguards (guaranteeing telemetry minimization)
    delete (sanitizedPayload as Record<string, unknown>).description;
    delete (sanitizedPayload as Record<string, unknown>).notes;
    delete (sanitizedPayload as Record<string, unknown>).notice_content;
    delete (sanitizedPayload as Record<string, unknown>).client_name;

    const eventRecord = {
      event,
      payload: sanitizedPayload,
      timestamp: new Date().toISOString(),
    };

    // Broadcast event for in-app observability or logging without external network leakage
    window.dispatchEvent(
      new CustomEvent("lcc:funnel-telemetry", {
        detail: eventRecord,
      })
    );

    if (process.env.NODE_ENV !== "production") {
      // Clean, low-noise diagnostic in development
      // console.debug("[LCC Funnel]", event, sanitizedPayload);
    }
  } catch {
    // Fail silently so telemetry never degrades client experience
  }
}
