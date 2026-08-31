// ============================================================================
// CORE ENTITIES & ENUMS
// ============================================================================

export type UserRole = "CLIENT" | "LAWYER" | "ADMIN";

export interface UserItem {
  id: string;
  email: string;
  role: UserRole;
  account_status: string;
}

// ----------------------------------------------------------------------------
// CASES & PARTICIPANTS
// ----------------------------------------------------------------------------

export interface CaseItem {
  id: string;
  title: string;
  description: string;
  status: "DRAFT" | "OPEN" | "IN_REVIEW" | "PENDING_COURT" | "IN_PROGRESS" | "CLOSED" | "ARCHIVED";
  case_number?: string;
  created_at: string;
  updated_at: string;
}

export interface CaseParticipantItem {
  id: string;
  case_id: string;
  user_id: string;
  participant_role: "OWNER" | "CLIENT" | "PRIMARY_LAWYER" | "COLLABORATING_LAWYER" | "LAWYER" | "PARALEGAL" | "VIEWER" | "OBSERVER";
  role?: string;
  status: "ACTIVE" | "PENDING" | "REMOVED";
  user?: {
    email: string;
    full_name?: string;
    role: string;
  };
  created_at: string;
}

export interface TimelineEventItem {
  id: string;
  case_id: string;
  actor_user_id?: string | null;
  event_type: string;
  description: string;
  event_metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface CaseWorkspaceResponse {
  case: CaseItem;
  effective_permissions: string[];
  participants: CaseParticipantItem[];
  lawyer: LawyerProfileItem | null;
  document_count: number;
  documents_summary: {
    total?: number;
    safe?: number;
    pending?: number;
    quarantined?: number;
    rejected?: number;
    by_category?: Record<string, number>;
  };
  tasks_summary: {
    total?: number;
    pending?: number;
    in_progress?: number;
    completed?: number;
    cancelled?: number;
  };
  upcoming_deadlines: Array<{
    type: string;
    id: string;
    title: string;
    due_date?: string;
    priority?: string;
  }>;
  notes_count: number;
  recent_activities: TimelineEventItem[];
  intelligence_summary: Record<string, unknown>;
}

// ----------------------------------------------------------------------------
// DOCUMENTS & EVIDENCE
// ----------------------------------------------------------------------------

export type DocumentCategory =
  | "CONTRACT"
  | "EVIDENCE"
  | "PLEADING"
  | "NOTICE"
  | "ORDER"
  | "CORRESPONDENCE"
  | "TRANSCRIPT"
  | "OTHER";

export interface DocumentItem {
  id: string;
  case_id: string;
  filename: string;
  document_type?: DocumentCategory | string;
  category?: string;
  storage_key?: string;
  mime_type: string;
  file_size: number;
  security_status: "SAFE" | "PENDING" | "VALIDATING" | "SCANNING" | "QUARANTINED" | "CLEAN" | "PENDING_SCAN" | "REJECTED";
  processing_status?: "PENDING" | "PROCESSING" | "EXTRACTED" | "INDEXED" | "FAILED";
  version?: number;
  document_version?: number;
  uploaded_by?: string;
  created_at: string;
  updated_at?: string;
}

export interface DocumentChunkItem {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  page_number?: number;
  token_count?: number;
  relevance_score?: number;
}

export interface DocumentPageItem {
  id: string;
  document_id: string;
  page_number: number;
  extracted_text?: string;
  confidence_score?: number;
}

export interface DocumentSummaryStats {
  total_documents: number;
  safe_documents: number;
  quarantined_documents: number;
  rejected_documents: number;
  pending_documents: number;
  total_chunks: number;
}

// ----------------------------------------------------------------------------
// CASE INTELLIGENCE
// ----------------------------------------------------------------------------

export interface CaseFactItem {
  id: string;
  case_id: string;
  fact_text?: string;
  fact_statement?: string;
  category?: string;
  verification_status: "AI_SUGGESTED" | "AI_VERIFIED" | "HUMAN_CONFIRMED" | "USER_REPORTED" | "CONTESTED";
  source_type: "CASE_EVIDENCE" | "LEGAL_AUTHORITY" | "USER_REPORTED" | "CONVERSATION_EXTRACTION" | string;
  source_chunk_id?: string | null;
  source_document_id?: string | null;
  source_filename?: string | null;
  source_authority_id?: string | null;
  confidence_score?: number;
  created_at: string;
  updated_at?: string;
}

export interface LegalIssueItem {
  id: string;
  case_id: string;
  issue_text?: string;
  issue_title?: string;
  issue_description?: string;
  category?: string;
  status: "IDENTIFIED" | "OPEN" | "IN_PROGRESS" | "RESOLVED" | "DISMISSED";
  verification_status?: string;
  supporting_fact_ids?: string[];
  relevant_authority_ids?: string[];
  uncertainties?: string[];
  created_at: string;
  updated_at?: string;
}

export interface ChronologyEventItem {
  id: string;
  case_id: string;
  event_date?: string | null;
  date_text?: string | null;
  date_precision?: "EXACT_DATE" | "MONTH_YEAR" | "YEAR_ONLY" | "ESTIMATED" | "UNKNOWN";
  event_type: string;
  title?: string;
  description: string;
  is_conflicting?: boolean;
  conflicting_source_details?: Array<{ source: string; detail: string }>;
  source_chunk_id?: string | null;
  source_document_id?: string | null;
  source_filename?: string | null;
  verification_status?: string;
  created_at: string;
}

export interface ClaimDefenseItem {
  id: string;
  case_id: string;
  position_type: "CLAIM" | "DEFENSE" | "COUNTER_CLAIM" | "PLAINTIFF_CLAIM" | "DEFENDANT_DEFENSE";
  party_role?: string;
  statement: string;
  status: "ASSERTED" | "DRAFTED" | "PLED" | "ARGUED" | "ACCEPTED" | "REJECTED";
  verification_status?: string;
  supporting_chunk_ids?: string[];
  opposing_chunk_ids?: string[];
  relevant_authority_ids?: string[];
  created_at: string;
}

export interface EvidenceGapItem {
  id: string;
  case_id: string;
  description: string;
  gap_type: "MISSING_DOCUMENT" | "UNSUPPORTED_FACT" | "UNVERIFIED_STATEMENT" | "WITNESS_CORROBORATION" | string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  status: "IDENTIFIED" | "REQUESTED" | "SATISFIED" | "WAIVED" | "NOT_FOUND_IN_AVAILABLE_MATERIALS" | string;
  related_issue_id?: string | null;
  related_claim_id?: string | null;
  created_at: string;
}

export interface CaseRiskIndicatorItem {
  id: string;
  case_id: string;
  risk_title: string;
  description: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  mitigation_hint?: string | null;
  evidence_sources?: Array<Record<string, unknown>>;
  verification_status?: string;
  created_at: string;
}

export interface CaseIntelligenceSummary {
  total_facts: number;
  verified_facts: number;
  user_reported_facts: number;
  open_issues: number;
  timeline_events: number;
  conflicting_timeline_events: number;
  active_claims: number;
  evidence_gaps: number;
  high_risks: number;
  critical_risks: number;
}

export interface CaseIntelligenceResponse {
  case_id: string;
  facts: CaseFactItem[];
  issues: LegalIssueItem[];
  claims_defenses: ClaimDefenseItem[];
  timeline: ChronologyEventItem[];
  evidence_gaps: EvidenceGapItem[];
  risks: CaseRiskIndicatorItem[];
  summary?: CaseIntelligenceSummary;
  last_refreshed_at?: string | null;
}

// ----------------------------------------------------------------------------
// WORKFLOW: TASKS, DEADLINES, HEARINGS, NOTES
// ----------------------------------------------------------------------------

export interface CaseTaskItem {
  id: string;
  case_id: string;
  title: string;
  description?: string;
  priority: "LOW" | "MEDIUM" | "HIGH" | "URGENT";
  status: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";
  due_date?: string | null;
  owner_user_id?: string | null;
  created_by_user_id?: string | null;
  is_confirmed: boolean;
  source_type?: string;
  created_at: string;
  updated_at?: string;
}

export interface CaseDeadlineItem {
  id: string;
  case_id: string;
  title: string;
  description?: string | null;
  deadline_at: string;
  deadline_type: "STATUTORY_LIMITATION" | "COURT_ORDERED" | "FILING" | "COMPLIANCE" | "GENERAL" | "CUSTOM";
  status: "UPCOMING" | "DUE" | "OVERDUE" | "COMPLETED" | "CANCELLED";
  is_confirmed: boolean;
  source_type?: string;
  source_reference?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface CaseHearingItem {
  id: string;
  case_id: string;
  court_name: string;
  hearing_at: string;
  purpose: string;
  status: "SCHEDULED" | "ADJOURNED" | "CONCLUDED" | "CANCELLED";
  bench_or_coram?: string | null;
  notes?: string | null;
  is_confirmed: boolean;
  source_type?: string;
  created_at: string;
  updated_at?: string;
}

export interface CaseOperationsSummary {
  open_tasks_count: number;
  overdue_tasks_count: number;
  upcoming_deadlines_count: number;
  overdue_deadlines_count: number;
  next_hearing: CaseHearingItem | null;
  unconfirmed_suggestions_count: number;
}

export interface CaseWorkflowResponse {
  case_id: string;
  tasks: CaseTaskItem[];
  deadlines: CaseDeadlineItem[];
  hearings: CaseHearingItem[];
  operations_summary: CaseOperationsSummary;
}

export interface CaseNoteItem {
  id: string;
  case_id: string;
  title: string;
  content: string;
  visibility: "CLIENT_PRIVATE" | "LAWYER_PRIVATE" | "SHARED";
  author_id?: string;
  created_by_user_id?: string;
  created_at: string;
  updated_at?: string;
}

export interface DecisionRecordItem {
  id: string;
  case_id: string;
  title: string;
  context: string;
  rationale: string;
  linked_evidence?: string | null;
  linked_authority?: string | null;
  decision_owner: string;
  status: "RECORDED" | "SUPERSEDED" | "AFFIRMED";
  created_at: string;
}

export interface ActionItemModel {
  id: string;
  case_id: string;
  title: string;
  description?: string;
  priority: "CRITICAL" | "ATTENTION" | "ROUTINE";
  category: "HEARING" | "LIMITATION" | "EVIDENCE_GAP" | "TASK" | "CONSULTATION" | "REVIEW";
  due_date?: string | null;
  source_provenance?: string;
  is_confirmed: boolean;
  status: string;
  action_type: "OPEN_HEARING" | "CONFIRM_TASK" | "CREATE_TASK" | "REVIEW_GAP" | "CONSULT_LAWYER" | "ADD_NOTE";
  target_id?: string;
}

// ----------------------------------------------------------------------------
// COPILOT & AI RETRIEVAL
// ----------------------------------------------------------------------------

export interface AIMessageCitation {
  chunk_id: string;
  document_id: string;
  document_version?: number;
  source_filename: string;
  page_start?: number | null;
  page_end?: number | null;
  text_snippet: string;
  relevance_score?: number | null;
}

export interface AIMessageAuthorityCitation {
  canonical_identifier: string;
  canonical_provision_id: string;
  act_or_judgment_name: string;
  section_or_para: string;
  source_type: string;
  authority_level: number;
  jurisdiction: string;
  effective_from?: string | null;
  effective_to?: string | null;
  text_snippet: string;
  relevance_score?: number | null;
}

export interface AIMessageClaim {
  claim_text: string;
  status: "SUPPORTED" | "PARTIALLY_SUPPORTED" | "CONTRADICTED" | "UNSUPPORTED";
  source_type: "CASE_EVIDENCE" | "LEGAL_AUTHORITY" | "GENERAL_LEGAL_PRINCIPLE";
  supporting_chunk_ids?: string[];
  supporting_authority_ids?: string[];
  explanation?: string | null;
}

export interface AIMessageItem {
  id: string;
  conversation_id: string;
  role: "USER" | "ASSISTANT" | "SYSTEM" | string;
  content: string;
  grounding_status?: "GROUNDED" | "PARTIALLY_GROUNDED" | "UNGROUNDED" | "FALLBACK" | string | null;
  citations?: AIMessageCitation[] | null;
  authority_citations?: AIMessageAuthorityCitation[] | null;
  claims?: AIMessageClaim[] | null;
  uncertainties?: string[] | null;
  warnings?: string[] | null;
  created_at: string;
}

export interface CaseAssistantQueryResponse {
  question: string;
  answer: string;
  grounding_status: "SUPPORTED" | "INSUFFICIENT_EVIDENCE" | "CONFLICTING_EVIDENCE" | "UNSUPPORTED";
  citations: AIMessageCitation[];
  authority_citations: AIMessageAuthorityCitation[];
  claims: AIMessageClaim[];
  uncertainties: string[];
  warnings: string[];
  disclaimer: string;
  model: string;
  latency_ms: number;
}

export interface AIConversationItem {
  id: string;
  case_id: string;
  title?: string | null;
  status?: string;
  created_at: string;
  updated_at?: string;
}

// ----------------------------------------------------------------------------
// SEARCH
// ----------------------------------------------------------------------------

export interface RetrievedEvidenceItem {
  chunk_id: string;
  document_id: string;
  case_id: string;
  document_version: number;
  document_category: string;
  source_filename: string;
  page_start: number;
  page_end: number;
  content: string;
  score: number;
  lexical_score?: number | null;
  semantic_score?: number | null;
}

export interface CaseSearchResponseItem {
  query: string;
  search_mode: string;
  total_results: number;
  results: RetrievedEvidenceItem[];
}

export interface RetrievedLegalAuthorityItem {
  source_id: string;
  version_id: string;
  canonical_identifier: string;
  canonical_provision_id: string;
  name: string;
  short_title?: string | null;
  section_number: string;
  version_label: string;
  title: string;
  content: string;
  source_type: string;
  authority_level: number;
  jurisdiction: string;
  citation_standard?: string | null;
  effective_from?: string | null;
  effective_to?: string | null;
  is_current: boolean;
  score: number;
  lexical_score?: number | null;
  semantic_score?: number | null;
}

export interface LegalAuthoritySearchResponse {
  query: string;
  search_mode: string;
  total_results: number;
  results: RetrievedLegalAuthorityItem[];
}

// ----------------------------------------------------------------------------
// LAWYERS & CONSULTATIONS
// ----------------------------------------------------------------------------

export interface LawyerAvailabilitySlot {
  id: string;
  lawyer_id: string;
  day_of_week: "MONDAY" | "TUESDAY" | "WEDNESDAY" | "THURSDAY" | "FRIDAY" | "SATURDAY" | "SUNDAY";
  start_time: string;
  end_time: string;
  is_active: boolean;
}

export interface LawyerProfileItem {
  id: string;
  user_id: string;
  full_name: string;
  location?: string;
  practice_areas?: string[] | string;
  experience_years?: number;
  court_jurisdictions?: string[];
  consultation_fee?: number;
  bio?: string;
  verification_status?: "PENDING" | "VERIFIED" | "REJECTED";
}

export interface ConsultationItem {
  id: string;
  client_id: string;
  lawyer_id: string;
  case_id?: string;
  scheduled_start: string;
  scheduled_end: string;
  status: "PENDING" | "CONFIRMED" | "COMPLETED" | "CANCELLED" | "NO_SHOW";
  notes?: string;
  meeting_url?: string;
  fee_amount?: number;
  created_at: string;
}

export interface VerificationItem {
  id: string;
  lawyer_profile_id: string;
  enrollment_number: string;
  state_bar_council: string;
  status: string;
  created_at: string;
  lawyer_name?: string;
}

// ----------------------------------------------------------------------------
// NOTIFICATIONS
// ----------------------------------------------------------------------------

export interface NotificationItem {
  id: string;
  user_id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  case_id?: string;
  document_id?: string;
  deadline_id?: string;
  hearing_id?: string;
  created_at: string;
}

// ----------------------------------------------------------------------------
// ADMIN: JOBS, METRICS & LEGAL DATA
// ----------------------------------------------------------------------------

export interface BackgroundJobItem {
  id: string;
  job_type: string;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "RETRYING" | "CANCELLED";
  attempt_count: number;
  max_attempts: number;
  scheduled_at: string;
  started_at?: string;
  completed_at?: string;
  last_error?: string;
  error_category?: string;
  created_at: string;
}

export interface MetricsSnapshotItem {
  uptime_seconds: number;
  total_http_requests: number;
  status_distribution: Record<string, number>;
  top_endpoints: Record<string, number>;
  latency_ms: {
    avg: number;
    p95: number;
    samples_count: number;
  };
  ai_operations: Record<string, number>;
}

// ----------------------------------------------------------------------------
// MATTER COLLABORATION & COMMUNICATION 4.0
// ----------------------------------------------------------------------------

export interface CaseMessageItem {
  id: string;
  case_id: string;
  sender_id: string;
  sender_name: string;
  sender_role: string;
  content: string;
  message_type: "GENERAL" | "FORMAL_NOTICE" | "STATUS_UPDATE" | "DOCUMENT_SUBMISSION" | "ACTION_REQUEST";
  linked_document_id?: string | null;
  linked_document_title?: string | null;
  linked_task_id?: string | null;
  linked_task_title?: string | null;
  is_counsel_only: boolean;
  created_at: string;
}

export interface MatterRequestItem {
  id: string;
  case_id: string;
  requesting_user_id: string;
  requesting_user_name: string;
  assigned_user_id?: string | null;
  assigned_user_name?: string | null;
  title: string;
  description: string;
  request_type: "DOCUMENT_UPLOAD" | "INFORMATION_REQUEST" | "CONFIRMATION" | "REVIEW";
  status: "PENDING" | "SUBMITTED" | "REVIEWED" | "CANCELLED";
  due_date?: string | null;
  submitted_document_id?: string | null;
  submitted_document_title?: string | null;
  submitted_document_status?: string | null;
  response_notes?: string | null;
  submitted_at?: string | null;
  reviewed_at?: string | null;
  reviewed_by_user_id?: string | null;
  reviewed_by_user_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MatterParticipantDetailItem {
  id: string;
  user_id: string;
  case_id: string;
  participant_role: string;
  status: string;
  full_name: string;
  email: string;
  phone?: string | null;
  lawyer_bar_number?: string | null;
  lawyer_specialization?: string | null;
  lawyer_firm_name?: string | null;
  client_organization?: string | null;
  joined_at: string;
}

export interface MatterBriefItem {
  case_id: string;
  title: string;
  status: string;
  created_at: string;
  lead_counsel_name?: string | null;
  participants_count: number;
  open_requests_count: number;
  next_hearing_date?: string | null;
  next_hearing_court?: string | null;
  recent_documents_count: number;
  pending_tasks_count: number;
}

export interface FunnelStepItem {
  step: string;
  count: number;
  conversion_rate: number;
}

export interface AIEvaluationSummaryItem {
  total_evaluations: number;
  avg_grounding_score: number;
  avg_citation_score: number;
  failure_rate: number;
}

export interface ProductHealthItem {
  total_users: number;
  active_matters: number;
  total_documents_uploaded: number;
  copilot_queries_count: number;
  actions_completed_count: number;
  funnel: FunnelStepItem[];
  ai_health: AIEvaluationSummaryItem;
  unresolved_feedback_p0_p1: number;
  unresolved_feedback_total: number;
}

export interface PilotFeedbackItem {
  id: string;
  user_id?: string | null;
  user_email?: string | null;
  category: string;
  description: string;
  page_url: string;
  status: string;
  priority?: string | null;
  resolution_notes?: string | null;
  created_at: string;
}

