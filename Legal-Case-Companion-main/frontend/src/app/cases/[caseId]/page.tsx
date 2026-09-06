"use client";

import React, { useEffect, useState, use, useCallback, useMemo, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
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
  CaseHealthSummary,
} from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { TimelineItem } from "@/components/ui/TimelineItem";
import { PaymentCheckoutModal } from "@/components/Payment/PaymentCheckoutModal";
import { CaseAttentionCard } from "@/components/CaseAttentionCard";
import { CopilotChat } from "@/components/Intelligence/CopilotChat";
import { MatterInbox } from "@/components/Collaboration/MatterInbox";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  CalendarIcon,
  DocumentIcon,
  LawyerIcon,
  ClockIcon,
  PlusIcon,
  AssistantIcon,
  ChatIcon,
} from "@/components/ui/Icons";

export type ClientWorkspaceTab =
  | "overview"
  | "timeline"
  | "documents"
  | "hearings"
  | "tasks"
  | "people"
  | "messages"
  | "payments"
  | "activity";

const CLIENT_TABS: Array<{ id: ClientWorkspaceTab; label: string; icon: string }> = [
  { id: "overview", label: "Overview", icon: "📁" },
  { id: "timeline", label: "Timeline", icon: "⏱" },
  { id: "documents", label: "Documents", icon: "📄" },
  { id: "hearings", label: "Hearings", icon: "⚖" },
  { id: "tasks", label: "Tasks", icon: "✓" },
  { id: "people", label: "People", icon: "👥" },
  { id: "messages", label: "Messages", icon: "💬" },
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
  const router = useRouter();

  interface LawyerCallStatus {
    lawyer_id: string;
    is_online: boolean;
    is_available: boolean;
    is_in_meeting: boolean;
    presence_status: string;
    status_label: string;
    reason?: string;
    can_call_now: boolean;
    active_consultation_id?: string | null;
  }
  const [lawyerCallStatus, setLawyerCallStatus] = useState<LawyerCallStatus | null>(null);
  const [startingCall, setStartingCall] = useState(false);
  const [callError, setCallError] = useState<string | null>(null);

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
  const [whatShouldIDoOpen, setWhatShouldIDoOpen] = useState(false);
  const [showAdvancedTools, setShowAdvancedTools] = useState(false);

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

  // New Task state & Operational Workflow State
  const [healthSummary, setHealthSummary] = useState<CaseHealthSummary | null>(null);
  const [taskStatusFilter, setTaskStatusFilter] = useState<string>("ALL");
  const [taskPriorityFilter, setTaskPriorityFilter] = useState<string>("ALL");
  const [taskSearchQuery, setTaskSearchQuery] = useState<string>("");
  const [templateModalOpen, setTemplateModalOpen] = useState<boolean>(false);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("HEARING_PREPARATION");
  const [templateHearingId, setTemplateHearingId] = useState<string>("");
  const [templateAssigneeId, setTemplateAssigneeId] = useState<string>("");
  const [applyingTemplate, setApplyingTemplate] = useState<boolean>(false);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskDesc, setNewTaskDesc] = useState("");
  const [newTaskDueDate, setNewTaskDueDate] = useState("");
  const [newTaskPriority, setNewTaskPriority] = useState<"LOW" | "MEDIUM" | "HIGH" | "URGENT">("MEDIUM");
  const [newTaskLinkedHearing, setNewTaskLinkedHearing] = useState<string>("");
  const [addingTask, setAddingTask] = useState(false);

  // Payment checkout modal
  const [checkoutConsultation, setCheckoutConsultation] = useState<ConsultationItem | null>(null);

  // Export Report State
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<"markdown" | "json">("markdown");
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // LCC Legal Assistant Modal (Section 12)
  const [copilotModalOpen, setCopilotModalOpen] = useState(false);

  // Quick Reply State for Case Overview
  const [quickReplyText, setQuickReplyText] = useState("");
  const [sendingQuickReply, setSendingQuickReply] = useState(false);

  const handleSendQuickReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickReplyText.trim() || sendingQuickReply) return;
    setSendingQuickReply(true);
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/collaboration/messages`, {
        content: quickReplyText.trim(),
        message_type: "GENERAL",
      });
      setQuickReplyText("");
      // Refresh case messages immediately
      const msgs = (await apiClient.get(`/api/v1/cases/${caseId}/collaboration/messages?limit=20`)) as CaseMessageItem[];
      if (Array.isArray(msgs)) setCaseMessages(msgs);
    } catch (err) {
      console.error("Failed to send quick reply:", err);
    } finally {
      setSendingQuickReply(false);
    }
  };

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
        healthRes,
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
        apiClient.get(`/api/v1/cases/${caseId}/workflow/health-summary`).catch(() => null),
      ]);

      setCaseData(caseRes);
      if (workspaceRes) setWorkspaceData(workspaceRes);
      if (briefRes) setMatterBrief(briefRes);
      if (healthRes) setHealthSummary(healthRes);

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

  // Task Lifecycle Actions
  const handleStartTask = async (taskId: string) => {
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/tasks/${taskId}/start`, {});
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, status: "IN_PROGRESS" } : t))
      );
    } catch {
      alert("Failed to start task.");
    }
  };

  const handleCompleteTaskAction = async (taskId: string) => {
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/tasks/${taskId}/complete`, {});
      setTasks((prev) =>
        prev.map((t) =>
          t.id === taskId ? { ...t, status: "COMPLETED", completed_at: new Date().toISOString() } : t
        )
      );
    } catch {
      alert("Failed to complete task.");
    }
  };

  const handleCancelTaskAction = async (taskId: string) => {
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/tasks/${taskId}/cancel`, {});
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, status: "CANCELLED" } : t))
      );
    } catch {
      alert("Failed to cancel task.");
    }
  };

  const handleReopenTaskAction = async (taskId: string) => {
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/tasks/${taskId}/reopen`, {});
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, status: "IN_PROGRESS", completed_at: null } : t))
      );
    } catch {
      alert("Failed to reopen task.");
    }
  };

  const handleCompleteDeadline = async (deadlineId: string) => {
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/deadlines/${deadlineId}/complete`, {});
      setDeadlines((prev) =>
        prev.map((d) =>
          d.id === deadlineId ? { ...d, status: "COMPLETED", completed_at: new Date().toISOString() } : d
        )
      );
    } catch {
      alert("Failed to complete deadline.");
    }
  };

  const handleCancelDeadline = async (deadlineId: string) => {
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/deadlines/${deadlineId}/cancel`, {});
      setDeadlines((prev) =>
        prev.map((d) => (d.id === deadlineId ? { ...d, status: "CANCELLED" } : d))
      );
    } catch {
      alert("Failed to cancel deadline.");
    }
  };

  const handleApplyWorkflowTemplate = async () => {
    if (applyingTemplate) return;
    setApplyingTemplate(true);
    try {
      const payload: Record<string, unknown> = {
        template_name: selectedTemplate,
      };
      if (templateHearingId) payload.hearing_id = templateHearingId;
      if (templateAssigneeId) payload.assignee_user_id = templateAssigneeId;

      await apiClient.post(`/api/v1/cases/${caseId}/workflow/templates/apply`, payload);
      setTemplateModalOpen(false);
      await fetchCaseWorkspace();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to apply workflow template.";
      alert(msg);
    } finally {
      setApplyingTemplate(false);
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim() || addingTask) return;
    setAddingTask(true);
    try {
      const res = await apiClient.post(`/api/v1/cases/${caseId}/tasks`, {
        title: newTaskTitle.trim(),
        description: newTaskDesc.trim() || null,
        due_date: newTaskDueDate ? new Date(newTaskDueDate).toISOString() : null,
        priority: newTaskPriority,
        linked_hearing_id: newTaskLinkedHearing || null,
      });
      setTasks((prev) => [res, ...prev]);
      setNewTaskTitle("");
      setNewTaskDesc("");
      setNewTaskDueDate("");
      setNewTaskPriority("MEDIUM");
      setNewTaskLinkedHearing("");
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

  const filteredTasksList = useMemo(() => {
    return tasks.filter((t) => {
      if (taskStatusFilter !== "ALL" && t.status !== taskStatusFilter) return false;
      if (taskPriorityFilter !== "ALL" && t.priority !== taskPriorityFilter) return false;
      if (taskSearchQuery.trim()) {
        const q = taskSearchQuery.toLowerCase();
        const inTitle = t.title.toLowerCase().includes(q);
        const inDesc = (t.description || "").toLowerCase().includes(q);
        if (!inTitle && !inDesc) return false;
      }
      return true;
    });
  }, [tasks, taskStatusFilter, taskPriorityFilter, taskSearchQuery]);

  const assignedLawyer = useMemo(() => {
    if (detailedParticipants.length > 0) {
      const lawyerPart = detailedParticipants.find((p) => p.participant_role === "LAWYER" || p.participant_role === "PRIMARY_LAWYER");
      if (lawyerPart) {
        return {
          ...lawyerPart,
          user_id: (lawyerPart.user_id || lawyerPart.id) as string,
          id: (lawyerPart.id || lawyerPart.user_id) as string,
        };
      }
    }
    if (workspaceData?.lawyer) {
      const l = workspaceData.lawyer as unknown as Record<string, unknown>;
      const lid = (l.user_id || l.id || workspaceData.lawyer.id) as string;
      return {
        id: lid,
        user_id: lid,
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
        id: "counsel",
        user_id: "counsel",
        full_name: matterBrief.lead_counsel_name,
        email: "Counsel on file",
      };
    }
    return null;
  }, [detailedParticipants, workspaceData, matterBrief]);

  // Periodic live check of assigned lawyer presence and call availability
  useEffect(() => {
    if (!assignedLawyer) return;
    const lid = assignedLawyer.user_id || assignedLawyer.id;
    if (!lid || lid === "counsel") return;

    const checkCallStatus = async () => {
      try {
        const res = await apiClient.get<LawyerCallStatus>(
          `/api/v1/consultations/lawyer-call-status?lawyer_id=${lid}&case_id=${caseId}`
        );
        if (res) setLawyerCallStatus(res);
      } catch {
        setLawyerCallStatus({
          lawyer_id: lid,
          is_online: true,
          is_available: true,
          is_in_meeting: false,
          presence_status: "AVAILABLE",
          status_label: "Available for Video Call",
          can_call_now: true,
        });
      }
    };
    void checkCallStatus();
    const interval = setInterval(checkCallStatus, 15000);
    return () => clearInterval(interval);
  }, [assignedLawyer, caseId]);

  // Periodic background refresh for live meeting alerts and real-time case messages
  useEffect(() => {
    if (!caseId) return;
    const pollInterval = setInterval(async () => {
      try {
        const [messagesRes, consultRes] = await Promise.all([
          apiClient.get(`/api/v1/cases/${caseId}/collaboration/messages?limit=20`).catch(() => []),
          apiClient.get(`/api/v1/cases/${caseId}/consultations`).catch(() => ({ items: [] })),
        ]);
        if (Array.isArray(messagesRes)) {
          setCaseMessages(messagesRes);
        }
        const consultItems = Array.isArray(consultRes) ? consultRes : (consultRes as any)?.items || [];
        setConsultations(consultItems);
      } catch {
        // silent polling
      }
    }, 4000);
    return () => clearInterval(pollInterval);
  }, [caseId]);

  // Instant Video Call trigger: client or lawyer can conduct video call at any time
  const handleStartInstantVideoCall = async () => {
    setStartingCall(true);
    setCallError(null);
    try {
      const lid = assignedLawyer?.user_id || assignedLawyer?.id || (workspaceData?.lawyer as any)?.id || "01a07113-f687-7363-8225-d2f8ec1c9763";
      const res = await apiClient.post<{ room_url: string; consultation_id: string }>(
        "/api/v1/consultations/instant-call",
        {
          lawyer_id: lid,
          case_id: caseId,
          duration_minutes: 30,
        }
      );
      if (res?.room_url) {
        router.push(res.room_url);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to initiate video call.";
      setCallError(msg);
      setStartingCall(false);
    }
  };

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

        {/* Back Link */}
        <Link href="/cases" className={styles.backLink}>
          <ArrowLeftIcon size={14} />
          <span>Back to My Cases</span>
        </Link>

        {/* 1. Case Header Card */}
        <div className={styles.caseHeaderCard}>
          <div className={styles.headerTopRow}>
            <span className={styles.caseStatusBadge}>
              ● {caseData.status === "CLOSED" ? "Closed Case" : "Active Case"}
            </span>
            <span className={styles.caseRefBadge}>
              REF #{caseData.id.slice(0, 8).toUpperCase()}
            </span>
          </div>

          <h1 className={styles.caseTitle}>{caseData.title}</h1>
          <p className={styles.caseDesc}>
            {caseData.description || "Your case is active. Below is your next event and what you need to do."}
          </p>

          {assignedLawyer && (
            <div style={{ marginTop: "16px", paddingTop: "14px", borderTop: "1px solid var(--border-light, #e2e8f0)", display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--navy-primary, #0f1e36)" }}>
                  Adv. {assignedLawyer.full_name}
                </span>
                {lawyerCallStatus?.is_in_meeting ? (
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "#d97706", background: "#fef3c7", padding: "2px 8px", borderRadius: "10px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                    <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#f59e0b" }}></span>
                    In Meeting
                  </span>
                ) : lawyerCallStatus?.is_online ? (
                  <span style={{ fontSize: "11px", fontWeight: 600, color: "#059669", background: "#d1fae5", padding: "2px 8px", borderRadius: "10px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                    <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#10b981" }}></span>
                    Online & Ready to Call
                  </span>
                ) : (
                  <span style={{ fontSize: "11px", color: "#64748b", background: "#f1f5f9", padding: "2px 8px", borderRadius: "10px" }}>
                    Offline
                  </span>
                )}
              </div>

              <button
                type="button"
                onClick={handleStartInstantVideoCall}
                disabled={startingCall || lawyerCallStatus?.is_in_meeting}
                style={{
                  background: lawyerCallStatus?.is_in_meeting ? "#e2e8f0" : "linear-gradient(135deg, #0f1e36 0%, #1e293b 100%)",
                  color: lawyerCallStatus?.is_in_meeting ? "#64748b" : "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  padding: "8px 14px",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: lawyerCallStatus?.is_in_meeting ? "not-allowed" : "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  boxShadow: lawyerCallStatus?.is_in_meeting ? "none" : "0 2px 4px rgba(15, 30, 54, 0.15)",
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
                <span>{startingCall ? "Connecting..." : lawyerCallStatus?.is_in_meeting ? "Lawyer in another meet" : "Video Call Lawyer →"}</span>
              </button>
            </div>
          )}
        </div>

        {/* Live Video Meeting Banner */}
        {consultations.some((c) => c.status === "IN_PROGRESS" || c.status === "PAID" || c.status === "SCHEDULED" || c.status === "ACCEPTED") && (
          <div
            style={{
              background: "linear-gradient(135deg, rgba(5, 150, 105, 0.15) 0%, rgba(15, 23, 42, 0.95) 100%)",
              border: "2px solid #10b981",
              borderRadius: "14px",
              padding: "16px 20px",
              marginBottom: "16px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "14px",
              boxShadow: "0 4px 20px rgba(16, 185, 129, 0.2)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <span style={{ display: "inline-flex", position: "relative", width: "12px", height: "12px", flexShrink: 0 }}>
                <span style={{ position: "absolute", width: "100%", height: "100%", borderRadius: "50%", background: "#10b981", opacity: 0.75, animation: "ping 1s cubic-bezier(0, 0, 0.2, 1) infinite" }} />
                <span style={{ width: "12px", height: "12px", borderRadius: "50%", background: "#10b981" }} />
              </span>
              <div>
                <div style={{ color: "#34d399", fontSize: "11px", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  🔴 Live Video Consultation
                </div>
                <h3 style={{ fontSize: "16px", color: "#fff", margin: "2px 0 0 0", fontWeight: 700 }}>
                  {user?.role === "LAWYER" ? "Client is In Video Room for this Case" : "Video Meeting with Your Advocate is Ready"}
                </h3>
                <p style={{ fontSize: "12px", color: "#94a3b8", margin: "2px 0 0 0" }}>
                  Consultation session is active. Join directly with case details and documents synchronized.
                </p>
              </div>
            </div>
            {(() => {
              const activeCon = consultations.find((c) => c.status === "IN_PROGRESS" || c.status === "PAID" || c.status === "SCHEDULED" || c.status === "ACCEPTED");
              return activeCon ? (
                <button
                  type="button"
                  onClick={() => router.push(`/consultations/${activeCon.id}/room?bypass_time=true`)}
                  style={{
                    background: "linear-gradient(135deg, #059669 0%, #047857 100%)",
                    border: "none",
                    color: "#fff",
                    fontWeight: 700,
                    fontSize: "13px",
                    padding: "10px 20px",
                    borderRadius: "8px",
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    boxShadow: "0 2px 10px rgba(5, 150, 105, 0.4)",
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
                  <span>Join Video Meeting Now →</span>
                </button>
              ) : null;
            })()}
          </div>
        )}

        {/* 2. Your Next Important Event Banner (Section 7) */}
        <div className={styles.nextEventBanner}>
          <div className={styles.nextEventContent}>
            <div className={styles.nextEventKicker}>Your next important event</div>
            <div className={styles.nextEventDate}>
              <CalendarIcon size={20} color="var(--navy-primary)" />
              <span>{nextHearing ? formatDateTime(nextHearing.hearing_at) : "Waiting for hearing date"}</span>
            </div>
            <div className={styles.nextEventLocation}>
              {nextHearing
                ? `${nextHearing.court_name}${nextHearing.bench_or_coram ? ` · Court ${nextHearing.bench_or_coram}` : ""}`
                : matterBrief?.next_hearing_court || "Official Court Record"}
            </div>
          </div>

          <button
            type="button"
            onClick={() => setWhatShouldIDoOpen((prev) => !prev)}
            className={styles.whatShouldIDoBtn}
          >
            <span>What should I do?</span>
            <ArrowRightIcon size={14} />
          </button>
        </div>

        {/* 3. "What Should I Do?" Simple Guidance Box (Section 7) */}
        {whatShouldIDoOpen && (
          <section className={styles.guidanceBox} aria-label="Action guidance for your case">
            <div className={styles.guidanceHeader}>
              <h3 className={styles.guidanceTitle}>
                <CheckCircleIcon size={20} color="var(--accent-gold)" />
                <span>What you need to do next</span>
              </h3>
              <button
                onClick={() => setWhatShouldIDoOpen(false)}
                style={{ color: "var(--text-muted)", cursor: "pointer", fontSize: "14px" }}
              >
                ✕
              </button>
            </div>

            <ul className={styles.guidanceList}>
              <li className={styles.guidanceItem}>
                <span className={styles.guidanceCheck}>✓</span>
                <div>
                  <strong>Bring your Government Photo ID:</strong> Carry your physical Aadhaar, PAN card, or Voter ID to enter the court complex.
                </div>
              </li>
              <li className={styles.guidanceItem}>
                <span className={styles.guidanceCheck}>✓</span>
                <div>
                  <strong>Bring requested documents:</strong> Ensure you have physical copies of agreements, notices, or payment receipts relevant to today&apos;s stage.
                </div>
              </li>
              <li className={styles.guidanceItem}>
                <span className={styles.guidanceCheck}>✓</span>
                <div>
                  <strong>Speak with your lawyer beforehand:</strong> Confirm your courtroom number ({nextHearing?.bench_or_coram || "registry"}) and check if your physical presence inside the courtroom is required.
                </div>
              </li>
            </ul>

            <div className={styles.guidanceDisclaimer}>
              <strong>What to ask your lawyer:</strong> &ldquo;Will our matter be taken up in the morning session? Do you need any supplementary affidavits or signatures from me today?&rdquo;
            </div>
          </section>
        )}

        {/* 4. Case Progress Stepper (Section 7) */}
        <div className={styles.progressCard}>
          <div className={styles.progressTitle}>Case Progress</div>
          <div className={styles.stepper}>
            {/* 1. Case Started */}
            <div className={styles.stepItem}>
              <div className={`${styles.stepCircle} ${styles.stepCompleted}`}>✓</div>
              <span className={styles.stepLabel}>Case Started</span>
            </div>
            {/* 2. Documents Submitted */}
            <div className={styles.stepItem}>
              <div className={`${styles.stepCircle} ${documents.length > 0 ? styles.stepCompleted : styles.stepCurrent}`}>
                {documents.length > 0 ? "✓" : "2"}
              </div>
              <span className={styles.stepLabel}>Documents Submitted</span>
            </div>
            {/* 3. Lawyer Assigned */}
            <div className={styles.stepItem}>
              <div className={`${styles.stepCircle} ${assignedLawyer ? styles.stepCompleted : documents.length > 0 ? styles.stepCurrent : styles.stepUpcoming}`}>
                {assignedLawyer ? "✓" : "3"}
              </div>
              <span className={styles.stepLabel}>Lawyer Assigned</span>
            </div>
            {/* 4. Next Hearing */}
            <div className={styles.stepItem}>
              <div className={`${styles.stepCircle} ${nextHearing ? styles.stepCurrent : styles.stepUpcoming}`}>
                4
              </div>
              <span className={styles.stepLabel}>Next Hearing</span>
            </div>
            {/* 5. Case Decision */}
            <div className={styles.stepItem}>
              <div className={`${styles.stepCircle} ${caseData.status === "CLOSED" ? styles.stepCompleted : styles.stepUpcoming}`}>
                {caseData.status === "CLOSED" ? "✓" : "5"}
              </div>
              <span className={`${styles.stepLabel} ${caseData.status !== "CLOSED" ? styles.stepLabelUpcoming : ""}`}>
                Case Decision
              </span>
            </div>
          </div>
        </div>

        {/* 5. What would you like to see? (Section 7) */}
        <div className={styles.sectionSwitcher}>
          <div className={styles.sectionSwitcherLabel}>What would you like to see?</div>
          <div className={styles.sectionButtons}>
            <button
              className={`${styles.sectionBtn} ${activeTab === "overview" ? styles.sectionBtnActive : ""}`}
              onClick={() => setActiveTab("overview")}
            >
              <span>Overview</span>
            </button>
            <button
              className={`${styles.sectionBtn} ${activeTab === "messages" ? styles.sectionBtnActive : ""}`}
              onClick={() => setActiveTab("messages")}
            >
              <ChatIcon size={16} />
              <span>Messages ({caseMessages.length})</span>
            </button>
            <button
              className={`${styles.sectionBtn} ${activeTab === "hearings" ? styles.sectionBtnActive : ""}`}
              onClick={() => setActiveTab("hearings")}
            >
              <CalendarIcon size={16} />
              <span>Hearings</span>
            </button>
            <button
              className={`${styles.sectionBtn} ${activeTab === "documents" ? styles.sectionBtnActive : ""}`}
              onClick={() => setActiveTab("documents")}
            >
              <DocumentIcon size={16} />
              <span>Documents ({documents.length})</span>
            </button>
            <button
              className={`${styles.sectionBtn} ${activeTab === "people" ? styles.sectionBtnActive : ""}`}
              onClick={() => setActiveTab("people")}
            >
              <LawyerIcon size={16} />
              <span>{user?.role === "LAWYER" ? "Client & Team" : "My Lawyer"}</span>
            </button>
            <button
              className={`${styles.sectionBtn} ${activeTab === "timeline" ? styles.sectionBtnActive : ""}`}
              onClick={() => setActiveTab("timeline")}
            >
              <ClockIcon size={16} />
              <span>Updates</span>
            </button>
            <button
              className={`${styles.sectionBtn} ${copilotModalOpen ? styles.sectionBtnActive : ""}`}
              onClick={() => setCopilotModalOpen(true)}
            >
              <AssistantIcon size={16} color="var(--gold-accent)" />
              <span>Ask LCC Assistant</span>
            </button>
          </div>

          {/* Progressive Disclosure for Advanced Case Tools */}
          <div style={{ marginTop: "12px" }}>
            <button
              type="button"
              onClick={() => setShowAdvancedTools((prev) => !prev)}
              className={styles.advancedToolsToggle}
            >
              <span>{showAdvancedTools ? "▲ Hide Case Options" : "▼ More Case Options & Tools"}</span>
            </button>

            {showAdvancedTools && (
              <div className={styles.advancedToolsPanel}>
                <button
                  onClick={() => {
                    setSubmittingRequestId(null);
                    setUploadModalOpen(true);
                  }}
                  className="btn btn-primary"
                  style={{ fontSize: "13px" }}
                >
                  <PlusIcon size={14} color="#fff" />
                  <span>Upload Document</span>
                </button>
                <Link href={`/cases/${caseId}/bundles`} className="btn btn-secondary" style={{ fontSize: "13px" }}>
                  <span>Court Bundles</span>
                </Link>
                <Link href={`/cases/${caseId}/evidence`} className="btn btn-secondary" style={{ fontSize: "13px" }}>
                  <span>Evidence Locker</span>
                </Link>
                <button onClick={() => setExportModalOpen(true)} className="btn btn-secondary" style={{ fontSize: "13px" }}>
                  <span>Export Report</span>
                </button>
                <button onClick={() => setActiveTab("tasks")} className="btn btn-secondary" style={{ fontSize: "13px" }}>
                  <span>Tasks & Deadlines</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Case Attention Card for Next Step */}
        <CaseAttentionCard caseId={caseId} />

        {/* TAB 1: OVERVIEW */}
        {activeTab === "overview" && (
          <div>
            {/* Active Consultation Callout */}
            {consultations.some((c) => c.status === "SCHEDULED" || c.status === "IN_PROGRESS" || c.status === "PAID" || c.status === "ACCEPTED") && (
              <div
                style={{
                  background: "linear-gradient(135deg, rgba(37, 99, 235, 0.14) 0%, rgba(16, 185, 129, 0.14) 100%)",
                  border: "1px solid rgba(59, 130, 246, 0.35)",
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
                  <div style={{ color: "#38bdf8", fontSize: "11px", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                    🎥 Active Video Consultation Ready
                  </div>
                  <h3 style={{ fontSize: "16px", color: "#fff", margin: "4px 0" }}>
                    Connect with Your Retained Advocate
                  </h3>
                  <p style={{ fontSize: "13px", color: "#cbd5e1", margin: 0 }}>
                    Discuss case updates face-to-face and exchange documents directly in the video room.
                  </p>
                </div>
                {(() => {
                  const activeCon = consultations.find((c) => c.status === "SCHEDULED" || c.status === "IN_PROGRESS" || c.status === "PAID" || c.status === "ACCEPTED");
                  return activeCon ? (
                    <button
                      onClick={() => router.push(`/consultations/${activeCon.id}/room?bypass_time=true`)}
                      className={styles.actionBtn}
                      style={{
                        background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
                        borderColor: "#2563eb",
                        color: "#fff",
                        fontWeight: 700,
                        padding: "10px 18px",
                      }}
                    >
                      🎥 Join Consultation Room →
                    </button>
                  ) : null;
                })()}
              </div>
            )}

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
                <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                  <Link
                    href={`/cases/${caseId}/bundles?hearingId=${nextHearing.id}`}
                    className={styles.actionBtn}
                    style={{ background: "#4f46e5", borderColor: "#4f46e5", textDecoration: "none" }}
                  >
                    📦 Prepare Bundle
                  </Link>
                  <button
                    onClick={() => setActiveTab("hearings")}
                    className={styles.actionBtn}
                    style={{ background: "#ef4444", borderColor: "#ef4444" }}
                  >
                    View Hearing →
                  </button>
                </div>
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

            {/* Case Communication / Messages Card (Section 17) */}
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
                <h4 style={{ fontSize: "15px", color: "#fff", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                  💬 Matter Messages & Notices ({caseMessages.length})
                </h4>
                <button
                  onClick={() => setActiveTab("messages")}
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                    color: "var(--brand-primary, #6366f1)",
                    background: "rgba(99, 102, 241, 0.12)",
                    border: "1px solid rgba(99, 102, 241, 0.25)",
                    padding: "5px 12px",
                    borderRadius: "6px",
                    cursor: "pointer",
                  }}
                >
                  {user?.role === "LAWYER" ? "Open Client Messaging Panel →" : "Message Assigned Counsel →"}
                </button>
              </div>

              {caseMessages.length > 0 ? (
                <div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "14px" }}>
                    {caseMessages.slice(-3).map((msg) => {
                      const isFromClient = msg.sender_role?.toUpperCase() === "CLIENT" || msg.sender_role?.toUpperCase() === "OWNER";
                      const isMeetingInvite = msg.content?.includes("/consultations/") || msg.content?.includes("video meeting");
                      return (
                        <div
                          key={msg.id}
                          style={{
                            background: isFromClient ? "rgba(14, 165, 233, 0.08)" : "rgba(255, 255, 255, 0.03)",
                            border: `1px solid ${isFromClient ? "rgba(14, 165, 233, 0.25)" : "rgba(255, 255, 255, 0.07)"}`,
                            borderRadius: "8px",
                            padding: "10px 14px",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <span style={{ fontSize: "12px", fontWeight: 700, color: isFromClient ? "#38bdf8" : "#818cf8" }}>
                                {msg.sender_name || (isFromClient ? "Client" : "Counsel")}
                              </span>
                              <span
                                style={{
                                  fontSize: "10px",
                                  fontWeight: 600,
                                  textTransform: "uppercase",
                                  padding: "2px 6px",
                                  borderRadius: "4px",
                                  background: isFromClient ? "rgba(14, 165, 233, 0.2)" : "rgba(99, 102, 241, 0.2)",
                                  color: isFromClient ? "#38bdf8" : "#a5b4fc",
                                }}
                              >
                                {msg.sender_role || (isFromClient ? "Client" : "Counsel")}
                              </span>
                            </div>
                            <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                              {formatDate(msg.created_at)}
                            </span>
                          </div>
                          <p style={{ fontSize: "13px", color: "#cbd5e1", margin: "0", lineHeight: 1.5 }}>
                            {msg.content}
                          </p>
                          {isMeetingInvite && (
                            <div style={{ marginTop: "8px" }}>
                              <button
                                onClick={() => {
                                  const match = msg.content.match(/\/consultations\/([a-zA-Z0-9_-]+)\/room/);
                                  if (match) {
                                    window.open(`/consultations/${match[1]}/room`, "_blank");
                                  } else {
                                    setActiveTab("messages");
                                  }
                                }}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "6px",
                                  fontSize: "12px",
                                  fontWeight: 600,
                                  color: "#fff",
                                  background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                                  border: "none",
                                  padding: "5px 12px",
                                  borderRadius: "6px",
                                  cursor: "pointer",
                                }}
                              >
                                📹 Join Video Consultation Now →
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Inline Quick Reply Form */}
                  <form onSubmit={handleSendQuickReply} style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                    <input
                      type="text"
                      placeholder="Type a quick reply to the client..."
                      value={quickReplyText}
                      onChange={(e) => setQuickReplyText(e.target.value)}
                      style={{
                        flex: 1,
                        background: "rgba(0, 0, 0, 0.3)",
                        border: "1px solid rgba(255, 255, 255, 0.15)",
                        borderRadius: "8px",
                        padding: "8px 12px",
                        fontSize: "13px",
                        color: "#fff",
                        outline: "none",
                      }}
                    />
                    <button
                      type="submit"
                      disabled={sendingQuickReply || !quickReplyText.trim()}
                      style={{
                        background: sendingQuickReply || !quickReplyText.trim() ? "rgba(99, 102, 241, 0.4)" : "#6366f1",
                        color: "#fff",
                        border: "none",
                        borderRadius: "8px",
                        padding: "8px 16px",
                        fontSize: "13px",
                        fontWeight: 600,
                        cursor: sendingQuickReply || !quickReplyText.trim() ? "not-allowed" : "pointer",
                        transition: "background 0.2s",
                      }}
                    >
                      {sendingQuickReply ? "Sending..." : "Reply"}
                    </button>
                  </form>

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <button
                      onClick={() => setActiveTab("messages")}
                      className={styles.secondaryBtn}
                      style={{ fontSize: "12px", padding: "4px 10px" }}
                    >
                      View all {caseMessages.length} messages in detail →
                    </button>
                    <span style={{ fontSize: "11px", color: "#64748b" }}>
                      Auto-synced with client portal
                    </span>
                  </div>
                </div>
              ) : (
                <div>
                  <p style={{ fontSize: "13px", color: "#94a3b8", margin: "0 0 12px 0" }}>
                    No messages recorded on this case yet. Start the conversation with your client below.
                  </p>
                  <form onSubmit={handleSendQuickReply} style={{ display: "flex", gap: "8px" }}>
                    <input
                      type="text"
                      placeholder="Send a message to client..."
                      value={quickReplyText}
                      onChange={(e) => setQuickReplyText(e.target.value)}
                      style={{
                        flex: 1,
                        background: "rgba(0, 0, 0, 0.3)",
                        border: "1px solid rgba(255, 255, 255, 0.15)",
                        borderRadius: "8px",
                        padding: "8px 12px",
                        fontSize: "13px",
                        color: "#fff",
                        outline: "none",
                      }}
                    />
                    <button
                      type="submit"
                      disabled={sendingQuickReply || !quickReplyText.trim()}
                      style={{
                        background: sendingQuickReply || !quickReplyText.trim() ? "rgba(99, 102, 241, 0.4)" : "#6366f1",
                        color: "#fff",
                        border: "none",
                        borderRadius: "8px",
                        padding: "8px 16px",
                        fontSize: "13px",
                        fontWeight: 600,
                        cursor: sendingQuickReply || !quickReplyText.trim() ? "not-allowed" : "pointer",
                      }}
                    >
                      {sendingQuickReply ? "Sending..." : "Send"}
                    </button>
                  </form>
                </div>
              )}
            </div>

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

              <Link
                href={`/cases/${caseId}/bundles`}
                className={styles.secondaryBtn}
                style={{ fontSize: "13px", textDecoration: "none" }}
              >
                <span>📦</span> Manage Evidentiary Bundles
              </Link>
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

                    <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                      <Link
                        href={`/cases/${caseId}/bundles?hearingId=${h.id}`}
                        className={styles.secondaryBtn}
                        style={{ fontSize: "12px", textDecoration: "none" }}
                      >
                        📦 Prepare Court Bundle
                      </Link>
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

        {/* TAB 5: TASKS & DEADLINES (CASE OPERATIONS & WORKFLOW AUTOMATION) */}
        {activeTab === "tasks" && (
          <div>
            {/* Header & Quick Action */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px", flexWrap: "wrap", gap: "12px" }}>
              <div>
                <h3 style={{ fontSize: "18px", color: "#fff", fontWeight: 700, margin: 0 }}>
                  Case Operations, Deadlines & Workflow Automation
                </h3>
                <p style={{ fontSize: "13px", color: "#94a3b8", marginTop: "4px" }}>
                  Actionable case tasks, statutory limitation deadlines, and deterministic procedural workflow templates.
                </p>
              </div>

              <button
                onClick={() => setTemplateModalOpen(true)}
                className={styles.actionBtn}
                style={{ fontSize: "13px", padding: "8px 16px", display: "flex", alignItems: "center", gap: "6px" }}
              >
                <span>⚡</span> Apply Workflow Template
              </button>
            </div>

            {/* Case Health Telemetry Card */}
            {healthSummary && (
              <div
                style={{
                  background: "#101218",
                  border: "1px solid #222634",
                  borderRadius: "12px",
                  padding: "16px 20px",
                  marginBottom: "24px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "14px" }}>📊</span>
                    <span style={{ fontSize: "13px", fontWeight: 700, color: "#fff", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      Operational Case Health Summary
                    </span>
                  </div>
                  <span style={{ fontSize: "11px", color: "#64748b" }}>
                    Deterministic Telemetry · Zero AI Interpretation
                  </span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "12px" }}>
                  <div style={{ background: "#171a24", padding: "12px 14px", borderRadius: "8px", border: "1px solid #252a39" }}>
                    <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}>Next Hearing</div>
                    <div style={{ fontSize: "14px", fontWeight: 700, color: healthSummary.has_upcoming_hearing ? "#38bdf8" : "#64748b", marginTop: "4px" }}>
                      {healthSummary.next_hearing_date ? formatDate(healthSummary.next_hearing_date) : "None scheduled"}
                    </div>
                    {healthSummary.next_hearing_court && (
                      <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>{healthSummary.next_hearing_court}</div>
                    )}
                  </div>

                  <div style={{ background: "#171a24", padding: "12px 14px", borderRadius: "8px", border: "1px solid #252a39" }}>
                    <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}>Overdue Tasks</div>
                    <div style={{ fontSize: "18px", fontWeight: 700, color: healthSummary.overdue_tasks_count > 0 ? "#f87171" : "#34d399", marginTop: "4px" }}>
                      {healthSummary.overdue_tasks_count}
                    </div>
                    <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                      {healthSummary.overdue_tasks_count > 0 ? "Requires attention" : "All current"}
                    </div>
                  </div>

                  <div style={{ background: "#171a24", padding: "12px 14px", borderRadius: "8px", border: "1px solid #252a39" }}>
                    <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}>Upcoming Deadlines</div>
                    <div style={{ fontSize: "18px", fontWeight: 700, color: "#818cf8", marginTop: "4px" }}>
                      {healthSummary.upcoming_deadlines_count}
                    </div>
                    <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>Statutory & compliance</div>
                  </div>

                  <div style={{ background: "#171a24", padding: "12px 14px", borderRadius: "8px", border: "1px solid #252a39" }}>
                    <div style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase", fontWeight: 600 }}>Active Evidence Items</div>
                    <div style={{ fontSize: "18px", fontWeight: 700, color: "#fbbf24", marginTop: "4px" }}>
                      {healthSummary.unreviewed_evidence_count}
                    </div>
                    <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>Evidence Locker records</div>
                  </div>
                </div>
              </div>
            )}

            {/* Deadlines Section */}
            <div style={{ marginBottom: "32px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                <h4 style={{ fontSize: "16px", color: "#fff", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                  <span>⏳</span> Statutory & Compliance Deadlines ({deadlines.length})
                </h4>
              </div>

              {deadlines.length === 0 ? (
                <div
                  style={{
                    background: "#0e121a",
                    border: "1px dashed rgba(255, 255, 255, 0.12)",
                    borderRadius: "10px",
                    padding: "24px 16px",
                    textAlign: "center",
                  }}
                >
                  <p style={{ color: "#64748b", fontSize: "13px", margin: 0 }}>
                    No statutory deadlines currently scheduled. Deadlines can be imported from court records or scheduled by counsel.
                  </p>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {deadlines.map((dl) => {
                    const isPassed = new Date(dl.deadline_at).getTime() < new Date().getTime();
                    const isClosed = dl.status === "COMPLETED" || dl.status === "CANCELLED";
                    return (
                      <div
                        key={dl.id}
                        style={{
                          background: "#101218",
                          border: isClosed ? "1px solid #1c202a" : isPassed ? "1px solid rgba(239, 68, 68, 0.3)" : "1px solid #222634",
                          borderRadius: "10px",
                          padding: "14px 18px",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                          flexWrap: "wrap",
                          gap: "12px",
                        }}
                      >
                        <div style={{ flex: 1, minWidth: "240px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                            <span style={{ fontSize: "15px", fontWeight: 600, color: isClosed ? "#64748b" : "#fff", textDecoration: dl.status === "COMPLETED" ? "line-through" : "none" }}>
                              {dl.title}
                            </span>
                            <span
                              style={{
                                fontSize: "10px",
                                textTransform: "uppercase",
                                fontWeight: 700,
                                padding: "2px 6px",
                                borderRadius: "4px",
                                background: dl.status === "COMPLETED" ? "rgba(52, 211, 153, 0.15)" : dl.status === "OVERDUE" || (isPassed && !isClosed) ? "rgba(239, 68, 68, 0.15)" : "rgba(99, 102, 241, 0.15)",
                                color: dl.status === "COMPLETED" ? "#34d399" : dl.status === "OVERDUE" || (isPassed && !isClosed) ? "#f87171" : "#818cf8",
                              }}
                            >
                              {dl.status}
                            </span>
                          </div>

                          {dl.description && (
                            <p style={{ fontSize: "13px", color: "#94a3b8", margin: "4px 0 8px" }}>
                              {dl.description}
                            </p>
                          )}

                          <div style={{ fontSize: "12px", color: "#64748b", display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
                            <span style={{ color: !isClosed && isPassed ? "#f87171" : "#94a3b8", fontWeight: 500 }}>
                              📅 Due: {formatDate(dl.deadline_at)}
                            </span>
                            <span>•</span>
                            <span>Type: {dl.deadline_type.replace(/_/g, " ")}</span>
                            <span>•</span>
                            <span style={{ color: "#38bdf8" }}>
                              Provenance: {dl.retrieval_method || "MANUAL"}
                            </span>
                            {dl.linked_hearing_id && (
                              <>
                                <span>•</span>
                                <span style={{ color: "#a855f7" }}>Linked to Court Hearing</span>
                              </>
                            )}
                          </div>
                        </div>

                        {!isClosed && (
                          <div style={{ display: "flex", gap: "8px" }}>
                            <button
                              onClick={() => void handleCompleteDeadline(dl.id)}
                              className={styles.actionBtn}
                              style={{ fontSize: "12px", padding: "5px 12px" }}
                            >
                              ✓ Complete
                            </button>
                            <button
                              onClick={() => void handleCancelDeadline(dl.id)}
                              className={styles.secondaryBtn}
                              style={{ fontSize: "12px", padding: "5px 10px" }}
                            >
                              Cancel
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Case Tasks Section */}
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
                <h4 style={{ fontSize: "16px", color: "#fff", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px", margin: 0 }}>
                  <span>✓</span> Case Tasks ({tasks.length})
                </h4>

                {/* Filter Controls */}
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
                  <input
                    type="text"
                    placeholder="Search tasks..."
                    value={taskSearchQuery}
                    onChange={(e) => setTaskSearchQuery(e.target.value)}
                    style={{
                      background: "#141722",
                      border: "1px solid #283042",
                      borderRadius: "6px",
                      padding: "6px 10px",
                      color: "#fff",
                      fontSize: "12px",
                      width: "160px",
                    }}
                  />

                  <select
                    value={taskStatusFilter}
                    onChange={(e) => setTaskStatusFilter(e.target.value)}
                    style={{
                      background: "#141722",
                      border: "1px solid #283042",
                      borderRadius: "6px",
                      padding: "6px 10px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                  >
                    <option value="ALL">All Statuses</option>
                    <option value="PENDING">Pending</option>
                    <option value="IN_PROGRESS">In Progress</option>
                    <option value="BLOCKED">Blocked</option>
                    <option value="COMPLETED">Completed</option>
                    <option value="CANCELLED">Cancelled</option>
                  </select>

                  <select
                    value={taskPriorityFilter}
                    onChange={(e) => setTaskPriorityFilter(e.target.value)}
                    style={{
                      background: "#141722",
                      border: "1px solid #283042",
                      borderRadius: "6px",
                      padding: "6px 10px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                  >
                    <option value="ALL">All Priorities</option>
                    <option value="URGENT">Urgent</option>
                    <option value="HIGH">High</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="LOW">Low</option>
                  </select>
                </div>
              </div>

              {/* Quick Task Creation Drawer */}
              <form
                onSubmit={handleCreateTask}
                style={{
                  background: "#101218",
                  border: "1px solid #222634",
                  borderRadius: "10px",
                  padding: "16px 18px",
                  marginBottom: "20px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                }}
              >
                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                  <input
                    type="text"
                    placeholder="Task title (e.g., Review listing cause list, finalize exhibit B)..."
                    value={newTaskTitle}
                    onChange={(e) => setNewTaskTitle(e.target.value)}
                    style={{
                      flex: 2,
                      minWidth: "240px",
                      background: "#141722",
                      border: "1px solid #283042",
                      borderRadius: "6px",
                      padding: "8px 12px",
                      color: "#fff",
                      fontSize: "13px",
                    }}
                  />

                  <select
                    value={newTaskPriority}
                    onChange={(e) => setNewTaskPriority(e.target.value as any)}
                    style={{
                      background: "#141722",
                      border: "1px solid #283042",
                      borderRadius: "6px",
                      padding: "8px 12px",
                      color: "#fff",
                      fontSize: "13px",
                    }}
                  >
                    <option value="LOW">Low Priority</option>
                    <option value="MEDIUM">Medium Priority</option>
                    <option value="HIGH">High Priority</option>
                    <option value="URGENT">Urgent Priority</option>
                  </select>

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
                </div>

                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
                  <input
                    type="text"
                    placeholder="Optional description / operational instructions..."
                    value={newTaskDesc}
                    onChange={(e) => setNewTaskDesc(e.target.value)}
                    style={{
                      flex: 1,
                      minWidth: "240px",
                      background: "#141722",
                      border: "1px solid #283042",
                      borderRadius: "6px",
                      padding: "8px 12px",
                      color: "#fff",
                      fontSize: "13px",
                    }}
                  />

                  {hearings.length > 0 && (
                    <select
                      value={newTaskLinkedHearing}
                      onChange={(e) => setNewTaskLinkedHearing(e.target.value)}
                      style={{
                        background: "#141722",
                        border: "1px solid #283042",
                        borderRadius: "6px",
                        padding: "8px 12px",
                        color: "#fff",
                        fontSize: "13px",
                      }}
                    >
                      <option value="">No Hearing Link</option>
                      {hearings.map((h) => (
                        <option key={h.id} value={h.id}>
                          Hearing: {h.court_name} ({formatDate(h.hearing_at)})
                        </option>
                      ))}
                    </select>
                  )}

                  <button
                    type="submit"
                    disabled={addingTask || !newTaskTitle.trim()}
                    className={styles.actionBtn}
                    style={{ fontSize: "12px", padding: "8px 16px" }}
                  >
                    {addingTask ? "Adding..." : "+ Create Task"}
                  </button>
                </div>
              </form>

              {/* Tasks List */}
              {filteredTasksList.length === 0 ? (
                <div
                  style={{
                    background: "#0e121a",
                    border: "1px dashed rgba(255, 255, 255, 0.12)",
                    borderRadius: "10px",
                    padding: "36px 20px",
                    textAlign: "center",
                  }}
                >
                  <p style={{ color: "#64748b", fontSize: "14px", margin: 0 }}>
                    {tasks.length === 0
                      ? "All operational tasks are up to date. You can add tasks above or apply a deterministic workflow template."
                      : "No tasks match the active filters."}
                  </p>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {filteredTasksList.map((task) => {
                    const isCompleted = task.status === "COMPLETED";
                    const isCancelled = task.status === "CANCELLED";
                    const isClosed = isCompleted || isCancelled;
                    const isOverdue = !isClosed && task.due_date && new Date(task.due_date).getTime() < new Date().getTime();

                    const priorityColors: Record<string, { bg: string; color: string }> = {
                      URGENT: { bg: "rgba(239, 68, 68, 0.15)", color: "#f87171" },
                      HIGH: { bg: "rgba(245, 158, 11, 0.15)", color: "#fbbf24" },
                      MEDIUM: { bg: "rgba(99, 102, 241, 0.15)", color: "#818cf8" },
                      LOW: { bg: "rgba(100, 116, 139, 0.15)", color: "#94a3b8" },
                    };
                    const pStyle = priorityColors[task.priority] || priorityColors.MEDIUM;

                    return (
                      <div
                        key={task.id}
                        style={{
                          background: "#101218",
                          border: isClosed ? "1px solid #1c202a" : isOverdue ? "1px solid rgba(239, 68, 68, 0.35)" : "1px solid #222634",
                          borderRadius: "10px",
                          padding: "14px 18px",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                          flexWrap: "wrap",
                          gap: "12px",
                        }}
                      >
                        <div style={{ flex: 1, minWidth: "240px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px", flexWrap: "wrap" }}>
                            <span
                              style={{
                                fontSize: "10px",
                                textTransform: "uppercase",
                                fontWeight: 700,
                                padding: "2px 6px",
                                borderRadius: "4px",
                                background: pStyle.bg,
                                color: pStyle.color,
                              }}
                            >
                              {task.priority}
                            </span>

                            <span
                              style={{
                                fontSize: "10px",
                                textTransform: "uppercase",
                                fontWeight: 700,
                                padding: "2px 6px",
                                borderRadius: "4px",
                                background: isCompleted ? "rgba(52, 211, 153, 0.15)" : task.status === "IN_PROGRESS" ? "rgba(56, 189, 248, 0.15)" : task.status === "BLOCKED" ? "rgba(249, 115, 22, 0.15)" : "rgba(100, 116, 139, 0.15)",
                                color: isCompleted ? "#34d399" : task.status === "IN_PROGRESS" ? "#38bdf8" : task.status === "BLOCKED" ? "#f97316" : "#94a3b8",
                              }}
                            >
                              {task.status.replace(/_/g, " ")}
                            </span>

                            <span
                              style={{
                                fontSize: "15px",
                                fontWeight: 600,
                                color: isClosed ? "#64748b" : "#fff",
                                textDecoration: isCompleted ? "line-through" : "none",
                              }}
                            >
                              {task.title}
                            </span>
                          </div>

                          {task.description && (
                            <p style={{ fontSize: "13px", color: "#94a3b8", margin: "4px 0 8px", lineHeight: "1.5" }}>
                              {task.description}
                            </p>
                          )}

                          <div style={{ fontSize: "12px", color: "#64748b", display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
                            {task.due_date && (
                              <span style={{ color: isOverdue ? "#f87171" : "#94a3b8", fontWeight: isOverdue ? 600 : 400 }}>
                                📅 Due: {formatDate(task.due_date)} {isOverdue && "(OVERDUE)"}
                              </span>
                            )}
                            {task.completed_at && (
                              <span style={{ color: "#34d399" }}>
                                ✓ Completed on {formatDate(task.completed_at)}
                              </span>
                            )}
                            {task.linked_hearing_id && (
                              <span style={{ color: "#a855f7" }}>🏛 Court Hearing Linked</span>
                            )}
                            {task.linked_evidence_id && (
                              <span style={{ color: "#38bdf8" }}>📄 Evidence Linked</span>
                            )}
                          </div>
                        </div>

                        {/* Interactive Lifecycle Actions */}
                        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
                          {(task.status === "PENDING" || task.status === "BLOCKED") && (
                            <button
                              onClick={() => void handleStartTask(task.id)}
                              className={styles.secondaryBtn}
                              style={{ fontSize: "11px", padding: "5px 10px" }}
                              title="Start working on this task"
                            >
                              ▶ Start
                            </button>
                          )}

                          {(task.status === "PENDING" || task.status === "IN_PROGRESS" || task.status === "BLOCKED") && (
                            <>
                              <button
                                onClick={() => void handleCompleteTaskAction(task.id)}
                                className={styles.actionBtn}
                                style={{ fontSize: "11px", padding: "5px 12px" }}
                              >
                                ✓ Complete
                              </button>
                              <button
                                onClick={() => void handleCancelTaskAction(task.id)}
                                className={styles.secondaryBtn}
                                style={{ fontSize: "11px", padding: "5px 8px" }}
                              >
                                ⊘
                              </button>
                            </>
                          )}

                          {isClosed && (
                            <button
                              onClick={() => void handleReopenTaskAction(task.id)}
                              className={styles.secondaryBtn}
                              style={{ fontSize: "11px", padding: "5px 10px" }}
                              title="Reopen task back to In Progress"
                            >
                              ↺ Reopen
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Workflow Template Application Modal */}
            {templateModalOpen && (
              <div
                style={{
                  position: "fixed",
                  inset: 0,
                  background: "rgba(0, 0, 0, 0.75)",
                  backdropFilter: "blur(4px)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  zIndex: 9999,
                  padding: "20px",
                }}
              >
                <div
                  style={{
                    background: "#101218",
                    border: "1px solid #283042",
                    borderRadius: "14px",
                    maxWidth: "600px",
                    width: "100%",
                    padding: "24px",
                    boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                    <div>
                      <h3 style={{ fontSize: "18px", color: "#fff", fontWeight: 700, margin: 0 }}>
                        ⚡ Procedural Case Workflow Templates
                      </h3>
                      <p style={{ fontSize: "12px", color: "#94a3b8", marginTop: "4px" }}>
                        Select a deterministic procedural template to batch generate verified operational tasks. Zero AI estimation.
                      </p>
                    </div>
                    <button
                      onClick={() => setTemplateModalOpen(false)}
                      style={{ background: "transparent", border: "none", color: "#94a3b8", fontSize: "20px", cursor: "pointer" }}
                    >
                      ✕
                    </button>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginBottom: "20px" }}>
                    {[
                      {
                        id: "HEARING_PREPARATION",
                        title: "🏛 Hearing Preparation Template",
                        desc: "Generates 6 tasks: Cause list verification, prior order audit, sequential exhibit check, evidentiary bundle PDF compilation with Bates stamps, BSA Section 63 certificate draft, and appearance logistics confirmation.",
                      },
                      {
                        id: "POST_HEARING_FOLLOWUP",
                        title: "📋 Post-Hearing Follow-up Template",
                        desc: "Generates 4 tasks: Bench proceedings synopsis, certified court order deposit to Evidence Locker, next listing date registration, and compliance filings scheduling.",
                      },
                      {
                        id: "EVIDENCE_PREPARATION",
                        title: "📁 Evidence Preparation Template",
                        desc: "Generates 3 tasks: Native digital records retrieval from client, Evidence Locker upload with SHA-256 integrity hashing, and formal exhibit letter designations.",
                      },
                      {
                        id: "NEW_CONSULTATION",
                        title: "🤝 New Matter Consultation Template",
                        desc: "Generates 3 tasks: Intake facts review, foundational agreement and ID document request, and consultation session with matter brief preparation.",
                      },
                    ].map((tpl) => (
                      <div
                        key={tpl.id}
                        onClick={() => setSelectedTemplate(tpl.id)}
                        style={{
                          background: selectedTemplate === tpl.id ? "rgba(99, 102, 241, 0.12)" : "#141722",
                          border: selectedTemplate === tpl.id ? "1px solid #4f5bf7" : "1px solid #252a39",
                          borderRadius: "8px",
                          padding: "12px 14px",
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <input
                            type="radio"
                            checked={selectedTemplate === tpl.id}
                            onChange={() => setSelectedTemplate(tpl.id)}
                            style={{ accentColor: "#4f5bf7" }}
                          />
                          <span style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>
                            {tpl.title}
                          </span>
                        </div>
                        <p style={{ fontSize: "12px", color: "#94a3b8", margin: "6px 0 0 24px", lineHeight: "1.4" }}>
                          {tpl.desc}
                        </p>
                      </div>
                    ))}
                  </div>

                  {/* Optional Target Hearing */}
                  {hearings.length > 0 && selectedTemplate === "HEARING_PREPARATION" && (
                    <div style={{ marginBottom: "20px" }}>
                      <label style={{ fontSize: "12px", color: "#94a3b8", display: "block", marginBottom: "6px" }}>
                        Link to Scheduled Hearing:
                      </label>
                      <select
                        value={templateHearingId}
                        onChange={(e) => setTemplateHearingId(e.target.value)}
                        style={{
                          width: "100%",
                          background: "#141722",
                          border: "1px solid #283042",
                          borderRadius: "6px",
                          padding: "8px 12px",
                          color: "#fff",
                          fontSize: "13px",
                        }}
                      >
                        <option value="">Select court listing...</option>
                        {hearings.map((h) => (
                          <option key={h.id} value={h.id}>
                            {h.court_name} · {formatDate(h.hearing_at)}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {participants.length > 0 && (
                    <div style={{ marginBottom: "20px" }}>
                      <label style={{ fontSize: "12px", color: "#94a3b8", display: "block", marginBottom: "6px" }}>
                        Assign Generated Tasks To:
                      </label>
                      <select
                        value={templateAssigneeId}
                        onChange={(e) => setTemplateAssigneeId(e.target.value)}
                        style={{
                          width: "100%",
                          background: "#141722",
                          border: "1px solid #283042",
                          borderRadius: "6px",
                          padding: "8px 12px",
                          color: "#fff",
                          fontSize: "13px",
                        }}
                      >
                        <option value="">Unassigned (Case Participants)</option>
                        {participants.map((p) => (
                          <option key={p.id} value={p.user_id}>
                            {p.user?.full_name || p.user?.email || p.user_id} ({p.participant_role})
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                    <button
                      onClick={() => setTemplateModalOpen(false)}
                      className={styles.secondaryBtn}
                      style={{ fontSize: "13px", padding: "8px 16px" }}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => void handleApplyWorkflowTemplate()}
                      disabled={applyingTemplate}
                      className={styles.actionBtn}
                      style={{ fontSize: "13px", padding: "8px 20px" }}
                    >
                      {applyingTemplate ? "Applying..." : "Apply Template"}
                    </button>
                  </div>
                </div>
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
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", margin: "10px 0 4px" }}>
                    <h4 style={{ fontSize: "18px", color: "#fff", fontWeight: 600, margin: 0 }}>
                      Adv. {assignedLawyer.full_name}
                    </h4>
                    {lawyerCallStatus?.is_in_meeting ? (
                      <span style={{ fontSize: "11px", color: "#f59e0b", background: "rgba(245, 158, 11, 0.15)", padding: "2px 8px", borderRadius: "12px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                        <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#f59e0b" }}></span>
                        In Another Meeting
                      </span>
                    ) : lawyerCallStatus?.is_online ? (
                      <span style={{ fontSize: "11px", color: "#10b981", background: "rgba(16, 185, 129, 0.15)", padding: "2px 8px", borderRadius: "12px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                        <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#10b981" }}></span>
                        Online & Available
                      </span>
                    ) : (
                      <span style={{ fontSize: "11px", color: "#94a3b8", background: "rgba(148, 163, 184, 0.15)", padding: "2px 8px", borderRadius: "12px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                        <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#94a3b8" }}></span>
                        Offline
                      </span>
                    )}
                  </div>
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

                  <div style={{ marginTop: "16px" }}>
                    {lawyerCallStatus?.is_in_meeting ? (
                      <div style={{ background: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.2)", borderRadius: "8px", padding: "10px 12px", fontSize: "13px", color: "#fbbf24" }}>
                        Advocate is currently in another consultation. You can send a request to join when they finish.
                        <button
                          onClick={handleStartInstantVideoCall}
                          disabled={startingCall}
                          style={{
                            marginTop: "8px",
                            width: "100%",
                            padding: "8px 12px",
                            borderRadius: "6px",
                            background: "rgba(245, 158, 11, 0.2)",
                            border: "1px solid rgba(245, 158, 11, 0.4)",
                            color: "#fbbf24",
                            cursor: "pointer",
                            fontSize: "12px",
                            fontWeight: 600,
                          }}
                        >
                          {startingCall ? "Connecting..." : "Send Request to Join"}
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={handleStartInstantVideoCall}
                        disabled={startingCall}
                        className={styles.actionBtn}
                        style={{
                          width: "100%",
                          justifyContent: "center",
                          background: "linear-gradient(135deg, #059669 0%, #047857 100%)",
                          color: "#fff",
                          fontWeight: 600,
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          padding: "10px 16px",
                          borderRadius: "8px",
                          cursor: "pointer",
                        }}
                      >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
                        {startingCall ? "Starting Video Room..." : "📹 Start Video Call Now →"}
                      </button>
                    )}
                    {callError && (
                      <div style={{ color: "#ef4444", fontSize: "12px", marginTop: "6px" }}>
                        {callError}
                      </div>
                    )}
                  </div>
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

        {/* TAB: MESSAGES */}
        {activeTab === "messages" && (
          <div>
            <MatterInbox
              caseId={caseId}
              messages={caseMessages}
              documents={documents}
              tasks={tasks}
              userRole={user?.role || "CLIENT"}
              onRefresh={fetchCaseWorkspace}
            />
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
                            <span style={{ color: "#fff", fontWeight: 600 }}>₹{fee.toLocaleString("en-IN")}</span>
                          </div>
                          <div style={{ display: "flex", justifyContent: "space-between", color: "#94a3b8", fontSize: "12px" }}>
                            <span>Taxes & Platform Charges:</span>
                            <span>Itemized at Checkout</span>
                          </div>
                        </div>
                      </div>

                      {isPending ? (
                        <button
                          onClick={() => setCheckoutConsultation(con)}
                          className={styles.actionBtn}
                          style={{ width: "100%", justifyContent: "center" }}
                        >
                          Pay securely →
                        </button>
                      ) : (
                        <button
                          onClick={() => router.push(`/consultations/${con.id}/room?bypass_time=true`)}
                          className={styles.actionBtn}
                          style={{
                            width: "100%",
                            justifyContent: "center",
                            background: "linear-gradient(135deg, #059669 0%, #047857 100%)",
                            color: "#fff",
                            fontWeight: 600,
                            display: "flex",
                            alignItems: "center",
                            gap: "8px",
                            padding: "10px 14px",
                            borderRadius: "8px",
                            cursor: "pointer",
                          }}
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
                          Join Video Call Now →
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

        {/* LCC Legal Assistant Modal (Section 12) */}
        {copilotModalOpen && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(15, 30, 54, 0.45)",
              backdropFilter: "blur(4px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
              padding: "20px",
            }}
            onClick={() => setCopilotModalOpen(false)}
          >
            <div
              style={{
                width: "100%",
                maxWidth: "960px",
                maxHeight: "90vh",
                background: "#FFFFFF",
                borderRadius: "var(--radius-xl)",
                overflow: "hidden",
                boxShadow: "var(--shadow-xl)",
                position: "relative",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ position: "absolute", top: "14px", right: "16px", zIndex: 10 }}>
                <button
                  onClick={() => setCopilotModalOpen(false)}
                  style={{
                    background: "#F1F5F9",
                    border: "none",
                    borderRadius: "50%",
                    width: "32px",
                    height: "32px",
                    fontSize: "16px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--navy-primary)",
                  }}
                  title="Close Legal Assistant"
                >
                  ✕
                </button>
              </div>
              <CopilotChat
                caseId={caseId}
                conversations={[]}
                activeConvId={null}
                messages={[]}
                onSelectConversation={async () => {}}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
