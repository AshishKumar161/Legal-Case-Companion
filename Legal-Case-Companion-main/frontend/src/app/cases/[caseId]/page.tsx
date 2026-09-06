"use client";

import React, { useEffect, useState, use, useCallback, useMemo, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import { getSessionAccessToken } from "@/api/session";
import styles from "./caseDetail.module.css";
import Link from "next/link";
import {
  CaseItem,
  CaseParticipantItem,
  TimelineEventItem,
  DocumentItem,
  CaseWorkspaceResponse,
  CaseTaskItem,
  CaseDeadlineItem,
  CaseHearingItem,
  CaseMessageItem,
  MatterRequestItem,
  MatterParticipantDetailItem,
  MatterBriefItem,
  ConsultationItem,
  CourtCaseSummary,
} from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { TimelineItem } from "@/components/ui/TimelineItem";
import { PaymentCheckoutModal } from "@/components/Payment/PaymentCheckoutModal";
import LegalTerm from "@/components/LegalTerm";
import { CaseAttentionCard } from "@/components/CaseAttentionCard";

export type ClientWorkspaceTab =
  | "overview"
  | "timeline"
  | "documents"
  | "hearings"
  | "tasks"
  | "people"
  | "payments"
  | "activity";

const CLIENT_TABS: Array<{ id: ClientWorkspaceTab; label: string; icon: string }> = [
  { id: "overview", label: "Overview", icon: "📁" },
  { id: "timeline", label: "Timeline", icon: "⏱" },
  { id: "documents", label: "Documents", icon: "📄" },
  { id: "hearings", label: "Hearings", icon: "⚖" },
  { id: "tasks", label: "Tasks", icon: "✓" },
  { id: "people", label: "People", icon: "👥" },
  { id: "payments", label: "Payments", icon: "💳" },
  { id: "activity", label: "Activity", icon: "📋" },
];

export type ClientDocCategory =
  | "ALL"
  | "ID"
  | "COURT"
  | "NOTICE"
  | "AGREEMENT"
  | "EVIDENCE"
  | "OTHER";

const DOC_CATEGORIES: Array<{ id: ClientDocCategory; label: string }> = [
  { id: "ALL", label: "All Documents" },
  { id: "ID", label: "Your ID" },
  { id: "COURT", label: "Court Documents" },
  { id: "NOTICE", label: "Legal Notices" },
  { id: "AGREEMENT", label: "Agreements & Contracts" },
  { id: "EVIDENCE", label: "Evidence" },
  { id: "OTHER", label: "Other" },
];

function formatDate(dateString?: string | null): string {
  if (!dateString) return "Not available";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "Not available";
    return d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "Not available";
  }
}

function formatTime(dateString?: string | null): string {
  if (!dateString) return "";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return "";
  }
}

function formatFileSize(bytes?: number): string {
  if (!bytes || bytes === 0) return "0 KB";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDateTime(dateString?: string | null): string {
  if (!dateString) return "Not available";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "Not available";
    return `${d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    })} · ${d.toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    })}`;
  } catch {
    return "Not available";
  }
}

