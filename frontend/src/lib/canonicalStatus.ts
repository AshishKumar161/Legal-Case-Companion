/**
 * CANONICAL FRONTEND DATA MODEL & STATUS REGISTRY
 *
 * Single authoritative source of truth for entity status definitions,
 * semantic human-readable meanings, accessible color tokens, and LegalTerm mappings.
 *
 * Principle: "One product, one design language, one source of truth."
 */

export interface CanonicalStatusDefinition {
  code: string;
  label: string;
  semanticMeaning: string;
  bg: string;
  text: string;
  border: string;
  dotColor: string;
  legalTermKey?: string;
  urgency?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
}

// ----------------------------------------------------------------------------
// 1. CASE STATUS REGISTRY
// ----------------------------------------------------------------------------
export const CASE_STATUS_MAP: Record<string, CanonicalStatusDefinition> = {
  DRAFT: {
    code: "DRAFT",
    label: "Draft",
    semanticMeaning: "Case is being drafted and has not yet been submitted or filed.",
    bg: "rgba(148, 163, 184, 0.12)",
    text: "#94a3b8",
    border: "rgba(148, 163, 184, 0.25)",
    dotColor: "#94a3b8",
    urgency: "LOW",
  },
  OPEN: {
    code: "OPEN",
    label: "Active",
    semanticMeaning: "Case is active and progressing through proceedings or client preparation.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  IN_PROGRESS: {
    code: "IN_PROGRESS",
    label: "In Progress",
    semanticMeaning: "Active legal work and counsel collaboration are ongoing.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  IN_REVIEW: {
    code: "IN_REVIEW",
    label: "In Review",
    semanticMeaning: "Pleadings, evidence, or settlement proposals are currently under lawyer or court review.",
    bg: "rgba(59, 130, 246, 0.12)",
    text: "#60a5fa",
    border: "rgba(59, 130, 246, 0.3)",
    dotColor: "#60a5fa",
    urgency: "MEDIUM",
  },
  PENDING_COURT: {
    code: "PENDING_COURT",
    label: "Pending in Court",
    semanticMeaning: "The matter is filed and awaiting court listing, notice issuance, or judge bench allocation.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    legalTermKey: "cause list",
    urgency: "MEDIUM",
  },
  CLOSED: {
    code: "CLOSED",
    label: "Disposed / Closed",
    semanticMeaning: "The court or parties have concluded the proceedings with a final judgment, decree, or settlement.",
    bg: "rgba(148, 163, 184, 0.12)",
    text: "#94a3b8",
    border: "rgba(148, 163, 184, 0.25)",
    dotColor: "#94a3b8",
    urgency: "LOW",
  },
  ARCHIVED: {
    code: "ARCHIVED",
    label: "Archived",
    semanticMeaning: "Case file is archived for compliance and historical record-keeping.",
    bg: "rgba(100, 116, 139, 0.12)",
    text: "#64748b",
    border: "rgba(100, 116, 139, 0.2)",
    dotColor: "#64748b",
    urgency: "LOW",
  },
};

