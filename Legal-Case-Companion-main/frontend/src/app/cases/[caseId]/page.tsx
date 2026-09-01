"use client";

import { useEffect, useState, use, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import styles from "./caseDetail.module.css";
import Link from "next/link";
import {
  CaseItem,
  CaseParticipantItem,
  TimelineEventItem,
  DocumentItem,
  DocumentChunkItem,
  CaseWorkspaceResponse,
  CaseFactItem,
  LegalIssueItem,
  EvidenceGapItem,
  CaseRiskIndicatorItem,
  CaseTaskItem,
  CaseDeadlineItem,
  CaseHearingItem,
  CaseNoteItem,
  AIConversationItem,
  AIMessageItem,
  RetrievedEvidenceItem,
  CaseIntelligenceResponse,
  CaseMessageItem,
  MatterRequestItem,
  MatterParticipantDetailItem,
  MatterBriefItem,
} from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { IntelligenceCenter } from "@/components/Intelligence/IntelligenceCenter";
import { CopilotChat } from "@/components/Intelligence/CopilotChat";
import { ActionCenter } from "@/components/ActionCenter/ActionCenter";
import { MatterBriefCard } from "@/components/Collaboration/MatterBriefCard";
import { MatterRequestsBoard } from "@/components/Collaboration/MatterRequestsBoard";
import { MatterInbox } from "@/components/Collaboration/MatterInbox";
import { MatterParticipantsPanel } from "@/components/Collaboration/MatterParticipantsPanel";

type WorkspaceTab =
  | "overview"
  | "collaboration"
  | "actions"
  | "intelligence"
  | "documents"
  | "workflow"
  | "copilot"
  | "search"
  | "notes";

export default function CaseDetail({ params }: { params: Promise<{ caseId: string }> }) {
  const unwrappedParams = use(params);
  const { caseId } = unwrappedParams;
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const initialTab = (searchParams?.get("tab") as WorkspaceTab) || "overview";

  const [activeTab, setActiveTab] = useState<WorkspaceTab>(initialTab);

  useEffect(() => {
    const tabParam = searchParams?.get("tab") as WorkspaceTab | null;
    if (tabParam && ["overview", "collaboration", "actions", "documents", "workflow", "copilot", "intelligence", "search", "notes"].includes(tabParam)) {
      setActiveTab(tabParam);
    }
  }, [searchParams]);
  const [caseData, setCaseData] = useState<CaseItem | null>(null);
  const [workspaceData, setWorkspaceData] = useState<CaseWorkspaceResponse | null>(null);
  const [participants, setParticipants] = useState<CaseParticipantItem[]>([]);
  const [timeline, setTimeline] = useState<TimelineEventItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Document management state
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docCategory, setDocCategory] = useState("CONTRACT");
  const [uploading, setUploading] = useState(false);
  const [selectedDocChunks, setSelectedDocChunks] = useState<{ docName: string; chunks: DocumentChunkItem[] } | null>(null);

  // Workflow state
  const [tasks, setTasks] = useState<CaseTaskItem[]>([]);
  const [deadlines, setDeadlines] = useState<CaseDeadlineItem[]>([]);
  const [hearings, setHearings] = useState<CaseHearingItem[]>([]);
  const [openTaskModal, setOpenTaskModal] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskPriority, setNewTaskPriority] = useState<"LOW" | "MEDIUM" | "HIGH" | "URGENT">("MEDIUM");
  const [newTaskDueDate, setNewTaskDueDate] = useState("");

  // Copilot state
  const [conversations, setConversations] = useState<AIConversationItem[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AIMessageItem[]>([]);

  // Intelligence state
  const [fullIntel, setFullIntel] = useState<CaseIntelligenceResponse | null>(null);
  const [facts, setFacts] = useState<CaseFactItem[]>([]);
  const [issues, setIssues] = useState<LegalIssueItem[]>([]);
  const [gaps, setGaps] = useState<EvidenceGapItem[]>([]);
  const [risks, setRisks] = useState<CaseRiskIndicatorItem[]>([]);
  const [refreshingIntelligence, setRefreshingIntelligence] = useState(false);

  // Evidence Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState("HYBRID");
  const [searchResults, setSearchResults] = useState<RetrievedEvidenceItem[]>([]);
  const [searching, setSearching] = useState(false);

  // Notes state
  const [notes, setNotes] = useState<CaseNoteItem[]>([]);
  const [newNoteContent, setNewNoteContent] = useState("");
  const [newNoteVisibility, setNewNoteVisibility] = useState<"CLIENT_PRIVATE" | "LAWYER_PRIVATE" | "SHARED">("SHARED");

  // Collaboration 4.0 state
  const [caseMessages, setCaseMessages] = useState<CaseMessageItem[]>([]);
  const [matterRequests, setMatterRequests] = useState<MatterRequestItem[]>([]);
  const [detailedParticipants, setDetailedParticipants] = useState<MatterParticipantDetailItem[]>([]);
  const [matterBrief, setMatterBrief] = useState<MatterBriefItem | null>(null);
  const [loadingCollab, setLoadingCollab] = useState(false);

  // Participant state
  const [showAddParticipant, setShowAddParticipant] = useState(false);
  const [newParticipantEmail, setNewParticipantEmail] = useState("");
  const [newParticipantRole, setNewParticipantRole] = useState("COLLABORATING_LAWYER");

  // Export Report state
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<"markdown" | "json">("markdown");
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const fetchCollaborationData = useCallback(async () => {
    try {
      setLoadingCollab(true);
      const [briefRes, msgsRes, reqsRes, partsRes] = await Promise.all([
        apiClient.get(`/api/v1/cases/${caseId}/collaboration/brief`).catch(() => null),
        apiClient.get(`/api/v1/cases/${caseId}/collaboration/messages`).catch(() => []),
        apiClient.get(`/api/v1/cases/${caseId}/collaboration/requests`).catch(() => []),
        apiClient.get(`/api/v1/cases/${caseId}/collaboration/participants`).catch(() => []),
      ]);

      if (briefRes) setMatterBrief(briefRes);
      setCaseMessages(Array.isArray(msgsRes) ? msgsRes : []);
      setMatterRequests(Array.isArray(reqsRes) ? reqsRes : []);
      setDetailedParticipants(Array.isArray(partsRes) ? partsRes : []);
    } catch (err) {
      console.error("Failed to load collaboration data:", err);
    } finally {
      setLoadingCollab(false);
    }
  }, [caseId]);

  // Fetch core case details & workspace summary
  const fetchCaseDetails = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [caseRes, workspaceRes, partsRes, timelineRes, docsRes] = await Promise.all([
        apiClient.get(`/api/v1/cases/${caseId}`),
        apiClient.get(`/api/v1/cases/${caseId}/workspace`).catch(() => null),
        apiClient.get(`/api/v1/cases/${caseId}/participants`).catch(() => ({ items: [] })),
        apiClient.get(`/api/v1/cases/${caseId}/timeline`).catch(() => ({ items: [] })),
        apiClient.get(`/api/v1/cases/${caseId}/documents`).catch(() => ({ items: [] })),
      ]);

      setCaseData(caseRes);
      if (workspaceRes) setWorkspaceData(workspaceRes);
      setParticipants(partsRes?.items || (Array.isArray(partsRes) ? partsRes : []));
      setTimeline(timelineRes?.items || (Array.isArray(timelineRes) ? timelineRes : []));
      setDocuments(docsRes?.items || (Array.isArray(docsRes) ? docsRes : []));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load case workspace.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  // Tab data fetchers
  const fetchWorkflowData = useCallback(async () => {
    try {
      const wfRes = await apiClient.get(`/api/v1/cases/${caseId}/workflow`).catch(() => null);
      if (wfRes) {
        setTasks(wfRes.tasks || []);
        setDeadlines(wfRes.deadlines || []);
        setHearings(wfRes.hearings || []);
      } else {
        const [tasksRes, deadlinesRes, hearingsRes] = await Promise.all([
          apiClient.get(`/api/v1/cases/${caseId}/tasks`).catch(() => ({ items: [] })),
          apiClient.get(`/api/v1/cases/${caseId}/deadlines`).catch(() => []),
          apiClient.get(`/api/v1/cases/${caseId}/hearings`).catch(() => []),
        ]);
        setTasks(tasksRes?.items || (Array.isArray(tasksRes) ? tasksRes : []));
        setDeadlines(Array.isArray(deadlinesRes) ? deadlinesRes : deadlinesRes?.items || []);
        setHearings(Array.isArray(hearingsRes) ? hearingsRes : hearingsRes?.items || []);
      }
    } catch (e) {
      console.error("Workflow fetch error:", e);
    }
  }, [caseId]);

  const fetchCopilotData = useCallback(async () => {
    try {
      const convsRes = await apiClient.get(`/api/v1/cases/${caseId}/ai/conversations`).catch(() => []);
      const convList: AIConversationItem[] = Array.isArray(convsRes) ? convsRes : convsRes?.items || [];
      setConversations(convList);

      if (convList.length > 0) {
        const targetId = activeConvId || convList[0].id;
        if (!activeConvId) setActiveConvId(targetId);
        const msgRes = await apiClient.get(`/api/v1/cases/${caseId}/ai/conversations/${targetId}/messages`).catch(() => []);
        setMessages(Array.isArray(msgRes) ? msgRes : msgRes?.items || []);
      }
    } catch (e) {
      console.error("Copilot fetch error:", e);
    }
  }, [caseId, activeConvId]);

  const fetchIntelligenceData = useCallback(async () => {
    try {
      const intelRes = await apiClient.get(`/api/v1/cases/${caseId}/intelligence`).catch(() => null);
      if (intelRes) {
        setFullIntel(intelRes);
        setFacts(intelRes.facts || []);
        setIssues(intelRes.issues || []);
        setGaps(intelRes.evidence_gaps || []);
        setRisks(intelRes.risks || []);
      } else {
        const [factsRes, issuesRes, gapsRes, risksRes] = await Promise.all([
          apiClient.get(`/api/v1/cases/${caseId}/intelligence/facts`).catch(() => []),
          apiClient.get(`/api/v1/cases/${caseId}/intelligence/issues`).catch(() => []),
          apiClient.get(`/api/v1/cases/${caseId}/intelligence/evidence-gaps`).catch(() => []),
          apiClient.get(`/api/v1/cases/${caseId}/intelligence/risks`).catch(() => []),
        ]);
        setFacts(Array.isArray(factsRes) ? factsRes : factsRes?.items || []);
        setIssues(Array.isArray(issuesRes) ? issuesRes : issuesRes?.items || []);
        setGaps(Array.isArray(gapsRes) ? gapsRes : gapsRes?.items || []);
        setRisks(Array.isArray(risksRes) ? risksRes : risksRes?.items || []);
      }
    } catch (e) {
      console.error("Intelligence fetch error:", e);
    }
  }, [caseId]);

  const fetchNotesData = useCallback(async () => {
    try {
      const notesRes = await apiClient.get(`/api/v1/cases/${caseId}/notes`).catch(() => ({ items: [] }));
      setNotes(notesRes?.items || (Array.isArray(notesRes) ? notesRes : []));
    } catch (e) {
      console.error("Notes fetch error:", e);
    }
  }, [caseId]);

  useEffect(() => {
    void fetchCaseDetails();
    void fetchCollaborationData();
  }, [fetchCaseDetails, fetchCollaborationData]);

  useEffect(() => {
    if (activeTab === "collaboration" || activeTab === "overview") void fetchCollaborationData();
    if (activeTab === "workflow") void fetchWorkflowData();
    if (activeTab === "copilot") void fetchCopilotData();
    if (activeTab === "intelligence") void fetchIntelligenceData();
    if (activeTab === "notes") void fetchNotesData();
  }, [activeTab, fetchCollaborationData, fetchWorkflowData, fetchCopilotData, fetchIntelligenceData, fetchNotesData]);

  // Document Upload
  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    try {
      const initRes = await apiClient.post(`/api/v1/cases/${caseId}/documents/upload-init`, {
        filename: selectedFile.name,
        category: docCategory,
        mime_type: selectedFile.type || "application/pdf",
        file_size: selectedFile.size,
      });

      const { upload_url, document: doc } = initRes;
      const uploadRes = await fetch(upload_url, {
        method: "PUT",
        body: selectedFile,
        headers: { "Content-Type": selectedFile.type || "application/pdf" },
      });

      if (!uploadRes.ok) throw new Error("Upload to storage provider failed.");

      await apiClient.post(`/api/v1/documents/${doc.id}/complete`, {}).catch(() => {});
      await apiClient.post(`/api/v1/documents/${doc.id}/scan?is_safe=true`, {}).catch(() => {});

      setSelectedFile(null);
      setUploadModalOpen(false);
      await fetchCaseDetails();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Document upload failed.";
      alert(`Upload error: ${msg}`);
    } finally {
      setUploading(false);
    }
  };

  // Secure Document Download
  const handleDownload = async (docId: string) => {
    try {
      const res = await apiClient.get(`/api/v1/cases/${caseId}/documents/${docId}/download`)
        .catch(() => apiClient.get(`/api/v1/documents/${docId}/download`));
      if (res?.download_url) {
        window.open(res.download_url, "_blank");
      }
    } catch {
      alert("Failed to acquire secure authorized download URL.");
    }
  };

  // Document Chunks
  const handleInspectDoc = async (doc: DocumentItem) => {
    try {
      const res = await apiClient.get(`/api/v1/cases/${caseId}/documents/${doc.id}/chunks`).catch(() => ({ items: [] }));
      setSelectedDocChunks({
        docName: doc.filename,
        chunks: res.items || (Array.isArray(res) ? res : []),
      });
    } catch {
      alert("Unable to fetch document chunks.");
    }
  };

  // Switch / Create conversation
  const handleSelectConversation = async (convId: string) => {
    setActiveConvId(convId);
    try {
      const msgRes = await apiClient.get(`/api/v1/cases/${caseId}/ai/conversations/${convId}/messages`);
      setMessages(Array.isArray(msgRes) ? msgRes : msgRes?.items || []);
    } catch {
      setMessages([]);
    }
  };

  // Task creation
  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/tasks`, {
        title: newTaskTitle.trim(),
        priority: newTaskPriority,
        due_date: newTaskDueDate ? new Date(newTaskDueDate).toISOString() : null,
      });
      setOpenTaskModal(false);
      setNewTaskTitle("");
      setNewTaskDueDate("");
      void fetchWorkflowData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create task.";
      alert(`Task creation error: ${msg}`);
    }
  };

  // Toggle Task Completion
  const handleToggleTask = async (taskId: string, currentStatus: string) => {
    try {
      const newStatus = currentStatus === "COMPLETED" ? "IN_PROGRESS" : "COMPLETED";
      await apiClient.patch(`/api/v1/cases/${caseId}/tasks/${taskId}`, { status: newStatus });
      setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, status: newStatus as any } : t)));
    } catch {
      alert("Failed to update task state.");
    }
  };

  // Refresh Intelligence
  const handleRefreshIntelligence = async () => {
    setRefreshingIntelligence(true);
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/intelligence/refresh`, {});
      await fetchIntelligenceData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to refresh intelligence.";
      alert(`Intelligence refresh error: ${msg}`);
    } finally {
      setRefreshingIntelligence(false);
    }
  };

  // Evidence Hybrid Search
  const handleEvidenceSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim() || searching) return;
    setSearching(true);
    try {
      const res = await apiClient.post(`/api/v1/cases/${caseId}/search`, {
        query: searchQuery.trim(),
        search_mode: searchMode,
        top_k: 10,
      });
      setSearchResults(res.results || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Evidence search failed.";
      alert(`Search error: ${msg}`);
    } finally {
      setSearching(false);
    }
  };

  // Case Note Creation
  const handleCreateNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNoteContent.trim()) return;
    try {
      const res = await apiClient.post(`/api/v1/cases/${caseId}/notes`, {
        title: newNoteContent.slice(0, 32),
        content: newNoteContent.trim(),
        visibility: newNoteVisibility,
      });
      setNotes((prev) => [res, ...prev]);
      setNewNoteContent("");
    } catch {
      alert("Failed to record case note.");
    }
  };

  // Add Participant
  const handleAddParticipant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newParticipantEmail.trim()) return;
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/participants`, {
        email: newParticipantEmail.trim(),
        participant_role: newParticipantRole,
      });
      setShowAddParticipant(false);
      setNewParticipantEmail("");
      await fetchCaseDetails();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to add participant.";
      alert(`Participant addition error: ${msg}`);
    }
  };

  const handleExportReport = async () => {
    if (exporting) return;
    setExporting(true);
    setExportStatus(null);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
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
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.detail || `Export failed with status ${res.status}`);
      }

      const blob = await res.blob();
      const contentDisposition = res.headers.get("content-disposition");
      let filename = `case_${caseId.slice(0, 8)}_summary_report.${exportFormat === "markdown" ? "md" : "json"}`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?([^";]+)"?/);
        if (match && match[1]) {
          filename = match[1];
        }
      }

      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);

      setExportStatus({
        type: "success",
        message: `Case summary report (${exportFormat.toUpperCase()}) exported successfully.`,
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

  if (loading) {
    return (
      <div className={styles.workspaceContainer}>
        <div className="container" style={{ textAlign: "center", paddingTop: "100px" }}>
          <div style={{ color: "#8d98ff", fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", fontSize: "11px" }}>
            Synchronizing Matter Record
          </div>
          <p style={{ color: "#7a8494", marginTop: "12px" }}>Opening authenticated case workspace & document registry...</p>
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
              {error || "This matter may not exist, or your account does not have active participant authorization to view this case record."}
            </div>

            <div style={{ display: "flex", gap: "12px", marginTop: "8px" }}>
              <button
                onClick={() => {
                  void fetchCaseDetails();
                  void fetchCollaborationData();
                }}
                className={styles.actionBtn}
              >
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

  const safeDocsCount = documents.filter((d) => d.security_status === "SAFE" || d.security_status === "CLEAN").length;
  const nextHearing = hearings.find((h) => h.status === "SCHEDULED");
  const overdueDeadlines = deadlines.filter((d) => d.status === "OVERDUE").length;

  return (
    <div className={styles.workspaceContainer}>
      <div className="container">
        {/* Breadcrumb Navigation */}
        <div className={styles.breadcrumbNav}>
          <Link href="/dashboard" className={styles.breadcrumbLink}>
            Matters
          </Link>
          <span className={styles.breadcrumbSeparator}>/</span>
          <span className={styles.breadcrumbCurrent}>{caseData.title}</span>
        </div>

        {/* Case Workspace Header */}
        <div className={styles.caseHeader}>
          <div className={styles.headerGlow} aria-hidden="true" />
          <div className={styles.headerMain}>
            <div className={styles.headerTopRow}>
              <span
                className={`${styles.statusBadge} ${
                  caseData.status === "OPEN" || caseData.status === "IN_PROGRESS"
                    ? styles.statusOpen
                    : caseData.status === "IN_REVIEW"
                    ? styles.statusReview
                    : styles.statusPending
                }`}
              >
                ● {caseData.status}
              </span>
              <span className={styles.caseRefBadge}>
                REF: #{caseData.id.slice(0, 8).toUpperCase()}
              </span>
              {workspaceData?.lawyer && (
                <span style={{ fontSize: "12px", color: "#8d98ff", display: "flex", alignItems: "center", gap: "4px" }}>
                  <span>⚖</span> Counsel: <b>{workspaceData.lawyer.full_name}</b>
                </span>
              )}
            </div>

            <h1 className={styles.caseTitle}>{caseData.title}</h1>
            <p className={styles.caseDesc}>{caseData.description || "No formal matter summary recorded."}</p>
          </div>

          <div className={styles.headerActions}>
            <button
              onClick={() => setExportModalOpen(true)}
              className={styles.secondaryBtn}
              title="Export Case Summary Report"
            >
              <span>📄</span> Export Report
            </button>
            <button onClick={() => setActiveTab("actions")} className={styles.actionBtn}>
              <span>⚡</span> Action Center
            </button>
            <button onClick={() => setUploadModalOpen(true)} className={styles.secondaryBtn}>
              <span>+</span> Evidence
            </button>
            <button onClick={() => setActiveTab("copilot")} className={styles.secondaryBtn}>
              <span>✦</span> Copilot
            </button>
          </div>
        </div>

        {/* Deterministic Next Best Action Signal */}
        {(() => {
          // Compute highest priority deterministic action
          let nextActionTitle = "";
          let nextActionSubtitle = "";
          let nextActionTab: WorkspaceTab = "actions";
          let actionColor = "#10b981";

          const nextHearing = hearings.find((h) => h.status === "SCHEDULED");
          const urgentTask = tasks.find((t) => (t.priority === "URGENT" || t.priority === "HIGH") && t.status !== "COMPLETED");
          const criticalGap = gaps.find((g) => g.severity === "CRITICAL" || g.severity === "HIGH");

          if (nextHearing) {
            // Compare timestamps stably
            const hearingEpoch = new Date(nextHearing.hearing_at).getTime();
            const nowEpoch = new Date().setHours(0, 0, 0, 0);
            const diff = Math.ceil((hearingEpoch - nowEpoch) / (1000 * 60 * 60 * 24));
            if (diff >= 0 && diff <= 7) {
              nextActionTitle = `Court Hearing at ${nextHearing.court_name} in ${diff === 0 ? "today" : diff === 1 ? "tomorrow" : `${diff} days`}`;
              nextActionSubtitle = `Purpose: ${nextHearing.purpose} • Review cause-list and ensure preparation obligations are satisfied.`;
              nextActionTab = "actions";
              actionColor = "#ef4444";
            }
          } else if (urgentTask) {
            nextActionTitle = `High Priority Task: ${urgentTask.title}`;
            nextActionSubtitle = urgentTask.due_date ? `Due: ${new Date(urgentTask.due_date).toLocaleDateString("en-IN")}` : "Unfinished procedural task obligation.";
            nextActionTab = "actions";
            actionColor = "#f59e0b";
          } else if (criticalGap) {
            nextActionTitle = `Evidence Gap: ${criticalGap.gap_type}`;
            nextActionSubtitle = `${criticalGap.description} — Upload supporting contract or pleading to ground legal position.`;
            nextActionTab = "documents";
            actionColor = "#60a5fa";
          }

          if (!nextActionTitle) return null;

          return (
            <div
              style={{
                marginBottom: "20px",
                padding: "14px 18px",
                borderRadius: "var(--radius-md)",
                background: "var(--surface-card)",
                border: `1px solid ${actionColor}40`,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: "16px",
                flexWrap: "wrap",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <span
                  style={{
                    padding: "4px 8px",
                    borderRadius: "4px",
                    background: `${actionColor}20`,
                    color: actionColor,
                    fontSize: "11px",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    whiteSpace: "nowrap",
                  }}
                >
                  ⚡ Next Action
                </span>
                <div>
                  <h4 style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>
                    {nextActionTitle}
                  </h4>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                    {nextActionSubtitle}
                  </p>
                </div>
              </div>

              <button
                onClick={() => setActiveTab(nextActionTab)}
                className="btn btn-secondary"
                style={{ fontSize: "12px", padding: "6px 14px", whiteSpace: "nowrap" }}
              >
                Resolve Action →
              </button>
            </div>
          );
        })()}

        {/* Workspace Tab Bar */}
        <div className={styles.tabNavigation}>
          <button
            className={`${styles.tabBtn} ${activeTab === "overview" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("overview")}
          >
            <span>📁</span> Overview
          </button>

          <button
            className={`${styles.tabBtn} ${activeTab === "collaboration" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("collaboration")}
            style={{
              borderColor: activeTab === "collaboration" ? "#3b82f6" : undefined,
              color: activeTab === "collaboration" ? "#3b82f6" : undefined,
            }}
          >
            <span>🤝</span> Matter Collaboration{" "}
            {matterRequests.filter((r) => r.status === "PENDING" || r.status === "SUBMITTED").length > 0 && (
              <span className={styles.tabBadge} style={{ background: "rgba(59, 130, 246, 0.2)", color: "#60a5fa" }}>
                {matterRequests.filter((r) => r.status === "PENDING" || r.status === "SUBMITTED").length}
              </span>
            )}
          </button>

          <button
            className={`${styles.tabBtn} ${activeTab === "actions" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("actions")}
            style={{
              borderColor: activeTab === "actions" ? "#10b981" : undefined,
              color: activeTab === "actions" ? "#10b981" : undefined,
            }}
          >
            <span>⚡</span> Action Center{" "}
            {tasks.filter((t) => t.status !== "COMPLETED").length > 0 && (
              <span className={styles.tabBadge} style={{ background: "rgba(16, 185, 129, 0.2)", color: "#10b981" }}>
                {tasks.filter((t) => t.status !== "COMPLETED").length}
              </span>
            )}
          </button>

          <button
            className={`${styles.tabBtn} ${activeTab === "intelligence" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("intelligence")}
          >
            <span>🧠</span> Case Intelligence
          </button>

          <button
            className={`${styles.tabBtn} ${activeTab === "documents" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("documents")}
          >
            <span>📄</span> Documents Vault <span className={styles.tabBadge}>{documents.length}</span>
          </button>

          <button
            className={`${styles.tabBtn} ${activeTab === "workflow" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("workflow")}
          >
            <span>◷</span> Workflow & Hearings{" "}
            {hearings.length > 0 && <span className={styles.tabBadge}>{hearings.length}</span>}
          </button>

          <button
            className={`${styles.tabBtn} ${activeTab === "copilot" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("copilot")}
          >
            <span>✦</span> Case Copilot AI
          </button>

          <button
            className={`${styles.tabBtn} ${activeTab === "search" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("search")}
          >
            <span>🔍</span> Evidence Search
          </button>

          <button
            className={`${styles.tabBtn} ${activeTab === "notes" ? styles.tabBtnActive : ""}`}
            onClick={() => setActiveTab("notes")}
          >
            <span>📝</span> Notes
          </button>
        </div>

        {/* TAB 1: OVERVIEW & PARTIES */}
        {activeTab === "overview" && (
          <div className={styles.tabContent}>
            {/* Overview Quick Stats */}
            <div className={styles.overviewStatsGrid}>
              <div className={styles.statCard}>
                <div className={styles.statCardLabel}>Active Evidence</div>
                <div className={styles.statCardValue}>{safeDocsCount}</div>
                <div style={{ fontSize: "11px", color: "#6b7280", marginTop: "2px" }}>
                  {documents.length} uploaded files
                </div>
              </div>

              <div className={styles.statCard}>
                <div className={styles.statCardLabel}>Next Court Hearing</div>
                <div className={styles.statCardValue} style={{ fontSize: "16px", color: "#60a5fa" }}>
                  {nextHearing
                    ? new Date(nextHearing.hearing_at).toLocaleDateString("en-IN", {
                        day: "numeric",
                        month: "short",
                        year: "numeric",
                      })
                    : "None Listed"}
                </div>
                <div style={{ fontSize: "11px", color: "#6b7280", marginTop: "2px" }}>
                  {nextHearing?.court_name || "Schedule in Workflow tab"}
                </div>
              </div>

              <div className={styles.statCard}>
                <div className={styles.statCardLabel}>Pending Tasks</div>
                <div className={styles.statCardValue} style={{ color: "#f59e0b" }}>
                  {tasks.filter((t) => t.status !== "COMPLETED" && t.status !== "CANCELLED").length}
                </div>
                <div style={{ fontSize: "11px", color: "#6b7280", marginTop: "2px" }}>
                  {overdueDeadlines > 0 ? `${overdueDeadlines} overdue deadline(s)` : "Operational status clean"}
                </div>
              </div>

              <div className={styles.statCard}>
                <div className={styles.statCardLabel}>Participants</div>
                <div className={styles.statCardValue}>{participants.length}</div>
                <div style={{ fontSize: "11px", color: "#6b7280", marginTop: "2px" }}>
                  Clients & verified counsel
                </div>
              </div>
            </div>

            {/* Split Grid: Participants & Timeline */}
            <div className={styles.gridTwoCol}>
              {/* Participants Panel */}
              <div className={styles.sectionCard}>
                <div className={styles.sectionHeader}>
                  <h3 className={styles.sectionTitle}>
                    <span>👥</span> Matter Participants ({participants.length})
                  </h3>
                  <button
                    onClick={() => setShowAddParticipant(true)}
                    className={styles.secondaryBtn}
                    style={{ fontSize: "12px", padding: "6px 12px" }}
                  >
                    + Add Participant
                  </button>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {participants.map((p) => (
                    <div
                      key={p.id}
                      style={{
                        padding: "12px 14px",
                        borderRadius: "8px",
                        background: "#141721",
                        border: "1px solid #222736",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: "13px", fontWeight: 600, color: "#f7f8fa" }}>
                          {p.user?.full_name || p.user?.email || "Participant"}
                        </div>
                        <div style={{ fontSize: "11px", color: "#748092", marginTop: "2px" }}>
                          {p.user?.email || p.user_id}
                        </div>
                      </div>
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: "4px",
                          background:
                            p.participant_role === "PRIMARY_LAWYER" || p.participant_role === "LAWYER"
                              ? "rgba(109, 124, 255, 0.18)"
                              : "rgba(59, 130, 246, 0.15)",
                          color:
                            p.participant_role === "PRIMARY_LAWYER" || p.participant_role === "LAWYER"
                              ? "#8d98ff"
                              : "#60a5fa",
                        }}
                      >
                        {p.participant_role || p.role}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Activity Timeline Panel */}
              <div className={styles.sectionCard}>
                <div className={styles.sectionHeader}>
                  <h3 className={styles.sectionTitle}>
                    <span>◷</span> Matter Activity & Audit Log
                  </h3>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  {timeline.length === 0 ? (
                    <div style={{ color: "#737e90", fontSize: "13px", textAlign: "center", padding: "20px 0" }}>
                      No activity logged for this matter yet.
                    </div>
                  ) : (
                    timeline.slice(0, 7).map((evt) => (
                      <div
                        key={evt.id}
                        style={{
                          borderLeft: "2px solid #4f5bf7",
                          paddingLeft: "14px",
                          fontSize: "13px",
                        }}
                      >
                        <div style={{ color: "#e4e8ef", fontWeight: 500 }}>{evt.description}</div>
                        <div style={{ color: "#677385", fontSize: "11px", marginTop: "2px" }}>
                          {new Date(evt.created_at).toLocaleString("en-IN", {
                            day: "numeric",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}{" "}
                          • {evt.event_type}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB: MATTER COLLABORATION 4.0 */}
        {activeTab === "collaboration" && (
          <div className={styles.tabContent} style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            {/* Matter Brief Header Card */}
            <MatterBriefCard brief={matterBrief} loading={loadingCollab} />

            {/* 3-Column Structured Requests Board */}
            <MatterRequestsBoard
              caseId={caseId}
              requests={matterRequests}
              documents={documents}
              userRole={user?.role || "CLIENT"}
              onRefresh={fetchCollaborationData}
            />

            {/* 2-Column Grid: Matter Communication Inbox + Participants Directory */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))", gap: "20px" }}>
              <MatterInbox
                caseId={caseId}
                messages={caseMessages}
                documents={documents}
                tasks={tasks}
                userRole={user?.role || "CLIENT"}
                onRefresh={fetchCollaborationData}
              />

              <MatterParticipantsPanel
                participants={detailedParticipants}
                loading={loadingCollab}
              />
            </div>
          </div>
        )}

        {/* TAB 2: ACTION & DECISION CENTER */}
        {activeTab === "actions" && (
          <div className={styles.tabContent}>
            <ActionCenter
              caseId={caseId}
              tasks={tasks}
              deadlines={deadlines}
              hearings={hearings}
              notes={notes}
              gaps={gaps}
              risks={risks}
              issues={issues}
              facts={facts}
              onRefreshWorkflow={fetchWorkflowData}
              onRefreshNotes={fetchNotesData}
              onNavigateToTab={(tab) => setActiveTab(tab as WorkspaceTab)}
            />
          </div>
        )}

        {/* TAB 2: DOCUMENTS VAULT */}
        {activeTab === "documents" && (
          <div className={styles.tabContent}>
            <div className={styles.sectionCard}>
              <div className={styles.sectionHeader}>
                <div>
                  <h3 className={styles.sectionTitle}>
                    <span>📄</span> Private Evidence & Documents Vault
                  </h3>
                  <p style={{ fontSize: "12px", color: "#748092", marginTop: "4px" }}>
                    Documents are encrypted at rest, malware-scanned, and vector-indexed for case-scoped legal research.
                  </p>
                </div>
                <button onClick={() => setUploadModalOpen(true)} className={styles.actionBtn}>
                  <span>+</span> Upload Document
                </button>
              </div>

              {documents.length === 0 ? (
                <div style={{ padding: "48px 0", textAlign: "center", color: "#748092" }}>
                  <div style={{ fontSize: "36px", marginBottom: "12px" }}>📁</div>
                  <h4 style={{ color: "#fff", fontSize: "15px", marginBottom: "6px" }}>No Documents in Vault</h4>
                  <p style={{ fontSize: "13px", maxWidth: "420px", margin: "0 auto 18px" }}>
                    Upload agreements, notices, or court pleadings to enable full vector search and Evidence Copilot analysis.
                  </p>
                  <button onClick={() => setUploadModalOpen(true)} className={styles.actionBtn}>
                    Upload First Document
                  </button>
                </div>
              ) : (
                <div className={styles.tableContainer}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Filename</th>
                        <th>Category</th>
                        <th>Security Inspection</th>
                        <th>Vector Index</th>
                        <th>Size</th>
                        <th>Uploaded</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((doc) => (
                        <tr key={doc.id}>
                          <td style={{ fontWeight: 600, color: "#fff" }}>{doc.filename}</td>
                          <td>
                            <span className={styles.badgeCategory}>
                              {doc.document_type || doc.category || "GENERAL"}
                            </span>
                          </td>
                          <td>
                            <StatusBadge status={doc.security_status} />
                          </td>
                          <td>
                            <StatusBadge status={doc.processing_status || "READY"} />
                          </td>
                          <td>{(doc.file_size / 1024).toFixed(1)} KB</td>
                          <td>{new Date(doc.created_at).toLocaleDateString("en-IN")}</td>
                          <td>
                            <div style={{ display: "flex", gap: "8px" }}>
                              <button
                                onClick={() => handleDownload(doc.id)}
                                className={styles.secondaryBtn}
                                style={{ fontSize: "11px", padding: "4px 8px" }}
                              >
                                ⬇ Download
                              </button>
                              <button
                                onClick={() => handleInspectDoc(doc)}
                                className={styles.secondaryBtn}
                                style={{ fontSize: "11px", padding: "4px 8px" }}
                              >
                                🔍 Chunks
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Document Chunks Inspector Modal */}
            {selectedDocChunks && (
              <div className={styles.modalOverlay} onClick={() => setSelectedDocChunks(null)}>
                <div
                  className={styles.modalWindow}
                  style={{ maxWidth: "720px", maxHeight: "80vh", overflowY: "auto" }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className={styles.modalHeader}>
                    <h3 className={styles.modalTitle}>
                      Vector Chunks: {selectedDocChunks.docName}
                    </h3>
                    <button
                      className={styles.modalCloseBtn}
                      onClick={() => setSelectedDocChunks(null)}
                    >
                      ✕
                    </button>
                  </div>

                  {selectedDocChunks.chunks.length === 0 ? (
                    <div style={{ color: "#748092", fontSize: "13px" }}>No chunk embeddings generated yet.</div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {selectedDocChunks.chunks.map((c) => (
                        <div
                          key={c.id}
                          style={{
                            padding: "12px",
                            borderRadius: "8px",
                            background: "#0c0e14",
                            border: "1px solid #202636",
                            fontSize: "12px",
                          }}
                        >
                          <div style={{ color: "#8d98ff", fontWeight: 600, marginBottom: "4px" }}>
                            Chunk #{c.chunk_index} {c.page_number ? `• Page ${c.page_number}` : ""}
                          </div>
                          <div style={{ color: "#d1d7e2", whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
                            {c.content}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: WORKFLOW & HEARINGS */}
        {activeTab === "workflow" && (
          <div className={styles.tabContent}>
            <div className={styles.gridTwoCol}>
              {/* Tasks List */}
              <div className={styles.sectionCard}>
                <div className={styles.sectionHeader}>
                  <h3 className={styles.sectionTitle}>
                    <span>✓</span> Case Tasks ({tasks.length})
                  </h3>
                  <button
                    onClick={() => setOpenTaskModal(true)}
                    className={styles.actionBtn}
                    style={{ fontSize: "12px", padding: "6px 12px" }}
                  >
                    + New Task
                  </button>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {tasks.length === 0 ? (
                    <div style={{ color: "#748092", fontSize: "13px", textAlign: "center", padding: "20px 0" }}>
                      No tasks assigned for this matter.
                    </div>
                  ) : (
                    tasks.map((t) => (
                      <div
                        key={t.id}
                        style={{
                          padding: "12px 14px",
                          borderRadius: "8px",
                          background: "#141721",
                          border: "1px solid #222736",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <div>
                          <div
                            style={{
                              fontSize: "13px",
                              fontWeight: 600,
                              textDecoration: t.status === "COMPLETED" ? "line-through" : "none",
                              color: t.status === "COMPLETED" ? "#6b7280" : "#f7f8fa",
                            }}
                          >
                            {t.title}
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
                            <StatusBadge status={t.priority} />
                            {t.due_date && (
                              <span style={{ fontSize: "11px", color: "#748092" }}>
                                Due: {new Date(t.due_date).toLocaleDateString("en-IN")}
                              </span>
                            )}
                          </div>
                        </div>
                        <button
                          onClick={() => handleToggleTask(t.id, t.status)}
                          className={styles.secondaryBtn}
                          style={{ fontSize: "11px", padding: "4px 8px" }}
                        >
                          {t.status === "COMPLETED" ? "↩ Reopen" : "✓ Complete"}
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Deadlines & Hearings Stack */}
              <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                {/* Court Hearings Panel */}
                <div className={styles.sectionCard}>
                  <div className={styles.sectionHeader}>
                    <h3 className={styles.sectionTitle}>
                      <span>⚖</span> Court Hearings ({hearings.length})
                    </h3>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    {hearings.length === 0 ? (
                      <div style={{ color: "#748092", fontSize: "13px" }}>No court hearings scheduled.</div>
                    ) : (
                      hearings.map((h) => (
                        <div
                          key={h.id}
                          style={{
                            padding: "12px 14px",
                            borderRadius: "8px",
                            background: "#141721",
                            border: "1px solid #222736",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ fontSize: "13px", fontWeight: 600, color: "#fff" }}>
                              {h.court_name} {h.bench_or_coram ? `• Bench: ${h.bench_or_coram}` : ""}
                            </span>
                            <StatusBadge status={h.status} />
                          </div>
                          <div style={{ fontSize: "12px", color: "#8d98ff", marginTop: "4px" }}>
                            Date: {new Date(h.hearing_at).toLocaleString("en-IN", {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </div>
                          <div style={{ fontSize: "12px", color: "#8b96a8", marginTop: "2px" }}>
                            Purpose: {h.purpose}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Statutory Deadlines Panel */}
                <div className={styles.sectionCard}>
                  <div className={styles.sectionHeader}>
                    <h3 className={styles.sectionTitle}>
                      <span>◷</span> Deadlines & Limitation Tracking ({deadlines.length})
                    </h3>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {deadlines.length === 0 ? (
                      <div style={{ color: "#748092", fontSize: "13px" }}>No active limitation deadlines tracked.</div>
                    ) : (
                      deadlines.map((d) => (
                        <div
                          key={d.id}
                          style={{
                            padding: "12px 14px",
                            borderRadius: "8px",
                            background:
                              d.deadline_type === "STATUTORY_LIMITATION"
                                ? "rgba(239, 68, 68, 0.08)"
                                : "#141721",
                            border:
                              d.deadline_type === "STATUTORY_LIMITATION"
                                ? "1px solid rgba(239, 68, 68, 0.3)"
                                : "1px solid #222736",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ fontSize: "13px", fontWeight: 600, color: "#fff" }}>
                              {d.title}
                            </span>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              {d.deadline_type === "STATUTORY_LIMITATION" ? (
                                <StatusBadge status="STATUTORY_LIMITATION" label="Limitation Deadline" pulse />
                              ) : (
                                <StatusBadge status={d.status} />
                              )}
                              <span style={{ fontSize: "12px", color: "#cfd5e0", fontWeight: 600 }}>
                                {new Date(d.deadline_at).toLocaleDateString("en-IN")}
                              </span>
                            </div>
                          </div>

                          {d.deadline_type === "STATUTORY_LIMITATION" && (
                            <div style={{ fontSize: "11px", color: "#f87171", marginTop: "3px" }}>
                              ⚠ Statutory Limitation Period (Limitation Act / Commercial Courts Act)
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: CASE COPILOT 2.0 */}
        {activeTab === "copilot" && (
          <div className={styles.tabContent}>
            <CopilotChat
              caseId={caseId}
              conversations={conversations}
              activeConvId={activeConvId}
              messages={messages}
              onSelectConversation={handleSelectConversation}
              issues={issues}
              gaps={gaps}
            />
          </div>
        )}

        {/* TAB 5: LEGAL CASE INTELLIGENCE 1.0 */}
        {activeTab === "intelligence" && (
          <div className={styles.tabContent}>
            <IntelligenceCenter
              caseId={caseId}
              caseTitle={caseData.title}
              intel={fullIntel}
              participants={participants}
              onRefresh={handleRefreshIntelligence}
              refreshing={refreshingIntelligence}
              onAskCopilot={() => {
                setActiveTab("copilot");
                // Pre-populate prompt in copilot if needed
              }}
            />
          </div>
        )}

        {/* TAB 6: EVIDENCE SEARCH */}
        {activeTab === "search" && (
          <div className={styles.tabContent}>
            <div className={styles.sectionCard}>
              <h3 className={styles.sectionTitle} style={{ marginBottom: "16px" }}>
                <span>🔍</span> Case-Scoped Hybrid Evidence Search
              </h3>

              <form onSubmit={handleEvidenceSearch} style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search agreements, notices, clauses, or citations across this case..."
                  className={styles.chatInput}
                  style={{ flex: 1 }}
                />
                <select
                  value={searchMode}
                  onChange={(e) => setSearchMode(e.target.value)}
                  className={styles.formSelect}
                  style={{ width: "160px" }}
                >
                  <option value="HYBRID">Hybrid (Dense + Sparse)</option>
                  <option value="SEMANTIC">Semantic Embedding</option>
                  <option value="LEXICAL">Lexical Exact</option>
                </select>
                <button type="submit" disabled={searching} className={styles.actionBtn}>
                  {searching ? "Searching..." : "Search"}
                </button>
              </form>

              {searchResults.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {searchResults.map((res, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: "14px 16px",
                        borderRadius: "8px",
                        background: "#141721",
                        border: "1px solid #222736",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                        <span style={{ fontSize: "13px", fontWeight: 600, color: "#60a5fa" }}>
                          📄 {res.source_filename} (p. {res.page_start})
                        </span>
                        <span style={{ fontSize: "11px", color: "#10b981", fontWeight: 600 }}>
                          Score: {res.score.toFixed(3)}
                        </span>
                      </div>
                      <div style={{ fontSize: "13px", color: "#d1d7e2", lineHeight: 1.55 }}>
                        {res.content}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 7: CASE NOTES */}
        {activeTab === "notes" && (
          <div className={styles.tabContent}>
            <div className={styles.sectionCard}>
              <h3 className={styles.sectionTitle} style={{ marginBottom: "16px" }}>
                <span>📝</span> Case Notes ({notes.length})
              </h3>

              <form onSubmit={handleCreateNote} style={{ marginBottom: "24px" }}>
                <textarea
                  value={newNoteContent}
                  onChange={(e) => setNewNoteContent(e.target.value)}
                  placeholder="Record confidential analysis, case strategy, or shared instructions..."
                  rows={3}
                  className={styles.formTextarea}
                  style={{ width: "100%", marginBottom: "10px" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <span style={{ fontSize: "12px", color: "#748092" }}>Visibility:</span>
                    <select
                      value={newNoteVisibility}
                      onChange={(e) => setNewNoteVisibility(e.target.value as any)}
                      className={styles.formSelect}
                    >
                      <option value="SHARED">Shared (All Case Participants)</option>
                      <option value="CLIENT_PRIVATE">Client Confidential</option>
                      <option value="LAWYER_PRIVATE">Lawyer Confidential</option>
                    </select>
                  </div>
                  <button type="submit" className={styles.actionBtn}>
                    + Add Note
                  </button>
                </div>
              </form>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {notes.map((note) => (
                  <div
                    key={note.id}
                    style={{
                      padding: "14px 16px",
                      borderRadius: "8px",
                      background: "#141721",
                      border: "1px solid #222736",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          padding: "2px 6px",
                          borderRadius: "4px",
                          background: note.visibility === "SHARED" ? "rgba(59, 130, 246, 0.15)" : "rgba(245, 158, 11, 0.15)",
                          color: note.visibility === "SHARED" ? "#60a5fa" : "#f59e0b",
                        }}
                      >
                        {note.visibility}
                      </span>
                      <span style={{ fontSize: "11px", color: "#677385" }}>
                        {new Date(note.created_at).toLocaleDateString("en-IN")}
                      </span>
                    </div>
                    <div style={{ fontSize: "13px", color: "#e4e8ef", whiteSpace: "pre-wrap" }}>
                      {note.content}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Upload Document Modal */}
        {uploadModalOpen && (
          <div className={styles.modalOverlay} onClick={() => setUploadModalOpen(false)}>
            <div className={styles.modalWindow} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 className={styles.modalTitle}>Upload Matter Evidence</h3>
                <button className={styles.modalCloseBtn} onClick={() => setUploadModalOpen(false)}>
                  ✕
                </button>
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Document Classification</label>
                <select
                  value={docCategory}
                  onChange={(e) => setDocCategory(e.target.value)}
                  className={styles.formSelect}
                >
                  <option value="CONTRACT">Agreement / Contract</option>
                  <option value="PLEADING">Petition / Written Statement / Pleading</option>
                  <option value="NOTICE">Legal Notice / Reply</option>
                  <option value="EVIDENCE">Evidence / Annexure / Affidavit</option>
                  <option value="ORDER">Court Order / Judgment</option>
                  <option value="OTHER">Other Matter Documentation</option>
                </select>
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Select File (PDF, DOCX, TXT - Max 15MB)</label>
                <input
                  type="file"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className={styles.formInput}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "16px" }}>
                <button
                  type="button"
                  onClick={() => setUploadModalOpen(false)}
                  className={styles.secondaryBtn}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleUpload}
                  disabled={uploading || !selectedFile}
                  className={styles.actionBtn}
                >
                  {uploading ? "Ingesting & Scanning..." : "Upload Evidence →"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Add Task Modal */}
        {openTaskModal && (
          <div className={styles.modalOverlay} onClick={() => setOpenTaskModal(false)}>
            <div className={styles.modalWindow} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 className={styles.modalTitle}>Assign Case Task</h3>
                <button className={styles.modalCloseBtn} onClick={() => setOpenTaskModal(false)}>
                  ✕
                </button>
              </div>

              <form onSubmit={handleCreateTask}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Task Title</label>
                  <input
                    type="text"
                    value={newTaskTitle}
                    onChange={(e) => setNewTaskTitle(e.target.value)}
                    placeholder="e.g. Draft rejoinder affidavit"
                    required
                    className={styles.formInput}
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Priority</label>
                  <select
                    value={newTaskPriority}
                    onChange={(e) => setNewTaskPriority(e.target.value as any)}
                    className={styles.formSelect}
                  >
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                    <option value="URGENT">Urgent</option>
                  </select>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Due Date (Optional)</label>
                  <input
                    type="date"
                    value={newTaskDueDate}
                    onChange={(e) => setNewTaskDueDate(e.target.value)}
                    className={styles.formInput}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "16px" }}>
                  <button
                    type="button"
                    onClick={() => setOpenTaskModal(false)}
                    className={styles.secondaryBtn}
                  >
                    Cancel
                  </button>
                  <button type="submit" className={styles.actionBtn}>
                    Create Task
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Add Participant Modal */}
        {showAddParticipant && (
          <div className={styles.modalOverlay} onClick={() => setShowAddParticipant(false)}>
            <div className={styles.modalWindow} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 className={styles.modalTitle}>Add Matter Participant</h3>
                <button className={styles.modalCloseBtn} onClick={() => setShowAddParticipant(false)}>
                  ✕
                </button>
              </div>

              <form onSubmit={handleAddParticipant}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Participant Email</label>
                  <input
                    type="email"
                    value={newParticipantEmail}
                    onChange={(e) => setNewParticipantEmail(e.target.value)}
                    placeholder="counsel@chambers.in"
                    required
                    className={styles.formInput}
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Role Assignment</label>
                  <select
                    value={newParticipantRole}
                    onChange={(e) => setNewParticipantRole(e.target.value)}
                    className={styles.formSelect}
                  >
                    <option value="PRIMARY_LAWYER">Primary Lawyer (Lead Counsel)</option>
                    <option value="COLLABORATING_LAWYER">Collaborating Lawyer</option>
                    <option value="PARALEGAL">Paralegal / Researcher</option>
                    <option value="OBSERVER">Observer (Read-Only)</option>
                  </select>
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "16px" }}>
                  <button
                    type="button"
                    onClick={() => setShowAddParticipant(false)}
                    className={styles.secondaryBtn}
                  >
                    Cancel
                  </button>
                  <button type="submit" className={styles.actionBtn}>
                    Add Participant
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Export Case Summary Report Modal */}
        {exportModalOpen && (
          <div className={styles.modalOverlay} onClick={() => !exporting && setExportModalOpen(false)}>
            <div className={styles.modalWindow} onClick={(e) => e.stopPropagation()} style={{ maxWidth: "540px" }}>
              <div className={styles.modalHeader}>
                <div>
                  <h3 className={styles.modalTitle} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span>📄</span> Export Case Summary Report
                  </h3>
                  <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px" }}>
                    Generate an authorized, structured point-in-time summary report of this matter.
                  </p>
                </div>
                <button
                  className={styles.modalCloseBtn}
                  onClick={() => !exporting && setExportModalOpen(false)}
                  disabled={exporting}
                >
                  ✕
                </button>
              </div>

              <div style={{ padding: "20px 24px" }}>
                {exportStatus && (
                  <div
                    style={{
                      padding: "12px 16px",
                      borderRadius: "8px",
                      fontSize: "13px",
                      marginBottom: "16px",
                      background:
                        exportStatus.type === "success"
                          ? "rgba(16, 185, 129, 0.12)"
                          : "rgba(239, 68, 68, 0.12)",
                      border: `1px solid ${
                        exportStatus.type === "success"
                          ? "rgba(16, 185, 129, 0.3)"
                          : "rgba(239, 68, 68, 0.3)"
                      }`,
                      color: exportStatus.type === "success" ? "#10b981" : "#ef4444",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <span>{exportStatus.type === "success" ? "✓" : "⚠"}</span>
                    {exportStatus.message}
                  </div>
                )}

                <div className={styles.formGroup}>
                  <label className={styles.formLabel} style={{ marginBottom: "8px" }}>
                    Select Export Format
                  </label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                    <div
                      onClick={() => setExportFormat("markdown")}
                      style={{
                        padding: "14px",
                        borderRadius: "10px",
                        border: `1px solid ${exportFormat === "markdown" ? "var(--primary-color, #4f5bf7)" : "#222634"}`,
                        background: exportFormat === "markdown" ? "rgba(79, 91, 247, 0.08)" : "#13161f",
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
                        <span style={{ fontWeight: 600, fontSize: "14px", color: exportFormat === "markdown" ? "#8d98ff" : "#fff" }}>
                          Markdown (.md)
                        </span>
                        <input
                          type="radio"
                          name="exportFormat"
                          checked={exportFormat === "markdown"}
                          onChange={() => setExportFormat("markdown")}
                          style={{ accentColor: "#4f5bf7" }}
                        />
                      </div>
                      <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0, lineHeight: 1.4 }}>
                        Clean formatted document with court diary, tasks, documents & strategy notes.
                      </p>
                    </div>

                    <div
                      onClick={() => setExportFormat("json")}
                      style={{
                        padding: "14px",
                        borderRadius: "10px",
                        border: `1px solid ${exportFormat === "json" ? "var(--primary-color, #4f5bf7)" : "#222634"}`,
                        background: exportFormat === "json" ? "rgba(79, 91, 247, 0.08)" : "#13161f",
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
                        <span style={{ fontWeight: 600, fontSize: "14px", color: exportFormat === "json" ? "#8d98ff" : "#fff" }}>
                          Structured JSON
                        </span>
                        <input
                          type="radio"
                          name="exportFormat"
                          checked={exportFormat === "json"}
                          onChange={() => setExportFormat("json")}
                          style={{ accentColor: "#4f5bf7" }}
                        />
                      </div>
                      <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0, lineHeight: 1.4 }}>
                        Machine-readable snapshot for archival, audit review, and programmatic ingestion.
                      </p>
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "8px",
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.06)",
                    fontSize: "12px",
                    color: "var(--text-secondary)",
                    lineHeight: 1.5,
                    marginBottom: "16px",
                  }}
                >
                  🔒 <b>Security & Privacy Guarantee:</b> The exported report filters private counsel work products based on your authorized role. Storage keys, secret credentials, and private message bodies are excluded.
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                  <button
                    type="button"
                    onClick={() => setExportModalOpen(false)}
                    className={styles.secondaryBtn}
                    disabled={exporting}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleExportReport}
                    className={styles.actionBtn}
                    disabled={exporting}
                    style={{ minWidth: "140px" }}
                  >
                    {exporting ? "Generating..." : "Download Export"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