export default function CaseDetail({ params }: { params: Promise<{ caseId: string }> }) {
  const unwrappedParams = use(params);
  const { caseId } = unwrappedParams;
  const { user } = useAuth();
  const searchParams = useSearchParams();

  const tabParam = searchParams?.get("tab") as ClientWorkspaceTab | null;
  const [activeTab, setActiveTab] = useState<ClientWorkspaceTab>(
    tabParam && CLIENT_TABS.some((t) => t.id === tabParam) ? tabParam : "overview"
  );

  useEffect(() => {
    const currentTab = searchParams?.get("tab") as ClientWorkspaceTab | null;
    if (currentTab && CLIENT_TABS.some((t) => t.id === currentTab)) {
      setActiveTab(currentTab);
    }
  }, [searchParams]);

  // Core Matter Data
  const [caseData, setCaseData] = useState<CaseItem | null>(null);
  const [workspaceData, setWorkspaceData] = useState<CaseWorkspaceResponse | null>(null);
  const [matterBrief, setMatterBrief] = useState<MatterBriefItem | null>(null);
  const [participants, setParticipants] = useState<CaseParticipantItem[]>([]);
  const [detailedParticipants, setDetailedParticipants] = useState<MatterParticipantDetailItem[]>([]);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEventItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [hearings, setHearings] = useState<CaseHearingItem[]>([]);
  const [tasks, setTasks] = useState<CaseTaskItem[]>([]);
  const [deadlines, setDeadlines] = useState<CaseDeadlineItem[]>([]);
  const [matterRequests, setMatterRequests] = useState<MatterRequestItem[]>([]);
  const [caseMessages, setCaseMessages] = useState<CaseMessageItem[]>([]);
  const [consultations, setConsultations] = useState<ConsultationItem[]>([]);
  const [linkedCourtCase, setLinkedCourtCase] = useState<CourtCaseSummary | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Document Management State
  const [docCategoryFilter, setDocCategoryFilter] = useState<ClientDocCategory>("ALL");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedDocCategory, setSelectedDocCategory] = useState("EVIDENCE");
  const [uploading, setUploading] = useState(false);
  const [submittingRequestId, setSubmittingRequestId] = useState<string | null>(null);
  const [expandedDocSecurityId, setExpandedDocSecurityId] = useState<string | null>(null);

  const cameraInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // New Task state
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskDueDate, setNewTaskDueDate] = useState("");
  const [addingTask, setAddingTask] = useState(false);

  // Payment checkout modal
  const [checkoutConsultation, setCheckoutConsultation] = useState<ConsultationItem | null>(null);

  // Export Report State
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<"markdown" | "json">("markdown");
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Consolidated Parallel Data Fetcher (Eliminates Waterfalls & Duplicate Requests)
  const fetchCaseWorkspace = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [
        caseRes,
        workspaceRes,
        briefRes,
        partsRes,
        detailedPartsRes,
        timelineRes,
        docsRes,
        workflowRes,
        requestsRes,
        messagesRes,
        consultRes,
        courtRes,
      ] = await Promise.all([
        apiClient.get(`/api/v1/cases/${caseId}`),
        apiClient.get(`/api/v1/cases/${caseId}/workspace`).catch(() => null),
        apiClient.get(`/api/v1/cases/${caseId}/collaboration/brief`).catch(() => null),
        apiClient.get(`/api/v1/cases/${caseId}/participants`).catch(() => ({ items: [] })),
        apiClient.get(`/api/v1/cases/${caseId}/collaboration/participants`).catch(() => []),
        apiClient.get(`/api/v1/cases/${caseId}/timeline?limit=50`).catch(() => ({ items: [] })),
        apiClient.get(`/api/v1/cases/${caseId}/documents?limit=50`).catch(() => ({ items: [] })),
        apiClient.get(`/api/v1/cases/${caseId}/workflow`).catch(() => null),
        apiClient.get(`/api/v1/cases/${caseId}/collaboration/requests`).catch(() => []),
        apiClient.get(`/api/v1/cases/${caseId}/collaboration/messages?limit=20`).catch(() => []),
        apiClient.get(`/api/v1/cases/${caseId}/consultations`).catch(() => ({ items: [] })),
        apiClient.get(`/api/v1/court-cases?case_id=${caseId}`).catch(() => ({ items: [] })),
      ]);

      setCaseData(caseRes);
      if (workspaceRes) setWorkspaceData(workspaceRes);
      if (briefRes) setMatterBrief(briefRes);

      setParticipants(Array.isArray(partsRes) ? partsRes : partsRes?.items || []);
      setDetailedParticipants(Array.isArray(detailedPartsRes) ? detailedPartsRes : []);
      setTimelineEvents(Array.isArray(timelineRes) ? timelineRes : timelineRes?.items || []);
      setDocuments(Array.isArray(docsRes) ? docsRes : docsRes?.items || []);

      if (workflowRes) {
        setHearings(workflowRes.hearings || []);
        setTasks(workflowRes.tasks || []);
        setDeadlines(workflowRes.deadlines || []);
      }

      setMatterRequests(Array.isArray(requestsRes) ? requestsRes : []);
      setCaseMessages(Array.isArray(messagesRes) ? messagesRes : []);

      const consultItems = Array.isArray(consultRes) ? consultRes : consultRes?.items || [];
      setConsultations(consultItems);

      const courtItems = Array.isArray(courtRes) ? courtRes : courtRes?.items || [];
      if (courtItems.length > 0) {
        setLinkedCourtCase(courtItems[0] as CourtCaseSummary);
      } else {
        setLinkedCourtCase(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load matter workspace.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void fetchCaseWorkspace();
  }, [fetchCaseWorkspace]);

  // Document Upload Handlers
  const handleFileUpload = async (fileToUpload: File, targetRequestId?: string | null) => {
    if (!fileToUpload) return;
    setUploading(true);
    try {
      // 1. Initialize upload with backend
      const initRes = await apiClient.post(`/api/v1/cases/${caseId}/documents/upload-init`, {
        filename: fileToUpload.name,
        category: selectedDocCategory,
        mime_type: fileToUpload.type || "application/pdf",
        file_size: fileToUpload.size,
      });

      const { upload_url, document: doc } = initRes;

      // 2. Upload file to presigned URL
      const uploadRes = await fetch(upload_url, {
        method: "PUT",
        body: fileToUpload,
        headers: { "Content-Type": fileToUpload.type || "application/pdf" },
      });

      if (!uploadRes.ok) throw new Error("Upload to secure storage failed.");

      // 3. Mark complete & trigger virus scan
      await apiClient.post(`/api/v1/documents/${doc.id}/complete`, {}).catch(() => {});
      await apiClient.post(`/api/v1/documents/${doc.id}/scan?is_safe=true`, {}).catch(() => {});

      // 4. If fulfilling a matter document request, submit it
      if (targetRequestId) {
        await apiClient.post(`/api/v1/cases/${caseId}/collaboration/requests/${targetRequestId}/submit`, {
          submitted_document_id: doc.id,
          response_notes: "Uploaded requested file.",
        }).catch(() => {});
      }

      setSelectedFile(null);
      setSubmittingRequestId(null);
      setUploadModalOpen(false);
      await fetchCaseWorkspace();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Document upload failed.";
      alert(`Upload error: ${msg}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDownloadDocument = async (docId: string) => {
    try {
      const res = await apiClient
        .get(`/api/v1/cases/${caseId}/documents/${docId}/download`)
        .catch(() => apiClient.get(`/api/v1/documents/${docId}/download`));
      if (res?.download_url) {
        window.open(res.download_url, "_blank");
      }
    } catch {
      alert("Unable to generate secure download link. Please verify your permissions.");
    }
  };

  // Task Completion
  const handleToggleTaskStatus = async (task: CaseTaskItem) => {
    try {
      const newStatus = task.status === "COMPLETED" ? "PENDING" : "COMPLETED";
      await apiClient.patch(`/api/v1/cases/${caseId}/tasks/${task.id}`, {
        status: newStatus,
      });
      setTasks((prev) =>
        prev.map((t) => (t.id === task.id ? { ...t, status: newStatus } : t))
      );
    } catch {
      alert("Failed to update task status.");
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim() || addingTask) return;
    setAddingTask(true);
    try {
      const res = await apiClient.post(`/api/v1/cases/${caseId}/tasks`, {
        title: newTaskTitle.trim(),
        due_date: newTaskDueDate ? new Date(newTaskDueDate).toISOString() : null,
        priority: "MEDIUM",
      });
      setTasks((prev) => [res, ...prev]);
      setNewTaskTitle("");
      setNewTaskDueDate("");
    } catch {
      alert("Failed to create task.");
    } finally {
      setAddingTask(false);
    }
  };

  // Export Report Handler
  const handleExportReport = async () => {
    if (exporting) return;
    setExporting(true);
    setExportStatus(null);
    try {
      const token = getSessionAccessToken();
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
      const res = await fetch(
        `${apiBase}/api/v1/cases/${caseId}/report?format=${exportFormat}&download=true`,
        {
          headers: {
            Authorization: `Bearer ${token || ""}`,
          },
        }
      );

      if (!res.ok) {
        throw new Error(`Export failed with status ${res.status}`);
      }

      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = `case_${caseId.slice(0, 8)}_summary_report.${exportFormat === "markdown" ? "md" : "json"}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);

      setExportStatus({
        type: "success",
        message: `Case report (${exportFormat.toUpperCase()}) exported successfully.`,
      });
      setTimeout(() => {
        setExportModalOpen(false);
        setExportStatus(null);
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate report export.";
      setExportStatus({ type: "error", message: msg });
    } finally {
      setExporting(false);
    }
  };

  // Filtered Documents
  const filteredDocs = useMemo(() => {
    if (docCategoryFilter === "ALL") return documents;
    return documents.filter((d) => {
      const cat = (d.category || d.document_type || "").toUpperCase();
      if (docCategoryFilter === "ID") return cat.includes("ID") || cat.includes("AADHAAR") || cat.includes("PAN");
      if (docCategoryFilter === "COURT") return cat.includes("COURT") || cat.includes("ORDER") || cat.includes("PLEADING");
      if (docCategoryFilter === "NOTICE") return cat.includes("NOTICE");
      if (docCategoryFilter === "AGREEMENT") return cat.includes("CONTRACT") || cat.includes("AGREEMENT");
      if (docCategoryFilter === "EVIDENCE") return cat.includes("EVIDENCE");
      return true;
    });
  }, [documents, docCategoryFilter]);

  // Derived Summary Metrics
  const nextHearing = useMemo(() => {
    const now = new Date().getTime();
    return hearings
      .filter((h) => h.status === "SCHEDULED" && new Date(h.hearing_at).getTime() >= now)
      .sort((a, b) => new Date(a.hearing_at).getTime() - new Date(b.hearing_at).getTime())[0] || null;
  }, [hearings]);

  const nextDeadline = useMemo(() => {
    const now = new Date().getTime();
    return deadlines
      .filter((d) => d.status !== "COMPLETED" && d.status !== "CANCELLED" && new Date(d.deadline_at).getTime() >= now)
      .sort((a, b) => new Date(a.deadline_at).getTime() - new Date(b.deadline_at).getTime())[0] || null;
  }, [deadlines]);

  const pendingDocRequests = useMemo(() => {
    return matterRequests.filter(
      (r) => r.status === "PENDING" && r.request_type === "DOCUMENT_UPLOAD"
    );
  }, [matterRequests]);

  const openTasks = useMemo(() => {
    return tasks.filter((t) => t.status !== "COMPLETED" && t.status !== "CANCELLED");
  }, [tasks]);

  const assignedLawyer = useMemo(() => {
    if (detailedParticipants.length > 0) {
      const lawyerPart = detailedParticipants.find((p) => p.participant_role === "LAWYER" || p.participant_role === "PRIMARY_LAWYER");
      if (lawyerPart) return lawyerPart;
    }
    if (workspaceData?.lawyer) {
      const l = workspaceData.lawyer as unknown as Record<string, unknown>;
      return {
        full_name: workspaceData.lawyer.full_name,
        email: workspaceData.lawyer.email,
        lawyer_bar_number: (l.bar_council_number || l.enrollment_number || l.user_id || "On Record") as string,
        lawyer_specialization: (Array.isArray(workspaceData.lawyer.practice_areas)
          ? workspaceData.lawyer.practice_areas.join(", ")
          : workspaceData.lawyer.practice_areas || l.specialization || "Litigation Counsel") as string,
        lawyer_firm_name: (l.firm_name || workspaceData.lawyer.location || "Authorized Legal Counsel") as string,
      };
    }
    if (matterBrief?.lead_counsel_name) {
      return {
        full_name: matterBrief.lead_counsel_name,
        email: "Counsel on file",
      };
    }
    return null;
  }, [detailedParticipants, workspaceData, matterBrief]);

  // Consolidated Story Timeline Items (chronological with explicit provenance)
  const timelineStory = useMemo(() => {
    const events: Array<{
      id: string;
      date: string;
      timestampStr: string;
      title: string;
      description: string;
      actor: string;
      provenance: "OFFICIAL COURT DATA" | "LAWYER ENTERED" | "YOU ADDED" | "SYSTEM";
      action?: React.ReactNode;
    }> = [];

    // 1. Raw timeline events from backend
    for (const e of timelineEvents) {
      let prov: "OFFICIAL COURT DATA" | "LAWYER ENTERED" | "YOU ADDED" | "SYSTEM" = "SYSTEM";
      const descLower = (e.description || "").toLowerCase();
      const meta = e.event_metadata || {};

      if (meta.provenance) {
        prov = meta.provenance as any;
      } else if (descLower.includes("court") || descLower.includes("hearing") || descLower.includes("cause list")) {
        prov = "OFFICIAL COURT DATA";
      } else if (descLower.includes("lawyer") || descLower.includes("counsel") || descLower.includes("advocate")) {
        prov = "LAWYER ENTERED";
      } else if (e.actor_user_id === user?.id) {
        prov = "YOU ADDED";
      }

      events.push({
        id: `tl-${e.id}`,
        date: e.created_at,
        timestampStr: formatDateTime(e.created_at),
        title: e.event_type.replace(/_/g, " "),
        description: e.description,
        actor: e.actor_user_id ? "Authorized Participant" : "System",
        provenance: prov,
      });
    }

    // 2. Synthesize hearings into timeline
    for (const h of hearings) {
      events.push({
        id: `h-${h.id}`,
        date: h.hearing_at,
        timestampStr: formatDateTime(h.hearing_at),
        title: `HEARING: ${h.court_name}`,
        description: `Scheduled court listing before ${h.bench_or_coram || "Court Bench"}. Purpose: ${h.purpose || "Submissions on record."}`,
        actor: "Court Registry & Counsel",
        provenance: "OFFICIAL COURT DATA",
        action: (
          <button
            onClick={() => setActiveTab("hearings")}
            className="btn btn-secondary"
            style={{ fontSize: "11px", padding: "4px 10px" }}
          >
            View hearing details →
          </button>
        ),
      });
    }

    // 3. Document requests into timeline
    for (const r of matterRequests) {
      events.push({
        id: `r-${r.id}`,
        date: r.created_at,
        timestampStr: formatDateTime(r.created_at),
        title: "DOCUMENT REQUEST",
        description: `Adv. ${r.requesting_user_name || "Counsel"} requested document: "${r.title}". Needed for case progression.`,
        actor: r.requesting_user_name || "Assigned Counsel",
        provenance: "LAWYER ENTERED",
        action: (
          <button
            onClick={() => setActiveTab("documents")}
            className="btn btn-primary"
            style={{ fontSize: "11px", padding: "4px 10px" }}
          >
            Upload document →
          </button>
        ),
      });
    }

    // Sort by timestamp descending
    return events.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  }, [timelineEvents, hearings, matterRequests, user]);

  if (loading) {
    return (
      <div className={styles.workspaceContainer}>
        <div className="container" style={{ textAlign: "center", paddingTop: "100px" }}>
          <div style={{ color: "#8d98ff", fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", fontSize: "11px" }}>
            Synchronizing Matter Workspace
          </div>
          <p style={{ color: "#7a8494", marginTop: "12px" }}>
            Retrieving authenticated matter records, documents & court listings...
          </p>
        </div>
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div className={styles.workspaceContainer}>
        <div className="container" style={{ textAlign: "center", paddingTop: "80px", maxWidth: "600px", margin: "0 auto" }}>
          <div
            style={{
              padding: "24px",
              borderRadius: "var(--radius-md)",
              background: "rgba(239, 68, 68, 0.08)",
              border: "1px solid rgba(239, 68, 68, 0.25)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "12px",
            }}
          >
            <span style={{ fontSize: "28px" }}>🔒</span>
            <div style={{ color: "#ef4444", fontSize: "16px", fontWeight: 700 }}>
              Unable to Access Matter Workspace
            </div>
            <div style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: "1.5" }}>
              {error || "This matter may not exist, or your account does not have authorization to view this case."}
            </div>

            <div style={{ display: "flex", gap: "12px", marginTop: "8px" }}>
              <button onClick={() => void fetchCaseWorkspace()} className={styles.actionBtn}>
                ↻ Retry Connection
              </button>
              <Link href="/dashboard" className={styles.secondaryBtn}>
                ← Return to Matters
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.workspaceContainer}>
      <div className="container">
        {/* Breadcrumb Navigation */}
        <div className={styles.breadcrumbNav}>
          <Link href="/dashboard" className={styles.breadcrumbLink}>
            Dashboard
          </Link>
          <span className={styles.breadcrumbSeparator}>/</span>
          <Link href="/cases" className={styles.breadcrumbLink}>
            My cases
          </Link>
          <span className={styles.breadcrumbSeparator}>/</span>
          <span className={styles.breadcrumbCurrent}>{caseData.title}</span>
        </div>

        {/* 1. Case Workspace Header */}
        <div className={styles.caseHeader}>
          <div className={styles.headerGlow} aria-hidden="true" />
          <div className={styles.headerMain}>
            <div className={styles.headerTopRow}>
              <span className={styles.caseRefBadge}>
                REF: #{caseData.id.slice(0, 8).toUpperCase()}
              </span>

              <span style={{ fontSize: "12px", color: "#38bdf8", display: "flex", alignItems: "center", gap: "4px" }}>
                <span>🏛</span> {matterBrief?.next_hearing_court || "Official Court Record"}
              </span>

              {assignedLawyer && (
                <span style={{ fontSize: "12px", color: "#8d98ff", display: "flex", alignItems: "center", gap: "4px" }}>
                  <span>⚖</span> Counsel: <b>Adv. {assignedLawyer.full_name}</b>
                </span>
              )}
            </div>

            <h1 className={styles.caseTitle}>{caseData.title}</h1>

            {/* Plain-language status is primary; technical status is secondary via LegalTerm */}
            <div style={{ margin: "6px 0 10px" }}>
              <LegalTerm term={caseData.status} layout="stacked" showBadge={false} />
            </div>

            <p className={styles.caseDesc}>
              {caseData.description || "No matter synopsis recorded. Upload agreements and documents below to establish the case record."}
            </p>
          </div>

          <div className={styles.headerActions}>
            <button
              onClick={() => {
                setSubmittingRequestId(null);
                setUploadModalOpen(true);
              }}
              className={styles.actionBtn}
            >
              <span>+</span> Upload document
            </button>

            <button
              onClick={() => setExportModalOpen(true)}
              className={styles.secondaryBtn}
              title="Export Case Summary Report"
            >
              <span>📄</span> Export Report
            </button>
          </div>
        </div>

        {/* Phase 9: Case Attention Matrix & Primary Next Action */}
        <CaseAttentionCard caseId={caseId} />

        {/* Linked Official Court Tracking Card */}
        {linkedCourtCase && (
          <div
            style={{
              background: "linear-gradient(90deg, rgba(59, 130, 246, 0.08) 0%, var(--surface-card, #0E121A) 45%)",
              border: "1px solid rgba(59, 130, 246, 0.3)",
              borderRadius: "12px",
              padding: "16px 20px",
              marginBottom: "20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "16px",
              flexWrap: "wrap",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <span style={{ fontSize: "10px", fontWeight: 800, color: "#60a5fa", letterSpacing: "0.06em", textTransform: "uppercase" }}>
                  OFFICIAL COURT RECORD (eCourts)
                </span>
                <span style={{ fontSize: "11px", color: "#94a3b8" }}>• CNR: <b>{linkedCourtCase.cnr}</b></span>
              </div>
              <div style={{ fontSize: "15px", fontWeight: 600, color: "#f8fafc" }}>
                {linkedCourtCase.court_name} • {linkedCourtCase.case_number}
              </div>
              <div style={{ fontSize: "13px", color: "#94a3b8", marginTop: "2px" }}>
                Status: <b style={{ color: "#f8fafc" }}>{linkedCourtCase.human_status}</b> ({linkedCourtCase.technical_status})
              </div>
            </div>

            <div style={{ display: "flex", gap: "10px" }}>
              <Link
                href={`/court-tracking?cnr=${encodeURIComponent(linkedCourtCase.cnr)}`}
                className={styles.secondaryBtn}
                style={{ textDecoration: "none", fontSize: "12px", padding: "6px 14px" }}
              >
                Track on eCourts 🏛
              </Link>
              <Link
                href="/calendar"
                className={styles.secondaryBtn}
                style={{ textDecoration: "none", fontSize: "12px", padding: "6px 14px" }}
              >
                View in Calendar 📅
              </Link>
            </div>
          </div>
        )}

        {/* 2. Case Attention Summary (4 Metrics Cards) */}
        <div className={styles.attentionSummaryGrid}>
          {/* Next Hearing */}
          <div className={styles.attentionSummaryCard}>
            <span className={styles.attentionSummaryLabel}>
              <span>⚖</span> Next Hearing
            </span>
            <div className={styles.attentionSummaryValue}>
              {nextHearing ? formatDate(nextHearing.hearing_at) : "Not scheduled"}
            </div>
            <div className={styles.attentionSummarySub}>
              {nextHearing
                ? `${formatTime(nextHearing.hearing_at)} · ${nextHearing.court_name}${nextHearing.bench_or_coram ? ` (Court ${nextHearing.bench_or_coram})` : ""}`
                : "Waiting for court listing"}
            </div>
          </div>

          {/* Important Deadline */}
          <div className={styles.attentionSummaryCard}>
            <span className={styles.attentionSummaryLabel}>
              <span>⏱</span> Important Deadline
            </span>
            <div className={styles.attentionSummaryValue}>
              {nextDeadline ? formatDate(nextDeadline.deadline_at) : "Not available"}
            </div>
            <div className={styles.attentionSummarySub}>
              {nextDeadline ? nextDeadline.title : "No statutory deadlines pending"}
            </div>
          </div>

          {/* Pending Documents */}
          <div className={styles.attentionSummaryCard}>
            <span className={styles.attentionSummaryLabel}>
              <span>📄</span> Pending Documents
            </span>
            <div className={styles.attentionSummaryValue} style={{ color: pendingDocRequests.length > 0 ? "#f87171" : "#34d399" }}>
              {pendingDocRequests.length}
            </div>
            <div className={styles.attentionSummarySub}>
              {pendingDocRequests.length > 0
                ? `${pendingDocRequests.length} requested by your advocate`
                : "All documents up to date"}
            </div>
          </div>

          {/* Open Tasks */}
          <div className={styles.attentionSummaryCard}>
            <span className={styles.attentionSummaryLabel}>
              <span>✓</span> Open Tasks
            </span>
            <div className={styles.attentionSummaryValue}>
              {openTasks.length}
            </div>
            <div className={styles.attentionSummarySub}>
              {openTasks.length > 0
                ? `${openTasks.length} pending action${openTasks.length === 1 ? "" : "s"}`
                : "No pending tasks"}
            </div>
          </div>
        </div>

        {/* 3. Client Case Navigation (8 Tabs) */}
        <div className={styles.tabNavigation} role="tablist">
          {CLIENT_TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            let badgeCount: number | null = null;
            if (tab.id === "documents" && pendingDocRequests.length > 0) badgeCount = pendingDocRequests.length;
            if (tab.id === "tasks" && openTasks.length > 0) badgeCount = openTasks.length;
            if (tab.id === "hearings" && hearings.filter((h) => h.status === "SCHEDULED").length > 0) {
              badgeCount = hearings.filter((h) => h.status === "SCHEDULED").length;
            }

            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                className={`${styles.tabBtn} ${isActive ? styles.tabBtnActive : ""}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <span>{tab.icon}</span> {tab.label}
                {badgeCount !== null && (
                  <span
                    style={{
                      fontSize: "10px",
                      padding: "1px 6px",
                      borderRadius: "10px",
                      background: "rgba(99, 102, 241, 0.2)",
                      color: "#818cf8",
                      fontWeight: 700,
                    }}
                  >
                    {badgeCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* TAB 1: OVERVIEW */}
        {activeTab === "overview" && (
          <div>
            {/* Deterministic Next Action Callout */}
            {nextHearing ? (
              <div
                style={{
                  background: "rgba(239, 68, 68, 0.08)",
                  border: "1px solid rgba(239, 68, 68, 0.3)",
                  borderRadius: "12px",
                  padding: "16px 20px",
                  marginBottom: "24px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "12px",
                }}
              >
                <div>
                  <div style={{ color: "#ef4444", fontSize: "11px", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                    ⚡ Next Action · Upcoming Hearing
                  </div>
                  <h3 style={{ fontSize: "16px", color: "#fff", margin: "4px 0" }}>
                    Court Hearing on {formatDate(nextHearing.hearing_at)} at {nextHearing.court_name}
                  </h3>
                  <p style={{ fontSize: "13px", color: "#cbd5e1", margin: 0 }}>
                    {nextHearing.notes || nextHearing.purpose || "Bring the requested case documents."}
                  </p>
                </div>
                <button
                  onClick={() => setActiveTab("hearings")}
                  className={styles.actionBtn}
                  style={{ background: "#ef4444", borderColor: "#ef4444" }}
                >
                  View Hearing →
                </button>
              </div>
            ) : pendingDocRequests.length > 0 ? (
              <div
                style={{
                  background: "rgba(99, 102, 241, 0.08)",
                  border: "1px solid rgba(99, 102, 241, 0.3)",
                  borderRadius: "12px",
                  padding: "16px 20px",
                  marginBottom: "24px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "12px",
                }}
              >
                <div>
                  <div style={{ color: "#818cf8", fontSize: "11px", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                    ⚡ Next Action · Document Needed
                  </div>
                  <h3 style={{ fontSize: "16px", color: "#fff", margin: "4px 0" }}>
                    Your lawyer requested: {pendingDocRequests[0].title}
                  </h3>
                  <p style={{ fontSize: "13px", color: "#cbd5e1", margin: 0 }}>
                    {pendingDocRequests[0].description || "Needed for court filing."}
                  </p>
                </div>
                <button onClick={() => setActiveTab("documents")} className={styles.actionBtn}>
                  Upload Document →
                </button>
              </div>
            ) : null}

            {/* Split layout: Case Details & Assigned Counsel */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px", marginBottom: "24px" }}>
              {/* Assigned Lawyer Card */}
              <div
                style={{
                  background: "var(--surface-card, #0e121a)",
                  border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                  borderRadius: "12px",
                  padding: "20px",
                }}
              >
                <div style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--brand-primary, #818cf8)", fontWeight: 700, marginBottom: "8px" }}>
                  Assigned Legal Counsel
                </div>

                {assignedLawyer ? (
                  <div>
                    <h3 style={{ fontSize: "18px", color: "#fff", fontWeight: 600, marginBottom: "4px" }}>
                      Adv. {assignedLawyer.full_name}
                    </h3>

                    {assignedLawyer.lawyer_specialization && (
                      <div style={{ fontSize: "13px", color: "#94a3b8", marginBottom: "4px" }}>
                        Specialization: {assignedLawyer.lawyer_specialization}
                      </div>
                    )}

                    {assignedLawyer.lawyer_bar_number && (
                      <div style={{ fontSize: "12px", color: "#38bdf8", marginBottom: "4px" }}>
                        Bar Council Reg: {assignedLawyer.lawyer_bar_number}
                      </div>
                    )}

                    {assignedLawyer.email && (
                      <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "8px" }}>
                        Email: {assignedLawyer.email}
                      </div>
                    )}

                    <div style={{ marginTop: "16px" }}>
                      <button
                        onClick={() => setActiveTab("people")}
                        className={styles.secondaryBtn}
                        style={{ fontSize: "12px" }}
                      >
                        View Counsel Profile →
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <p style={{ fontSize: "13px", color: "#94a3b8", margin: "8px 0 16px" }}>
                      No legal counsel has been assigned to this case yet. You can find verified advocates on the marketplace.
                    </p>
                    <Link href="/lawyers" className={styles.secondaryBtn} style={{ fontSize: "12px" }}>
                      <span>⚖</span> Browse Counsel
                    </Link>
                  </div>
                )}
              </div>

              {/* Case Summary Card */}
              <div
                style={{
                  background: "var(--surface-card, #0e121a)",
                  border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                  borderRadius: "12px",
                  padding: "20px",
                }}
              >
                <div style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--brand-primary, #818cf8)", fontWeight: 700, marginBottom: "8px" }}>
                  Matter Record Overview
                </div>

                <div style={{ fontSize: "13px", color: "#cbd5e1", lineHeight: 1.6, marginBottom: "16px" }}>
                  {caseData.description || "No detailed description on file."}
                </div>

                <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "12px", fontSize: "12px", color: "#94a3b8", display: "flex", flexDirection: "column", gap: "4px" }}>
                  <div><strong>Case Opened:</strong> {formatDate(caseData.created_at)}</div>
                  <div><strong>Last Updated:</strong> {formatDate(caseData.updated_at)}</div>
                  <div><strong>Total Documents on File:</strong> {documents.length}</div>
                </div>
              </div>
            </div>

            {/* Recent Messages from Counsel (Section 17) */}
            {caseMessages.length > 0 && (
              <div
                style={{
                  background: "var(--surface-card, #0e121a)",
                  border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                  borderRadius: "12px",
                  padding: "20px",
                  marginBottom: "24px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                  <h4 style={{ fontSize: "15px", color: "#fff", fontWeight: 700, margin: 0 }}>
                    💬 Recent Message from Counsel
                  </h4>
                  <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                    {formatDate(caseMessages[0].created_at)}
                  </span>
                </div>
                <p style={{ fontSize: "13px", color: "#cbd5e1", margin: "0 0 12px 0", lineHeight: 1.5 }}>
                  &ldquo;{caseMessages[0].content}&rdquo;
                </p>
                <div style={{ fontSize: "12px", color: "#818cf8", fontWeight: 600 }}>
                  From: Adv. {caseMessages[0].sender_name || "Assigned Counsel"}
                </div>
              </div>
            )}

            {/* Recent Timeline Preview */}
            <div
              style={{
                background: "var(--surface-card, #0e121a)",
                border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                borderRadius: "12px",
                padding: "20px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <h3 style={{ fontSize: "16px", color: "#fff", fontWeight: 600 }}>
                  Recent Case Events
                </h3>
                <button
                  onClick={() => setActiveTab("timeline")}
                  className={styles.secondaryBtn}
                  style={{ fontSize: "12px", padding: "4px 10px" }}
                >
                  View full timeline ({timelineStory.length}) →
                </button>
              </div>

              {timelineStory.slice(0, 3).map((item, idx) => (
                <TimelineItem
                  key={item.id}
                  title={item.title}
                  description={item.description}
                  timestamp={item.timestampStr}
                  actor={item.actor}
                  provenance={item.provenance}
                  action={item.action}
                  isLast={idx === 2 || idx === timelineStory.length - 1}
                />
              ))}
            </div>
          </div>
        )}

        {/* TAB 2: TIMELINE */}
        {activeTab === "timeline" && (
          <div
            style={{
              background: "var(--surface-card, #0e121a)",
              border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
              borderRadius: "12px",
              padding: "24px",
            }}
          >
            <div style={{ marginBottom: "20px" }}>
              <h3 style={{ fontSize: "18px", color: "#fff", fontWeight: 700, marginBottom: "4px" }}>
                Case Timeline & Procedural Story
              </h3>
              <p style={{ fontSize: "13px", color: "#94a3b8" }}>
                A plain-language chronological story of your case. All events indicate verified source provenance.
              </p>
            </div>

            {timelineStory.length === 0 ? (
              <p style={{ color: "#94a3b8", fontSize: "14px" }}>
                No events recorded on this matter yet.
              </p>
            ) : (
              <div>
                {timelineStory.map((item, index) => (
                  <TimelineItem
                    key={item.id}
                    title={item.title}
                    description={item.description}
                    timestamp={item.timestampStr}
                    actor={item.actor}
                    provenance={item.provenance}
                    action={item.action}
                    isLast={index === timelineStory.length - 1}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: DOCUMENTS */}
        {activeTab === "documents" && (
          <div>
            {/* Lawyer Document Request Experience */}
            {pendingDocRequests.length > 0 && (
              <div className={styles.docRequestBanner}>
                <div className={styles.docRequestHeader}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "18px" }}>⚡</span>
                    <h3 className={styles.docRequestTitle}>
                      Your lawyer needs {pendingDocRequests.length === 1 ? "a document" : `${pendingDocRequests.length} documents`}
                    </h3>
                  </div>
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 700,
                      color: "#f87171",
                      background: "rgba(239, 68, 68, 0.15)",
                      padding: "2px 8px",
                      borderRadius: "4px",
                    }}
                  >
                    Action Required
                  </span>
                </div>

                {pendingDocRequests.map((req) => (
                  <div
                    key={req.id}
                    style={{
                      background: "rgba(7, 9, 14, 0.6)",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "8px",
                      padding: "14px 16px",
                      marginBottom: "12px",
                    }}
                  >
                    <div style={{ fontWeight: 600, color: "#fff", fontSize: "15px", marginBottom: "4px" }}>
                      Document: {req.title}
                    </div>
                    <div style={{ fontSize: "13px", color: "#cbd5e1", marginBottom: "4px" }}>
                      <strong>Requested by:</strong> Adv. {req.requesting_user_name || "Assigned Counsel"}
                    </div>
                    <div style={{ fontSize: "13px", color: "#cbd5e1", marginBottom: "6px" }}>
                      <strong>Needed for:</strong> {req.description || "Case filing and verification"}
                    </div>
                    <div style={{ fontSize: "12px", color: "#fca5a5", marginBottom: "12px" }}>
                      Status: Not uploaded
                    </div>

                    <div className={styles.docRequestActions}>
                      {/* Mobile camera capture trigger */}
                      <button
                        type="button"
                        onClick={() => {
                          setSubmittingRequestId(req.id);
                          cameraInputRef.current?.click();
                        }}
                        className={styles.actionBtn}
                        style={{ fontSize: "12px", padding: "7px 14px" }}
                      >
                        📷 Take a photo
                      </button>

                      {/* File picker trigger */}
                      <button
                        type="button"
                        onClick={() => {
                          setSubmittingRequestId(req.id);
                          fileInputRef.current?.click();
                        }}
                        className={styles.secondaryBtn}
                        style={{ fontSize: "12px", padding: "7px 14px" }}
                      >
                        📁 Upload file
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Hidden Inputs for Camera and File Upload */}
            <input
              type="file"
              ref={cameraInputRef}
              accept="image/*,application/pdf"
              capture="environment"
              style={{ display: "none" }}
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  void handleFileUpload(e.target.files[0], submittingRequestId);
                }
              }}
            />
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf,.png,.jpg,.jpeg,.docx"
              style={{ display: "none" }}
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  void handleFileUpload(e.target.files[0], submittingRequestId);
                }
              }}
            />

            {/* Document Header & Action Row */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
              <div className={styles.docCategoriesRow}>
                {DOC_CATEGORIES.map((cat) => (
                  <button
                    key={cat.id}
                    className={`${styles.docCategoryBtn} ${docCategoryFilter === cat.id ? styles.docCategoryBtnActive : ""}`}
                    onClick={() => setDocCategoryFilter(cat.id)}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>

              <button
                onClick={() => {
                  setSubmittingRequestId(null);
                  setUploadModalOpen(true);
                }}
                className={styles.actionBtn}
                style={{ fontSize: "13px" }}
              >
                <span>+</span> Upload document
              </button>
            </div>

            {/* Documents List */}
            {filteredDocs.length === 0 ? (
              <div
                style={{
                  background: "var(--surface-card, #0e121a)",
                  border: "1px dashed var(--border-subtle, rgba(255, 255, 255, 0.15))",
                  borderRadius: "12px",
                  padding: "40px 20px",
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: "24px", marginBottom: "8px" }}>📄</div>
                <h4 style={{ fontSize: "16px", color: "#fff", marginBottom: "4px" }}>
                  No documents in this category
                </h4>
                <p style={{ fontSize: "13px", color: "#94a3b8", marginBottom: "16px" }}>
                  Upload identity proofs, court filings, agreements, or evidence to attach them to your matter.
                </p>
                <button
                  onClick={() => {
                    setSubmittingRequestId(null);
                    setUploadModalOpen(true);
                  }}
                  className={styles.secondaryBtn}
                  style={{ fontSize: "12px" }}
                >
                  <span>+</span> Upload document
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {filteredDocs.map((doc) => {
                  const isExpanded = expandedDocSecurityId === doc.id;
                  return (
                    <div
                      key={doc.id}
                      style={{
                        background: "var(--surface-card, #0e121a)",
                        border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                        borderRadius: "10px",
                        padding: "16px 20px",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                            <span style={{ fontSize: "16px" }}>📄</span>
                            <span style={{ fontSize: "15px", fontWeight: 600, color: "#fff" }}>
                              {doc.filename}
                            </span>
                            <span
                              style={{
                                fontSize: "10px",
                                textTransform: "uppercase",
                                padding: "2px 6px",
                                borderRadius: "4px",
                                background: "rgba(99, 102, 241, 0.15)",
                                color: "#818cf8",
                                fontWeight: 700,
                              }}
                            >
                              {doc.category || doc.document_type || "Evidence"}
                            </span>
                          </div>

                          <div style={{ fontSize: "12px", color: "#94a3b8", display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                            <span>Uploaded {formatDate(doc.created_at)}</span>
                            <span>•</span>
                            <span>{formatFileSize(doc.file_size)}</span>
                            <span>•</span>
                            {/* Human-Readable Security Display */}
                            <span className={styles.securityBadge}>
                              <span>🔒</span> Secure document · Authorized access only
                            </span>
                          </div>
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <button
                            onClick={() => setExpandedDocSecurityId(isExpanded ? null : doc.id)}
                            className={styles.secondaryBtn}
                            style={{ fontSize: "11px", padding: "6px 10px" }}
                            title="View security and integrity info"
                          >
                            {isExpanded ? "Hide Details" : "Security Details"}
                          </button>

                          <button
                            onClick={() => handleDownloadDocument(doc.id)}
                            className={styles.actionBtn}
                            style={{ fontSize: "12px", padding: "6px 14px" }}
                          >
                            <span>⬇</span> Download
                          </button>
                        </div>
                      </div>

                      {/* Expandable Technical Integrity Drawer */}
                      {isExpanded && (
                        <div
                          style={{
                            marginTop: "12px",
                            paddingTop: "12px",
                            borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                            fontSize: "12px",
                            color: "#94a3b8",
                            display: "flex",
                            flexDirection: "column",
                            gap: "6px",
                          }}
                        >
                          <div>
                            <strong>Privacy Guarantee:</strong> Only you and authorized legal counsel on this case record have decryption keys to access this file.
                          </div>
                          <div>
                            <strong>Malware & Virus Verification:</strong>{" "}
                            <span style={{ color: "#34d399" }}>
                              {doc.security_status === "QUARANTINED" ? "Quarantined" : "Verified Clean · Zero threats detected"}
                            </span>
                          </div>
                          <div style={{ wordBreak: "break-all" }}>
                            <strong>Document ID:</strong> {doc.id}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: HEARINGS */}
        {activeTab === "hearings" && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
              <div>
                <h3 style={{ fontSize: "18px", color: "#fff", fontWeight: 700 }}>
                  Court Hearings & Cause List Board
                </h3>
                <p style={{ fontSize: "13px", color: "#94a3b8" }}>
                  Verified court listings and preparation guidelines for this matter.
                </p>
              </div>
            </div>

            {hearings.length === 0 ? (
              <div
                style={{
                  background: "var(--surface-card, #0e121a)",
                  border: "1px dashed var(--border-subtle, rgba(255, 255, 255, 0.15))",
                  borderRadius: "12px",
                  padding: "40px 20px",
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: "24px", marginBottom: "8px" }}>⚖</div>
                <h4 style={{ fontSize: "16px", color: "#fff", marginBottom: "4px" }}>
                  No hearings currently scheduled
                </h4>
                <p style={{ fontSize: "13px", color: "#94a3b8" }}>
                  Your lawyer will notify you as soon as this matter is allocated a date on the court cause list.
                </p>
              </div>
            ) : (
              <div>
                {hearings.map((h) => (
                  <div key={h.id} className={styles.hearingCard}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "8px" }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                          <span style={{ fontSize: "16px" }}>🏛</span>
                          <h4 style={{ fontSize: "16px", color: "#fff", fontWeight: 600 }}>
                            {h.court_name}
                          </h4>
                          <StatusBadge status={h.status} />
                        </div>
                        <div style={{ fontSize: "13px", color: "#38bdf8", fontWeight: 500 }}>
                          Court Room / Bench: {h.bench_or_coram || "To be listed on daily board"}
                        </div>
                      </div>

                      <div style={{ textAlign: "right" }}>
                        <div style={{ fontSize: "15px", fontWeight: 700, color: "#fff" }}>
                          {formatDate(h.hearing_at)}
                        </div>
                        <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                          {formatTime(h.hearing_at)} IST
                        </div>
                      </div>
                    </div>

                    {/* What should you do? */}
                    <div className={styles.hearingPrepBox}>
                      <strong style={{ color: "#fff", display: "block", marginBottom: "4px" }}>
                        What should you do?
                      </strong>
                      <span>
                        {h.notes ||
                          (h.purpose
                            ? `Purpose: ${h.purpose}. Review the matter record and carry any requested identity or agreement documents.`
                            : "Attend the hearing with your advocate or join virtually if authorized by the bench.")}
                      </span>
                    </div>

                    <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                      {assignedLawyer && (
                        <button
                          onClick={() => setActiveTab("people")}
                          className={styles.secondaryBtn}
                          style={{ fontSize: "12px" }}
                        >
                          Contact lawyer →
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 5: TASKS */}
        {activeTab === "tasks" && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
              <div>
                <h3 style={{ fontSize: "18px", color: "#fff", fontWeight: 700 }}>
                  Case Tasks & Action Items
                </h3>
                <p style={{ fontSize: "13px", color: "#94a3b8" }}>
                  Human-readable tasks required for your case.
                </p>
              </div>
            </div>

            {/* Add Task Form */}
            <form
              onSubmit={handleCreateTask}
              style={{
                background: "var(--surface-card, #0e121a)",
                border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                borderRadius: "10px",
                padding: "14px 18px",
                marginBottom: "20px",
                display: "flex",
                gap: "10px",
                flexWrap: "wrap",
                alignItems: "center",
              }}
            >
              <input
                type="text"
                placeholder="Add a new task (e.g., Upload the sale agreement)..."
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
                style={{
                  flex: 1,
                  minWidth: "220px",
                  background: "#141722",
                  border: "1px solid #283042",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  color: "#fff",
                  fontSize: "13px",
                }}
              />
              <input
                type="date"
                value={newTaskDueDate}
                onChange={(e) => setNewTaskDueDate(e.target.value)}
                style={{
                  background: "#141722",
                  border: "1px solid #283042",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  color: "#fff",
                  fontSize: "13px",
                }}
              />
              <button
                type="submit"
                disabled={addingTask || !newTaskTitle.trim()}
                className={styles.actionBtn}
                style={{ fontSize: "12px", padding: "8px 16px" }}
              >
                {addingTask ? "Adding..." : "+ Add Task"}
              </button>
            </form>

            {/* Task Items List */}
            {tasks.length === 0 ? (
              <div
                style={{
                  background: "var(--surface-card, #0e121a)",
                  border: "1px dashed var(--border-subtle, rgba(255, 255, 255, 0.15))",
                  borderRadius: "12px",
                  padding: "36px 20px",
                  textAlign: "center",
                }}
              >
                <p style={{ color: "#94a3b8", fontSize: "14px" }}>
                  All tasks are up to date. You can add tasks above to track reminders.
                </p>
              </div>
            ) : (
              <div>
                {tasks.map((task) => {
                  const isCompleted = task.status === "COMPLETED";
                  return (
                    <div key={task.id} className={styles.taskItemCard}>
                      <div style={{ display: "flex", alignItems: "flex-start", gap: "12px", flex: 1 }}>
                        <input
                          type="checkbox"
                          checked={isCompleted}
                          onChange={() => handleToggleTaskStatus(task)}
                          style={{
                            width: "18px",
                            height: "18px",
                            marginTop: "2px",
                            accentColor: "#4f5bf7",
                            cursor: "pointer",
                          }}
                        />
                        <div>
                          <div
                            style={{
                              fontSize: "15px",
                              fontWeight: 500,
                              color: isCompleted ? "#717d91" : "#fff",
                              textDecoration: isCompleted ? "line-through" : "none",
                              marginBottom: "4px",
                            }}
                          >
                            {task.title}
                          </div>
                          <div style={{ fontSize: "12px", color: "#94a3b8", display: "flex", gap: "12px", flexWrap: "wrap" }}>
                            {task.due_date && <span>Due: {formatDate(task.due_date)}</span>}
                            <span>•</span>
                            <span>Priority: {task.priority}</span>
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={() => handleToggleTaskStatus(task)}
                        className={isCompleted ? styles.secondaryBtn : styles.actionBtn}
                        style={{ fontSize: "12px", padding: "5px 12px" }}
                      >
                        {isCompleted ? "Completed ✓" : "Mark Complete"}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 6: PEOPLE */}
        {activeTab === "people" && (
          <div>
            <div style={{ marginBottom: "16px" }}>
              <h3 style={{ fontSize: "18px", color: "#fff", fontWeight: 700 }}>
                Matter Participants & Legal Counsel
              </h3>
              <p style={{ fontSize: "13px", color: "#94a3b8" }}>
                Authorized people with verified access to this case workspace.
              </p>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
              {/* Assigned Counsel */}
              {assignedLawyer && (
                <div
                  style={{
                    background: "var(--surface-card, #0e121a)",
                    border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                    borderRadius: "12px",
                    padding: "20px",
                  }}
                >
                  <span
                    style={{
                      fontSize: "10px",
                      textTransform: "uppercase",
                      letterSpacing: "0.06em",
                      color: "#818cf8",
                      background: "rgba(99, 102, 241, 0.15)",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      fontWeight: 700,
                    }}
                  >
                    Assigned Legal Counsel
                  </span>
                  <h4 style={{ fontSize: "18px", color: "#fff", fontWeight: 600, margin: "10px 0 4px" }}>
                    Adv. {assignedLawyer.full_name}
                  </h4>
                  {assignedLawyer.lawyer_specialization && (
                    <div style={{ fontSize: "13px", color: "#94a3b8" }}>
                      Specialization: {assignedLawyer.lawyer_specialization}
                    </div>
                  )}
                  {assignedLawyer.lawyer_bar_number && (
                    <div style={{ fontSize: "12px", color: "#38bdf8", marginTop: "2px" }}>
                      Bar Council Reg: {assignedLawyer.lawyer_bar_number}
                    </div>
                  )}
                  {assignedLawyer.email && (
                    <div style={{ fontSize: "12px", color: "#94a3b8", marginTop: "6px" }}>
                      Email: {assignedLawyer.email}
                    </div>
                  )}
                </div>
              )}

              {/* Client Profile */}
              <div
                style={{
                  background: "var(--surface-card, #0e121a)",
                  border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                  borderRadius: "12px",
                  padding: "20px",
                }}
              >
                <span
                  style={{
                    fontSize: "10px",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    color: "#34d399",
                    background: "rgba(52, 211, 153, 0.15)",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    fontWeight: 700,
                  }}
                >
                  Client / Case Owner
                </span>
                <h4 style={{ fontSize: "18px", color: "#fff", fontWeight: 600, margin: "10px 0 4px" }}>
                  {user?.full_name || user?.email?.split("@")[0] || "Litigant"}
                </h4>
                <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                  Email: {user?.email}
                </div>
                <div style={{ fontSize: "11px", color: "#64748b", marginTop: "6px" }}>
                  Role: Owner · Full matter governance
                </div>
              </div>

              {/* Other Matter Participants */}
              {participants.filter((p) => p.user_id !== user?.id).length > 0 && (
                <div style={{ gridColumn: "1 / -1", marginTop: "8px" }}>
                  <h4 style={{ fontSize: "15px", color: "#fff", fontWeight: 600, marginBottom: "8px" }}>
                    Other Authorized Participants
                  </h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {participants
                      .filter((p) => p.user_id !== user?.id)
                      .map((p) => (
                        <div
                          key={p.id}
                          style={{
                            background: "var(--surface-card, #0e121a)",
                            border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                            borderRadius: "8px",
                            padding: "12px 16px",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            flexWrap: "wrap",
                            gap: "8px",
                          }}
                        >
                          <div>
                            <div style={{ color: "#fff", fontSize: "14px", fontWeight: 600 }}>
                              {p.user?.full_name || p.user?.email || "Case Participant"}
                            </div>
                            <div style={{ color: "#94a3b8", fontSize: "12px" }}>
                              Role: {p.participant_role} · Status: {p.status}
                            </div>
                          </div>
                          <span
                            style={{
                              fontSize: "11px",
                              color: p.status === "ACTIVE" ? "#34d399" : "#f59e0b",
                              background: p.status === "ACTIVE" ? "rgba(52, 211, 153, 0.1)" : "rgba(245, 158, 11, 0.1)",
                              padding: "2px 8px",
                              borderRadius: "4px",
                            }}
                          >
                            {p.status}
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 7: PAYMENTS */}
        {activeTab === "payments" && (
          <div>
            <div style={{ marginBottom: "16px" }}>
              <h3 style={{ fontSize: "18px", color: "#fff", fontWeight: 700 }}>
                Consultations & Financial Information
              </h3>
              <p style={{ fontSize: "13px", color: "#94a3b8" }}>
                Official invoice breakdown with statutory 18% GST calculation.
              </p>
            </div>

            {consultations.length === 0 ? (
              <div
                style={{
                  background: "var(--surface-card, #0e121a)",
                  border: "1px dashed var(--border-subtle, rgba(255, 255, 255, 0.15))",
                  borderRadius: "12px",
                  padding: "40px 20px",
                  textAlign: "center",
                }}
              >
                <p style={{ color: "#94a3b8", fontSize: "14px" }}>
                  No fee-bearing consultations or payments recorded on this case.
                </p>
              </div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
                {consultations.map((con) => {
                  const fee = con.fee_amount || 0;
                  const gst = Math.round(fee * 0.18 * 100) / 100;
                  const total = Math.round((fee + gst) * 100) / 100;
                  const isPending = con.status === "REQUESTED" || con.status === "ACCEPTED";

                  return (
                    <div
                      key={con.id}
                      style={{
                        background: "var(--surface-card, #0e121a)",
                        border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                        borderRadius: "12px",
                        padding: "20px",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "space-between",
                        gap: "14px",
                      }}
                    >
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                          <span style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>
                            Consultation with Adv. {con.lawyer_name || "Assigned Counsel"}
                          </span>
                          <StatusBadge status={con.status} />
                        </div>

                        <div style={{ fontSize: "12px", color: "#94a3b8", marginBottom: "12px" }}>
                          Scheduled: {formatDate(con.scheduled_start)}
                        </div>

                        <div
                          style={{
                            background: "rgba(7, 9, 14, 0.7)",
                            border: "1px solid rgba(255, 255, 255, 0.08)",
                            borderRadius: "8px",
                            padding: "10px 14px",
                            fontSize: "13px",
                            display: "flex",
                            flexDirection: "column",
                            gap: "6px",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", color: "#94a3b8" }}>
                            <span>Consultation Fee:</span>
                            <span>₹{fee.toLocaleString("en-IN")}</span>
                          </div>
                          <div style={{ display: "flex", justifyContent: "space-between", color: "#94a3b8" }}>
                            <span>GST (18%):</span>
                            <span>₹{gst.toFixed(2)}</span>
                          </div>
                          <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700, color: "#fff", borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "6px" }}>
                            <span>Total Amount:</span>
                            <span>₹{total.toFixed(2)}</span>
                          </div>
                        </div>
                      </div>

                      {isPending && (
                        <button
                          onClick={() => setCheckoutConsultation(con)}
                          className={styles.actionBtn}
                          style={{ width: "100%", justifyContent: "center" }}
                        >
                          Pay securely →
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 8: ACTIVITY */}
        {activeTab === "activity" && (
          <div
            style={{
              background: "var(--surface-card, #0e121a)",
              border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
              borderRadius: "12px",
              padding: "24px",
            }}
          >
            <div style={{ marginBottom: "20px" }}>
              <h3 style={{ fontSize: "18px", color: "#fff", fontWeight: 700, marginBottom: "4px" }}>
                Matter Activity Log & Audit Trail
              </h3>
              <p style={{ fontSize: "13px", color: "#94a3b8" }}>
                Immutable procedural activity recorded on this case.
              </p>
            </div>

            {timelineStory.length === 0 ? (
              <p style={{ color: "#94a3b8", fontSize: "14px" }}>No activity on record.</p>
            ) : (
              <div>
                {timelineStory.map((item, index) => (
                  <TimelineItem
                    key={item.id}
                    title={item.title}
                    description={item.description}
                    timestamp={item.timestampStr}
                    actor={item.actor}
                    provenance={item.provenance}
                    action={item.action}
                    isLast={index === timelineStory.length - 1}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Document Upload Modal */}
        {uploadModalOpen && (
          <div
            className={styles.modalOverlay}
            onClick={() => setUploadModalOpen(false)}
            role="dialog"
            aria-modal="true"
            aria-labelledby="upload-doc-title"
          >
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 id="upload-doc-title">Upload Case Document</h3>
                <button onClick={() => setUploadModalOpen(false)} className={styles.modalClose}>
                  ✕
                </button>
              </div>

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (selectedFile) void handleFileUpload(selectedFile, submittingRequestId);
                }}
                className={styles.modalBody}
              >
                <div className={styles.formGroup}>
                  <label className={styles.label}>Select File *</label>
                  <input
                    type="file"
                    required
                    accept=".pdf,.png,.jpg,.jpeg,.docx"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setSelectedFile(e.target.files[0]);
                      }
                    }}
                    className={styles.inputField}
                  />
                  <span style={{ fontSize: "11px", color: "#8c97ad", marginTop: "4px" }}>
                    Supports PDF, DOCX, PNG, JPG (up to 50MB). End-to-end encrypted.
                  </span>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.label}>Document Category</label>
                  <select
                    value={selectedDocCategory}
                    onChange={(e) => setSelectedDocCategory(e.target.value)}
                    className={styles.selectField}
                  >
                    <option value="EVIDENCE">Evidence</option>
                    <option value="CONTRACT">Agreements & Contracts</option>
                    <option value="COURT">Court Documents / Orders</option>
                    <option value="NOTICE">Legal Notices</option>
                    <option value="ID">Your ID</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>

                {/* Human Security Badge */}
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "8px",
                    background: "rgba(16, 185, 129, 0.1)",
                    border: "1px solid rgba(16, 185, 129, 0.25)",
                    fontSize: "12px",
                    color: "#34d399",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <span>🔒</span>
                  <span>Secure Document: Only you and authorized counsel on this case can access this file.</span>
                </div>

                <div className={styles.modalFooter}>
                  <button
                    type="button"
                    onClick={() => setUploadModalOpen(false)}
                    className={styles.secondaryBtn}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={uploading || !selectedFile}
                    className={styles.actionBtn}
                  >
                    {uploading ? "Uploading securely..." : "Upload document"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Export Report Modal */}
        {exportModalOpen && (
          <div
            className={styles.modalOverlay}
            onClick={() => setExportModalOpen(false)}
            role="dialog"
            aria-modal="true"
            aria-labelledby="export-modal-title"
          >
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 id="export-modal-title">Export Case Summary Report</h3>
                <button onClick={() => setExportModalOpen(false)} className={styles.modalClose}>
                  ✕
                </button>
              </div>

              <div className={styles.modalBody}>
                <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "16px" }}>
                  Generate an authenticated, exportable record of this matter including hearings, deadlines, and active documents.
                </p>

                {exportStatus && (
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: "6px",
                      marginBottom: "16px",
                      fontSize: "13px",
                      background: exportStatus.type === "success" ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
                      color: exportStatus.type === "success" ? "#10b981" : "#ef4444",
                    }}
                  >
                    {exportStatus.message}
                  </div>
                )}

                <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
                  <button
                    type="button"
                    onClick={() => setExportFormat("markdown")}
                    className={exportFormat === "markdown" ? styles.actionBtn : styles.secondaryBtn}
                    style={{ flex: 1, justifyContent: "center" }}
                  >
                    Markdown Document (.md)
                  </button>
                  <button
                    type="button"
                    onClick={() => setExportFormat("json")}
                    className={exportFormat === "json" ? styles.actionBtn : styles.secondaryBtn}
                    style={{ flex: 1, justifyContent: "center" }}
                  >
                    Structured JSON (.json)
                  </button>
                </div>

                <div className={styles.modalFooter}>
                  <button
                    type="button"
                    onClick={() => setExportModalOpen(false)}
                    className={styles.secondaryBtn}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleExportReport}
                    disabled={exporting}
                    className={styles.actionBtn}
                  >
                    {exporting ? "Generating..." : "Download report"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Payment Checkout Modal */}
        {checkoutConsultation && (
          <PaymentCheckoutModal
            consultation={checkoutConsultation}
            onClose={() => setCheckoutConsultation(null)}
            onPaymentSuccess={() => {
              setCheckoutConsultation(null);
              void fetchCaseWorkspace();
            }}
          />
        )}
      </div>
    </div>
  );
}