// ----------------------------------------------------------------------------
// 2. HEARING STATUS REGISTRY
// ----------------------------------------------------------------------------
export const HEARING_STATUS_MAP: Record<string, CanonicalStatusDefinition> = {
  SCHEDULED: {
    code: "SCHEDULED",
    label: "Scheduled",
    semanticMeaning: "A future court hearing date has been assigned by the court registry or judicial bench.",
    bg: "rgba(59, 130, 246, 0.12)",
    text: "#60a5fa",
    border: "rgba(59, 130, 246, 0.3)",
    dotColor: "#60a5fa",
    urgency: "MEDIUM",
  },
  LISTED: {
    code: "LISTED",
    label: "Listed in Cause List",
    semanticMeaning: "The matter is published on the official court daily cause list with bench and item number.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    legalTermKey: "cause list",
    urgency: "HIGH",
  },
  COMPLETED: {
    code: "COMPLETED",
    label: "Hearing Completed",
    semanticMeaning: "The scheduled hearing session has concluded. Await registry order or proceedings record.",
    bg: "rgba(148, 163, 184, 0.12)",
    text: "#94a3b8",
    border: "rgba(148, 163, 184, 0.25)",
    dotColor: "#94a3b8",
    urgency: "LOW",
  },
  ADJOURNED: {
    code: "ADJOURNED",
    label: "Adjourned",
    semanticMeaning: "The court deferred hearing the matter today and assigned a subsequent date.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "MEDIUM",
  },
  POSTPONED: {
    code: "POSTPONED",
    label: "Postponed",
    semanticMeaning: "Hearing deferred due to administrative notice, judge leave, or registry rescheduling.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "MEDIUM",
  },
  CANCELLED: {
    code: "CANCELLED",
    label: "Cancelled",
    semanticMeaning: "The hearing listing was cancelled or removed from the board.",
    bg: "rgba(239, 68, 68, 0.12)",
    text: "#ef4444",
    border: "rgba(239, 68, 68, 0.3)",
    dotColor: "#ef4444",
    urgency: "HIGH",
  },
  JUDGMENT_RESERVED: {
    code: "JUDGMENT_RESERVED",
    label: "Judgment Reserved",
    semanticMeaning: "Oral arguments are complete. The judge has reserved the matter to draft and deliver the verdict.",
    bg: "rgba(168, 85, 247, 0.14)",
    text: "#c084fc",
    border: "rgba(168, 85, 247, 0.35)",
    dotColor: "#c084fc",
    legalTermKey: "judgment reserved",
    urgency: "HIGH",
  },
  UNKNOWN: {
    code: "UNKNOWN",
    label: "Status Pending",
    semanticMeaning: "Official court status pending registry upload.",
    bg: "rgba(100, 116, 139, 0.12)",
    text: "#94a3b8",
    border: "rgba(100, 116, 139, 0.2)",
    dotColor: "#94a3b8",
    urgency: "LOW",
  },
};

// ----------------------------------------------------------------------------
// 3. CONSULTATION STATUS REGISTRY
// ----------------------------------------------------------------------------
export const CONSULTATION_STATUS_MAP: Record<string, CanonicalStatusDefinition> = {
  REQUESTED: {
    code: "REQUESTED",
    label: "Requested",
    semanticMeaning: "Consultation requested by client; awaiting advocate slot confirmation.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "MEDIUM",
  },
  ACCEPTED: {
    code: "ACCEPTED",
    label: "Confirmed",
    semanticMeaning: "Advocate accepted consultation; time slot reserved.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  CONFIRMED: {
    code: "CONFIRMED",
    label: "Confirmed",
    semanticMeaning: "Slot confirmed and verified.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  SCHEDULED: {
    code: "SCHEDULED",
    label: "Upcoming Session",
    semanticMeaning: "Consultation booked and scheduled in IST.",
    bg: "rgba(59, 130, 246, 0.12)",
    text: "#60a5fa",
    border: "rgba(59, 130, 246, 0.3)",
    dotColor: "#60a5fa",
    urgency: "MEDIUM",
  },
  IN_PROGRESS: {
    code: "IN_PROGRESS",
    label: "Session Active",
    semanticMeaning: "Confidential video/audio consultation is currently in progress.",
    bg: "rgba(16, 185, 129, 0.18)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.4)",
    dotColor: "#10b981",
    urgency: "HIGH",
  },
  COMPLETED: {
    code: "COMPLETED",
    label: "Completed",
    semanticMeaning: "Consultation concluded successfully.",
    bg: "rgba(148, 163, 184, 0.12)",
    text: "#94a3b8",
    border: "rgba(148, 163, 184, 0.25)",
    dotColor: "#94a3b8",
    urgency: "LOW",
  },
  CANCELLED: {
    code: "CANCELLED",
    label: "Cancelled",
    semanticMeaning: "Consultation was cancelled.",
    bg: "rgba(239, 68, 68, 0.12)",
    text: "#ef4444",
    border: "rgba(239, 68, 68, 0.3)",
    dotColor: "#ef4444",
    urgency: "HIGH",
  },
  RESCHEDULED: {
    code: "RESCHEDULED",
    label: "Rescheduled",
    semanticMeaning: "Consultation moved to a newly selected time slot.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "MEDIUM",
  },
  REJECTED: {
    code: "REJECTED",
    label: "Declined",
    semanticMeaning: "Lawyer could not accommodate the consultation request.",
    bg: "rgba(239, 68, 68, 0.12)",
    text: "#ef4444",
    border: "rgba(239, 68, 68, 0.3)",
    dotColor: "#ef4444",
    urgency: "HIGH",
  },
};

