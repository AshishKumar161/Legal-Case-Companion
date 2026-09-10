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
  status: "DRAFT" | "OPEN" | "IN_REVIEW" | "PENDING_COURT" | "IN_PROGRESS" | "CLOSED" | "CANCELLED" | "ARCHIVED";
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
  verification_status: "AI_SUGGESTED" | "AI_VERIFIED" | "AI_GENERATED" | "SYSTEM_RULE" | "SYSTEM_GENERATED" | "USER_PROVIDED" | "LAWYER_VERIFIED" | "OFFICIAL_SOURCE" | "HUMAN_CONFIRMED" | "USER_REPORTED" | "CONTESTED" | "UNVERIFIED";
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
  status: "PENDING" | "IN_PROGRESS" | "BLOCKED" | "COMPLETED" | "CANCELLED";
  due_date?: string | null;
  owner_user_id?: string | null;
  created_by_user_id?: string | null;
  is_confirmed: boolean;
  source_type?: string;
  linked_evidence_id?: string | null;
  linked_hearing_id?: string | null;
  linked_deadline_id?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface CaseDeadlineItem {
  id: string;
  case_id: string;
  title: string;
  description?: string | null;
  deadline_at: string;
  deadline_type: "STATUTORY_LIMITATION" | "COURT_ORDERED" | "FILING" | "COMPLIANCE" | "GENERAL" | "CUSTOM" | string;
  status: "UPCOMING" | "DUE" | "OVERDUE" | "COMPLETED" | "CANCELLED";
  is_confirmed: boolean;
  source_type?: string;
  source_reference?: string | null;
  linked_hearing_id?: string | null;
  retrieval_method?: string | null;
  retrieved_at?: string | null;
  confirmed_by_user_id?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface CaseHealthSummary {
  case_id: string;
  has_upcoming_hearing: boolean;
  next_hearing_date?: string | null;
  next_hearing_court?: string | null;
  overdue_tasks_count: number;
  upcoming_deadlines_count: number;
  unreviewed_evidence_count: number;
  latest_activity_at?: string | null;
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

export interface ClientProfileItem {
  id: string;
  user_id: string;
  full_name: string;
  location?: string;
  email?: string;
  phone?: string;
}

export interface LawyerProfileItem {
  id: string;
  user_id: string;
  full_name: string;
  location?: string;
  email?: string;
  phone?: string;
  practice_areas?: string[] | string;
  experience_years?: number;
  court_jurisdictions?: string[];
  languages?: string[];
  consultation_fee?: number;
  bio?: string;
  verification_status?: "PENDING" | "VERIFIED" | "REJECTED" | "APPROVED" | "UNDER_REVIEW";
  is_online?: boolean;
  match_reasons?: string[];
}

export interface NotificationPreferenceItem {
  email_enabled: boolean;
  case_updates: boolean;
  task_updates: boolean;
  consultation_updates: boolean;
}

export interface ConsultationItem {
  id: string;
  client_id: string;
  lawyer_id: string;
  case_id?: string;
  scheduled_start: string;
  scheduled_end: string;
  status:
    | "REQUESTED"
    | "ACCEPTED"
    | "PAID"
    | "SCHEDULED"
    | "IN_PROGRESS"
    | "COMPLETED"
    | "CANCELLED"
    | "REJECTED"
    | "NO_SHOW"
    | "PENDING"
    | "CONFIRMED";
  notes?: string;
  meeting_url?: string;
  fee_amount?: number;
  currency?: string;
  duration_minutes?: number;
  rejection_reason?: string;
  scheduled_at?: string;
  lawyer_name?: string;
  client_name?: string;
  created_at: string;
}

export interface ConsultationNoteItem {
  id: string;
  consultation_id: string;
  author_user_id: string;
  author_role: string;
  summary: string;
  action_items?: string[];
  client_shared: boolean;
  created_at: string;
  updated_at?: string;
}

export interface SlotItem {
  start_time: string;
  end_time: string;
  duration_minutes: number;
}

export interface LawyerPublicItem {
  id: string;
  user_id?: string;
  full_name: string;
  location?: string;
  practice_areas?: string[];
  primary_practice_area?: string;
  experience_years?: number;
  court_jurisdictions?: string[];
  languages?: string[];
  consultation_fee?: number;
  bio?: string;
  verification_status?: string;
  is_available?: boolean;
}

export interface LawyerAvailabilityItem {
  id: string;
  lawyer_profile_id?: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  slot_duration_minutes?: number;
  is_active: boolean;
}

export type PaymentStatus =
  | "CREATED"
  | "PENDING"
  | "SUCCEEDED"
  | "FAILED"
  | "REFUNDED";

export interface PaymentItem {
  id: string;
  consultation_id: string;
  payer_user_id: string;
  amount: number;
  currency: string;
  status: PaymentStatus;
  provider: string;
  created_at: string;
}

export interface PaymentIntentResponse {
  payment_id: string;
  client_secret: string;
  amount: number;
  currency: string;
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
  read_at?: string | null;
  case_id?: string | null;
  consultation_id?: string | null;
  task_id?: string | null;
  deadline_id?: string | null;
  hearing_id?: string | null;
  document_id?: string | null;
  event_id?: string | null;
  metadata?: Record<string, unknown> | null;
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

// ----------------------------------------------------------------------------
// ADMIN & PLATFORM OPERATIONS
// ----------------------------------------------------------------------------

export interface AdminOverviewItem {
  total_users: number;
  active_users: number;
  suspended_users: number;
  total_lawyers: number;
  pending_verifications: number;
  verified_lawyers: number;
  total_cases: number;
  active_cases: number;
  closed_cases: number;
  total_consultations: number;
  paid_consultations: number;
  scheduled_consultations: number;
  total_payments: number;
  succeeded_payments: number;
  total_revenue_inr: number;
  total_documents: number;
  quarantined_documents: number;
  rejected_documents: number;
  security_event_count: number;
}

export interface AdminUserItem {
  id: string;
  email: string;
  full_name: string;
  role: "CLIENT" | "LAWYER" | "ADMIN";
  account_status: "ACTIVE" | "SUSPENDED" | "PENDING_VERIFICATION" | "DELETED";
  created_at: string;
  updated_at: string;
}

export interface AdminCaseItem {
  id: string;
  title: string;
  description: string;
  status: "OPEN" | "IN_PROGRESS" | "CLOSED" | "CANCELLED";
  created_at: string;
  updated_at: string;
  participant_count: number;
  document_count: number;
  owner_email?: string | null;
}

export interface AdminConsultationItem {
  id: string;
  client_id: string;
  lawyer_id: string;
  case_id?: string | null;
  status: string;
  fee_amount: number;
  currency: string;
  scheduled_start: string;
  scheduled_end: string;
  meeting_url?: string | null;
  created_at: string;
}

export interface AdminPaymentItem {
  id: string;
  consultation_id: string;
  payer_user_id: string;
  amount: number;
  currency: string;
  status: string;
  provider: string;
  provider_payment_id?: string | null;
  created_at: string;
}

export interface AdminDocumentSecurityItem {
  id: string;
  case_id: string;
  filename: string;
  mime_type: string;
  file_size: number;
  security_status: string;
  created_at: string;
}

export interface AdminSecurityEventItem {
  id: string;
  actor_user_id?: string | null;
  event_type: string;
  entity_type?: string | null;
  entity_id?: string | null;
  action: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface AuditEventItem {
  id: string;
  actor_user_id?: string | null;
  event_type: string;
  entity_type?: string | null;
  entity_id?: string | null;
  action: string;
  timestamp: string;
  metadata_?: Record<string, unknown>;
}

// ----------------------------------------------------------------------------
// CASE SUMMARY REPORT EXPORT
// ----------------------------------------------------------------------------

export interface CaseReportMetadata {
  report_id: string;
  generated_at: string;
  generated_by_user_id: string;
  generated_by_name: string;
  generated_by_role: string;
}

export interface CaseOverviewReportItem {
  case_id: string;
  case_number?: string | null;
  title: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ParticipantReportItem {
  id: string;
  user_id: string;
  full_name: string;
  email?: string | null;
  participant_role: string;
  status: string;
  joined_at: string;
}

export interface HearingReportItem {
  id: string;
  court_name: string;
  bench_judge?: string | null;
  hearing_date: string;
  purpose?: string | null;
  outcome?: string | null;
  status: string;
}

export interface DeadlineReportItem {
  id: string;
  title: string;
  deadline_type: string;
  deadline_at: string;
  status: string;
  description?: string | null;
}

export interface TaskReportItem {
  id: string;
  title: string;
  description?: string | null;
  priority: string;
  status: string;
  due_date?: string | null;
  completed_at?: string | null;
  assignee_name?: string | null;
}

export interface DocumentReportItem {
  id: string;
  name: string;
  category: string;
  security_status: string;
  mime_type?: string | null;
  file_size_bytes?: number | null;
  created_at: string;
}

export interface TimelineReportItem {
  id: string;
  event_type: string;
  description: string;
  created_at: string;
  actor_user_id?: string | null;
}

export interface ConsultationReportItem {
  id: string;
  lawyer_name?: string | null;
  scheduled_at: string;
  status: string;
  duration_minutes?: number | null;
  fee_amount?: number | null;
  currency?: string | null;
}

export interface CommunicationsSummaryReportItem {
  total_messages: number;
  total_requests: number;
  latest_activity_at?: string | null;
}

export interface NoteReportItem {
  id: string;
  title?: string | null;
  content: string;
  visibility: string;
  author_name?: string | null;
  created_at: string;
}

export interface CaseSummaryReportResponse {
  metadata: CaseReportMetadata;
  case_overview: CaseOverviewReportItem;
  participants: ParticipantReportItem[];
  hearings: HearingReportItem[];
  deadlines: DeadlineReportItem[];
  tasks: TaskReportItem[];
  documents: DocumentReportItem[];
  timeline: TimelineReportItem[];
  consultations: ConsultationReportItem[];
  communications_summary: CommunicationsSummaryReportItem;
  notes: NoteReportItem[];
}

// ----------------------------------------------------------------------------
// VIDEO RECORDINGS & IN-APP CONSULTATION MEETING
// ----------------------------------------------------------------------------

export type VideoRecordingStatus =
  | "PENDING"
  | "CONSENTED"
  | "RECORDING"
  | "UPLOADING"
  | "PROCESSING"
  | "AVAILABLE"
  | "FAILED";

export interface VideoRecordingItem {
  id: string;
  consultation_id: string;
  case_id?: string | null;
  recording_type: string;
  status: VideoRecordingStatus;
  started_at?: string | null;
  ended_at?: string | null;
  duration_seconds?: number | null;
  file_size_bytes?: number | null;
  mime_type: string;
  checksum_sha256?: string | null;
  playback_url?: string | null;
  created_at: string;
}

export interface RecordingConsentStatus {
  consultation_id: string;
  client_consented: boolean;
  lawyer_consented: boolean;
  can_record: boolean;
}

export interface VideoRoomAccessStatus {
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
  lawyer_online?: boolean | null;
  time_bypass_allowed?: boolean | null;
}

export interface ShareableParticipant {
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  has_access: boolean;
  current_access_level?: "VIEW" | "DOWNLOAD" | "MANAGE" | null;
  grant_id?: string | null;
}

export interface EvidenceAccessGrantItem {
  id: string;
  evidence_id: string;
  grantee_user_id: string;
  granted_by_user_id: string;
  grantee_name?: string | null;
  grantee_email?: string | null;
  access_level: "VIEW" | "DOWNLOAD" | "MANAGE";
  created_at: string;
  expires_at?: string | null;
  revoked_at?: string | null;
  revocation_reason?: string | null;
}

export interface SharedEvidenceItem {
  id: string;
  case_id: string;
  case_title: string;
  title: string;
  description?: string | null;
  category: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  access_level: "VIEW" | "DOWNLOAD" | "MANAGE";
  granted_by_name: string;
  granted_at: string;
  expires_at?: string | null;
  version_number: number;
  sha256: string;
}

export interface InMeetingChatMessage {
  id: string;
  sender_id: string;
  sender_name: string;
  sender_role: string;
  content: string;
  timestamp: string;
}

export interface ConsultationPricingResponse {
  lawyer_id: string;
  duration_minutes: number;
  fee_amount: number;
  gst_rate: number;
  gst_amount: number;
  platform_fee: number;
  total_amount: number;
  currency: string;
  breakdown: {
    cgst: number;
    sgst: number;
    description: string;
  };
}

// ----------------------------------------------------------------------------
// Phase 7.4 Court Tracking & Calendar Types
// ----------------------------------------------------------------------------

export interface CourtHearingHistoryItem {
  date: string;
  judge: string;
  business: string;
  next_date?: string | null;
  hearing_id?: string | null;
}

export interface CourtCauseListItem {
  court_room: string;
  item_number: string;
  cause_list_date: string;
  bench: string;
  board_status: string;
}

export interface CourtOrderItem {
  title: string;
  order_date: string;
  pages: number;
  sha256: string;
  document_id?: string | null;
}

export interface CourtCaseSummary {
  id: string;
  cnr: string;
  case_number: string;
  case_type: string;
  court_name: string;
  bench?: string | null;
  petitioner: string;
  respondent: string;
  petitioner_advocate?: string | null;
  respondent_advocate?: string | null;
  technical_status: string;
  human_status: string;
  next_hearing_date?: string | null;
  next_hearing_purpose?: string | null;
  source_provenance: string;
  last_synchronized_at: string;
  sync_status: string;
  case_id?: string | null;
  is_followed: boolean;
}

export interface CourtCaseDetail extends CourtCaseSummary {
  filing_number?: string | null;
  filing_date?: string | null;
  registration_date?: string | null;
  court_room?: string | null;
  item_number?: string | null;
  acts_and_sections?: string | null;
  history: CourtHearingHistoryItem[];
  cause_list?: CourtCauseListItem | null;
  orders: CourtOrderItem[];
}

export interface CalendarEventItem {
  id: string;
  type: "hearing" | "limitation" | "consultation" | "task";
  type_label: string;
  scheduled_at: string;
  month: string;
  day: string;
  time_display: string;
  title: string;
  case_id?: string | null;
  case_name: string;
  case_ref: string;
  forum: string;
  action_tip: string;
  technical_term?: string | null;
  source: string;
  action_label: string;
  action_href: string;
  is_urgent: boolean;
  source_type?: string | null;
  source_id?: string | null;
  start_at?: string | null;
  end_at?: string | null;
  status?: string | null;
  priority?: string | null;
  category?: string | null;
  lawyer_details?: {
    court?: string;
    court_room?: string;
    item_number?: string;
    bench?: string;
    status?: string;
    petitioner_advocate?: string | null;
    respondent_advocate?: string | null;
    deadline_type?: string;
    duration_minutes?: number;
    fee?: number;
    priority?: string;
    is_confirmed?: boolean;
  } | null;
}

export interface CalendarEventsResponse {
  events: CalendarEventItem[];
  total: number;
  next_attention_event?: CalendarEventItem | null;
  timeframe?: string | null;
  range_start?: string | null;
  range_end?: string | null;
}

// ----------------------------------------------------------------------------
// LAWYER OPERATIONAL DASHBOARD (PHASE 13)
// ----------------------------------------------------------------------------

export interface OperationalAttentionItem {
  item_id: string;
  item_type:
    | "OVERDUE_TASK"
    | "OVERDUE_DEADLINE"
    | "IMMINENT_HEARING"
    | "APPROACHING_DEADLINE"
    | "UNREVIEWED_EVIDENCE";
  title: string;
  case_id: string;
  case_title: string;
  severity: "URGENT" | "WARNING" | "INFO";
  reason: string;
  action_href: string;
  action_label: string;
  due_at?: string | null;
}

export interface TodayAgendaItem {
  id: string;
  event_type: "HEARING" | "DEADLINE" | "TASK" | "CONSULTATION";
  title: string;
  scheduled_at: string;
  time_display: string;
  case_id?: string | null;
  case_title: string;
  court_info?: string | null;
  status: string;
  priority?: string | null;
  action_href: string;
  action_label: string;
  is_urgent: boolean;
}

export interface UpcomingHearingSummary {
  hearing_id: string;
  case_id: string;
  case_title: string;
  court_name: string;
  courtroom?: string | null;
  bench?: string | null;
  purpose?: string | null;
  hearing_at: string;
  time_display: string;
  status: string;
  preparation_tasks_total: number;
  preparation_tasks_completed: number;
  exhibits_count: number;
  bundle_status?: string | null;
  action_href: string;
}

export interface UpcomingDeadlineSummary {
  deadline_id: string;
  case_id: string;
  case_title: string;
  title: string;
  deadline_at: string;
  time_display: string;
  status: string;
  source: string;
  retrieval_method?: string | null;
  is_urgent: boolean;
  action_href: string;
}

export interface AssignedMatterSummary {
  case_id: string;
  title: string;
  case_number?: string | null;
  status: string;
  court_name?: string | null;
  next_hearing_at?: string | null;
  next_hearing_purpose?: string | null;
  overdue_tasks_count: number;
  active_deadlines_count: number;
  unreviewed_evidence_count: number;
  bundle_status?: string | null;
  last_activity_at?: string | null;
  action_href: string;
}

export interface LawyerOperationalMetrics {
  active_cases_count: number;
  upcoming_hearings_count: number;
  overdue_tasks_count: number;
  upcoming_deadlines_count: number;
  pending_consultations_count: number;
  unread_notifications_count: number;
}

export interface LawyerDashboardResponse {
  metrics: LawyerOperationalMetrics;
  today_agenda: TodayAgendaItem[];
  needs_attention: OperationalAttentionItem[];
  upcoming_hearings: UpcomingHearingSummary[];
  upcoming_deadlines: UpcomingDeadlineSummary[];
  high_priority_tasks: TodayAgendaItem[];
  assigned_matters: AssignedMatterSummary[];
  range_days: number;
}

// ----------------------------------------------------------------------------
// EVIDENTIARY BUNDLES & BSA SECTION 63 CERTIFICATES (PHASE 11)
// ----------------------------------------------------------------------------

export type BundleStatus = "DRAFT" | "GENERATING" | "FINALIZED" | "FAILED";

export interface BundleItem {
  id: string;
  bundle_id: string;
  evidence_id: string;
  evidence_version_id: string;
  order_index: number;
  exhibit_label?: string | null;
  bates_start?: string | null;
  bates_end?: string | null;
  page_count: number;
  evidence_title?: string | null;
  original_filename?: string | null;
  sha256_hash?: string | null;
  mime_type?: string | null;
  file_size_bytes?: number | null;
}

export interface BSACertificateDraftItem {
  id: string;
  bundle_id: string;
  case_id: string;
  created_by_user_id: string;
  statutory_reference: string;
  declarant_name: string;
  declarant_designation: string;
  declarant_organization?: string | null;
  device_description: string;
  device_serial_number?: string | null;
  lawful_control_declaration: string;
  operational_condition_declaration: string;
  is_confirmed: boolean;
  is_draft: boolean;
  certificate_pdf_storage_key?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceBundleItemDetail {
  id: string;
  case_id: string;
  hearing_id?: string | null;
  created_by_user_id: string;
  title: string;
  description?: string | null;
  bates_prefix: string;
  bates_start_number: number;
  status: BundleStatus;
  finalized_at?: string | null;
  bundle_pdf_storage_key?: string | null;
  bundle_sha256?: string | null;
  total_pages: number;
  total_size_bytes: number;
  created_at: string;
  updated_at: string;
  item_count: number;
  items?: BundleItem[];
  manifest_data?: Record<string, unknown> | null;
  certificate_drafts?: BSACertificateDraftItem[];
}

// ----------------------------------------------------------------------------
// ADVOCATE VERIFICATION & PRACTICE COMPLIANCE (PHASE 14)
// ----------------------------------------------------------------------------

export type AdvocateDocumentType =
  | "BAR_COUNCIL_ENROLLMENT_CERTIFICATE"
  | "CERTIFICATE_OF_PRACTICE"
  | "IDENTITY_DOCUMENT"
  | "PROPORTIONAL_PRACTICE_CREDENTIAL"
  | "RESIDENCE_ADDRESS_SUPPORT";

export type DocumentVerificationStatus =
  | "NOT_SUBMITTED"
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "NEEDS_RESUBMISSION";

export type DocumentScanStatus = "PENDING" | "CLEAN" | "FLAGGED" | "UNSUPPORTED";

export type AdvocateVerificationStatus =
  | "DRAFT"
  | "PENDING"
  | "UNDER_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "NEEDS_INFO"
  | "REVOKED";

export interface AdvocateVerificationDocumentItem {
  id: string;
  document_type: AdvocateDocumentType;
  original_filename: string;
  file_size: number;
  mime_type: string;
  sha256_hash: string;
  scan_status: DocumentScanStatus;
  verification_status: DocumentVerificationStatus;
  rejection_reason?: string | null;
  created_at: string;
}

export interface VerificationReviewEventItem {
  id: string;
  reviewer_id?: string | null;
  from_status?: string | null;
  to_status: string;
  decision: string;
  verification_method?: string | null;
  verification_source?: string | null;
  source_reference?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface AdvocateVerificationDetail {
  id: string;
  lawyer_profile_id: string;
  user_id?: string | null;
  full_name?: string | null;
  enrollment_number?: string | null;
  state_bar_council?: string | null;
  status: AdvocateVerificationStatus;
  declared_practice_jurisdictions?: string[];
  verification_source?: string | null;
  source_reference?: string | null;
  verification_method?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  last_reviewed_at?: string | null;
  expires_at?: string | null;
  reviewer_notes?: string | null;
  rejection_reason_category?: string | null;
  created_at: string;
  updated_at: string;
  documents: AdvocateVerificationDocumentItem[];
  missing_documents: AdvocateDocumentType[];
  review_events: VerificationReviewEventItem[];
}

export interface VerificationQueueItem {
  id: string;
  lawyer_profile_id: string;
  full_name: string;
  email?: string | null;
  enrollment_number: string;
  state_bar_council: string;
  status: AdvocateVerificationStatus;
  submitted_documents_count: number;
  missing_documents: string[];
  submitted_at?: string | null;
  last_reviewed_at?: string | null;
  reviewer_name?: string | null;
}

export interface VerificationQueueResponse {
  items: VerificationQueueItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface PublicVerificationBadge {
  lawyer_id: string;
  is_verified: boolean;
  verification_badge_text: string;
  verified_at?: string | null;
  expires_at?: string | null;
  state_bar_council?: string | null;
  enrollment_number_masked?: string | null;
  verification_method?: string | null;
  verification_source?: string | null;
  compliance_declaration: string;
}