// ----------------------------------------------------------------------------
// 4. PAYMENT STATUS REGISTRY
// ----------------------------------------------------------------------------
export const PAYMENT_STATUS_MAP: Record<string, CanonicalStatusDefinition> = {
  CREATED: {
    code: "CREATED",
    label: "Pending Payment",
    semanticMeaning: "Invoice or checkout order generated; awaiting client authorization.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "MEDIUM",
  },
  PENDING: {
    code: "PENDING",
    label: "Pending",
    semanticMeaning: "Awaiting bank gateway response or UPI settlement.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "MEDIUM",
  },
  PROCESSING: {
    code: "PROCESSING",
    label: "Processing",
    semanticMeaning: "Payment is being cleared and validated with the payment aggregator.",
    bg: "rgba(59, 130, 246, 0.12)",
    text: "#60a5fa",
    border: "rgba(59, 130, 246, 0.3)",
    dotColor: "#60a5fa",
    urgency: "MEDIUM",
  },
  SUCCEEDED: {
    code: "SUCCEEDED",
    label: "Paid",
    semanticMeaning: "Payment verified. GST tax invoice and receipt issued.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  PAID: {
    code: "PAID",
    label: "Paid",
    semanticMeaning: "Payment settled and confirmed.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  FAILED: {
    code: "FAILED",
    label: "Payment Failed",
    semanticMeaning: "Transaction was declined or interrupted. No funds were captured.",
    bg: "rgba(239, 68, 68, 0.12)",
    text: "#ef4444",
    border: "rgba(239, 68, 68, 0.3)",
    dotColor: "#ef4444",
    urgency: "HIGH",
  },
  REFUNDED: {
    code: "REFUNDED",
    label: "Refunded",
    semanticMeaning: "Funds returned to original payment source.",
    bg: "rgba(168, 85, 247, 0.12)",
    text: "#c084fc",
    border: "rgba(168, 85, 247, 0.3)",
    dotColor: "#c084fc",
    urgency: "LOW",
  },
  CANCELLED: {
    code: "CANCELLED",
    label: "Cancelled",
    semanticMeaning: "Checkout order expired or cancelled.",
    bg: "rgba(148, 163, 184, 0.12)",
    text: "#94a3b8",
    border: "rgba(148, 163, 184, 0.25)",
    dotColor: "#94a3b8",
    urgency: "LOW",
  },
};

// ----------------------------------------------------------------------------
// 5. DOCUMENT & EVIDENCE STATUS REGISTRY
// ----------------------------------------------------------------------------
export const DOCUMENT_STATUS_MAP: Record<string, CanonicalStatusDefinition> = {
  SAFE: {
    code: "SAFE",
    label: "Verified Safe",
    semanticMeaning: "Cryptographic SHA-256 hash verified and antivirus inspection clean.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  CLEAN: {
    code: "CLEAN",
    label: "Clean",
    semanticMeaning: "Security scan confirmed document integrity.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  PENDING: {
    code: "PENDING",
    label: "Validating",
    semanticMeaning: "Document uploaded; awaiting automated malware scan and checksum validation.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "MEDIUM",
  },
  VALIDATING: {
    code: "VALIDATING",
    label: "Validating",
    semanticMeaning: "Checking digital signature and storage integrity.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "MEDIUM",
  },
  SCANNING: {
    code: "SCANNING",
    label: "Scanning",
    semanticMeaning: "Antivirus scanner actively inspecting file contents.",
    bg: "rgba(59, 130, 246, 0.12)",
    text: "#60a5fa",
    border: "rgba(59, 130, 246, 0.3)",
    dotColor: "#60a5fa",
    urgency: "MEDIUM",
  },
  INDEXED: {
    code: "INDEXED",
    label: "Indexed",
    semanticMeaning: "Text extracted and indexed for fast legal search.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  QUARANTINED: {
    code: "QUARANTINED",
    label: "Quarantined",
    semanticMeaning: "Suspicious payload or signature mismatch detected. File is isolated.",
    bg: "rgba(239, 68, 68, 0.15)",
    text: "#ef4444",
    border: "rgba(239, 68, 68, 0.35)",
    dotColor: "#ef4444",
    urgency: "CRITICAL",
  },
  REJECTED: {
    code: "REJECTED",
    label: "Rejected",
    semanticMeaning: "Document failed file validation policy or size limit.",
    bg: "rgba(239, 68, 68, 0.12)",
    text: "#ef4444",
    border: "rgba(239, 68, 68, 0.3)",
    dotColor: "#ef4444",
    urgency: "HIGH",
  },
  FAILED: {
    code: "FAILED",
    label: "Failed",
    semanticMeaning: "Document extraction or validation encountered an error.",
    bg: "rgba(239, 68, 68, 0.12)",
    text: "#ef4444",
    border: "rgba(239, 68, 68, 0.3)",
    dotColor: "#ef4444",
    urgency: "HIGH",
  },
};

// ----------------------------------------------------------------------------
// 6. TASK & DEADLINE STATUS REGISTRY
// ----------------------------------------------------------------------------
export const TASK_STATUS_MAP: Record<string, CanonicalStatusDefinition> = {
  PENDING: {
    code: "PENDING",
    label: "To Do",
    semanticMeaning: "Action item pending initiation.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "MEDIUM",
  },
  TODO: {
    code: "TODO",
    label: "To Do",
    semanticMeaning: "Action item awaiting completion.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "MEDIUM",
  },
  IN_PROGRESS: {
    code: "IN_PROGRESS",
    label: "In Progress",
    semanticMeaning: "Task is actively being handled.",
    bg: "rgba(59, 130, 246, 0.12)",
    text: "#60a5fa",
    border: "rgba(59, 130, 246, 0.3)",
    dotColor: "#60a5fa",
    urgency: "MEDIUM",
  },
  COMPLETED: {
    code: "COMPLETED",
    label: "Done",
    semanticMeaning: "Task completed and verified.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  CANCELLED: {
    code: "CANCELLED",
    label: "Cancelled",
    semanticMeaning: "Task is no longer required.",
    bg: "rgba(148, 163, 184, 0.12)",
    text: "#94a3b8",
    border: "rgba(148, 163, 184, 0.25)",
    dotColor: "#94a3b8",
    urgency: "LOW",
  },
  OVERDUE: {
    code: "OVERDUE",
    label: "Overdue",
    semanticMeaning: "Deadline has passed without verified completion.",
    bg: "rgba(239, 68, 68, 0.15)",
    text: "#ef4444",
    border: "rgba(239, 68, 68, 0.35)",
    dotColor: "#ef4444",
    urgency: "CRITICAL",
  },
  STATUTORY_LIMITATION: {
    code: "STATUTORY_LIMITATION",
    label: "Statutory Limitation",
    semanticMeaning: "Strict judicial limitation under Indian Limitation Act, 1963. Non-extendable.",
    bg: "rgba(220, 38, 38, 0.18)",
    text: "#f87171",
    border: "rgba(220, 38, 38, 0.4)",
    dotColor: "#f87171",
    urgency: "CRITICAL",
  },
};

// ----------------------------------------------------------------------------
// 7. PROVENANCE TYPE REGISTRY (SECTION 25)
// ----------------------------------------------------------------------------
export const PROVENANCE_TYPE_MAP: Record<string, CanonicalStatusDefinition> = {
  "OFFICIAL COURT DATA": {
    code: "OFFICIAL_COURT_DATA",
    label: "Official Court Data",
    semanticMeaning: "Directly synchronized from official Indian Court Registry / eCourts National Portal.",
    bg: "rgba(59, 130, 246, 0.12)",
    text: "#60a5fa",
    border: "rgba(59, 130, 246, 0.3)",
    dotColor: "#60a5fa",
    urgency: "LOW",
  },
  "LAWYER ENTERED": {
    code: "LAWYER_ENTERED",
    label: "Lawyer Entered",
    semanticMeaning: "Entered or verified by an enrolled advocate representing the matter.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  "YOU ADDED": {
    code: "YOU_ADDED",
    label: "You Added",
    semanticMeaning: "Uploaded or submitted directly by you into your secure case vault.",
    bg: "rgba(168, 85, 247, 0.12)",
    text: "#c084fc",
    border: "rgba(168, 85, 247, 0.3)",
    dotColor: "#c084fc",
    urgency: "LOW",
  },
  "LCC INFORMATION": {
    code: "LCC_INFORMATION",
    label: "LCC Information",
    semanticMeaning: "Platform explanation, procedural guidance, or statutory timeline reference.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "LOW",
  },
  SYSTEM: {
    code: "SYSTEM",
    label: "System",
    semanticMeaning: "Computed automatically by platform business rules or cryptographic checks.",
    bg: "rgba(148, 163, 184, 0.12)",
    text: "#94a3b8",
    border: "rgba(148, 163, 184, 0.25)",
    dotColor: "#94a3b8",
    urgency: "LOW",
  },
};

// ----------------------------------------------------------------------------
// 8. VERIFICATION STATUS REGISTRY
// ----------------------------------------------------------------------------
export const VERIFICATION_STATUS_MAP: Record<string, CanonicalStatusDefinition> = {
  VERIFIED: {
    code: "VERIFIED",
    label: "Verified",
    semanticMeaning: "Independently verified with supporting documentary evidence.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  CONFIRMED: {
    code: "CONFIRMED",
    label: "Confirmed",
    semanticMeaning: "Confirmed by participating party or counsel.",
    bg: "rgba(16, 185, 129, 0.12)",
    text: "#10b981",
    border: "rgba(16, 185, 129, 0.3)",
    dotColor: "#10b981",
    urgency: "LOW",
  },
  PENDING: {
    code: "PENDING",
    label: "Pending Verification",
    semanticMeaning: "Awaiting documentary proof or lawyer review.",
    bg: "rgba(245, 158, 11, 0.12)",
    text: "#f59e0b",
    border: "rgba(245, 158, 11, 0.3)",
    dotColor: "#f59e0b",
    urgency: "MEDIUM",
  },
  CONTESTED: {
    code: "CONTESTED",
    label: "Contested / Disputed",
    semanticMeaning: "Disputed by opposing counsel or contradicted by evidence.",
    bg: "rgba(239, 68, 68, 0.12)",
    text: "#ef4444",
    border: "rgba(239, 68, 68, 0.3)",
    dotColor: "#ef4444",
    urgency: "HIGH",
  },
  UNVERIFIED: {
    code: "UNVERIFIED",
    label: "Unverified",
    semanticMeaning: "Statement or upload without corroborating proof.",
    bg: "rgba(148, 163, 184, 0.12)",
    text: "#94a3b8",
    border: "rgba(148, 163, 184, 0.25)",
    dotColor: "#94a3b8",
    urgency: "LOW",
  },
};

/**
 * Universal resolver function: maps any status code across all 8 entity types
 * to its canonical definition. Falls back gracefully if unknown.
 */
export function resolveCanonicalStatus(rawStatus?: string | null): CanonicalStatusDefinition {
  if (!rawStatus) {
    return {
      code: "UNKNOWN",
      label: "Unknown",
      semanticMeaning: "Status information currently unavailable.",
      bg: "rgba(100, 116, 139, 0.12)",
      text: "#94a3b8",
      border: "rgba(100, 116, 139, 0.2)",
      dotColor: "#94a3b8",
      urgency: "LOW",
    };
  }

  const norm = rawStatus.toUpperCase().trim().replace(/[\s-]/g, "_");

  // Check specific maps in logical order
  if (PROVENANCE_TYPE_MAP[rawStatus.toUpperCase()]) return PROVENANCE_TYPE_MAP[rawStatus.toUpperCase()];
  if (PROVENANCE_TYPE_MAP[norm.replace(/_/g, " ")]) return PROVENANCE_TYPE_MAP[norm.replace(/_/g, " ")];

  if (CASE_STATUS_MAP[norm]) return CASE_STATUS_MAP[norm];
  if (HEARING_STATUS_MAP[norm]) return HEARING_STATUS_MAP[norm];
  if (CONSULTATION_STATUS_MAP[norm]) return CONSULTATION_STATUS_MAP[norm];
  if (PAYMENT_STATUS_MAP[norm]) return PAYMENT_STATUS_MAP[norm];
  if (DOCUMENT_STATUS_MAP[norm]) return DOCUMENT_STATUS_MAP[norm];
  if (TASK_STATUS_MAP[norm]) return TASK_STATUS_MAP[norm];
  if (VERIFICATION_STATUS_MAP[norm]) return VERIFICATION_STATUS_MAP[norm];

  // Friendly fallback formatting
  const formattedLabel = rawStatus
    .replace(/[_-]/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return {
    code: norm,
    label: formattedLabel,
    semanticMeaning: `Status: ${formattedLabel}`,
    bg: "rgba(100, 116, 139, 0.12)",
    text: "#94a3b8",
    border: "rgba(100, 116, 139, 0.2)",
    dotColor: "#94a3b8",
    urgency: "LOW",
  };
}
