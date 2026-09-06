"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { apiClient } from "@/api/client";
import Link from "next/link";
import {
  CaseItem,
  ConsultationItem,
  MatterBriefItem,
  MatterRequestItem,
  CaseHearingItem,
  CaseDeadlineItem,
  CaseMessageItem,
} from "@/types";
import styles from "./dashboard.module.css";
import { PaymentCheckoutModal } from "@/components/Payment/PaymentCheckoutModal";
import { ConsultationActionModal } from "@/components/Consultation/ConsultationActionModal";
import { NextStep } from "@/components/NextStep";
import LegalTerm from "@/components/LegalTerm";
import { WhatChangedBanner } from "@/components/WhatChangedBanner";

interface DashboardAttentionItem {
  id: string;
  priority: number; // 1: Urgent Hearing, 2: Deadline, 3: Document Request, 4: Message, 5: Payment, 6: Consultation
  type: "HEARING" | "DEADLINE" | "DOCUMENT_REQUEST" | "MESSAGE" | "PAYMENT" | "CONSULTATION";
  headerText: string;
  badgeLabel: string;
  badgeColor: string;
  matterTitle?: string;
  caseId?: string;
  detailsContent: React.ReactNode;
  actionLabel: string;
  actionHref?: string;
  onActionClick?: () => void;
  isUrgent?: boolean;
}

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

function formatDateTime(dateString?: string | null): string {
  if (!dateString) return "Not available";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "Not available";
    const datePart = d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "long",
    });
    const timePart = d.toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
    return `${datePart} · ${timePart}`;
  } catch {
    return "Not available";
  }
}

export default function Dashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [cases, setCases] = useState<CaseItem[]>([]);
  const [briefsByCaseId, setBriefsByCaseId] = useState<Record<string, MatterBriefItem>>({});
  const [hearings, setHearings] = useState<CaseHearingItem[]>([]);
  const [deadlines, setDeadlines] = useState<CaseDeadlineItem[]>([]);
  const [documentRequests, setDocumentRequests] = useState<MatterRequestItem[]>([]);
  const [recentMessages, setRecentMessages] = useState<CaseMessageItem[]>([]);
  const [consultations, setConsultations] = useState<ConsultationItem[]>([]);

  const [fetching, setFetching] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Modals
  const [checkoutConsultation, setCheckoutConsultation] = useState<ConsultationItem | null>(null);
  const [actionConsultationModal, setActionConsultationModal] = useState<{
    type: "RESCHEDULE" | "CANCEL";
    consultation: ConsultationItem;
  } | null>(null);

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Create Case Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchDashboardData = useCallback(async () => {
    try {
      setFetching(true);
      setFetchError(null);

      // 1. Parallel primary fetch: Cases, Consultations, and Aggregated Calendar Events (Eliminates 16+ sequential sub-requests)
      const [casesRes, consultRes, calEventsRes] = await Promise.all([
        apiClient.get("/api/v1/cases").catch(() => ({ items: [] })),
        apiClient.get("/api/v1/consultations").catch(() => ({ items: [] })),
        apiClient.get("/api/v1/calendar/events?timeframe=upcoming").catch(() => ({ events: [] })),
      ]);

      const caseItems: CaseItem[] = Array.isArray(casesRes)
        ? casesRes
        : casesRes?.items || [];
      const consultItems: ConsultationItem[] = Array.isArray(consultRes)
        ? consultRes
        : consultRes?.items || [];

      setCases(caseItems);
      setConsultations(consultItems);

      // Extract hearings and deadlines directly from aggregated calendar events
      const rawEvents = (calEventsRes as { events?: Array<Record<string, unknown>> })?.events || [];
      const allHearings: CaseHearingItem[] = [];
      const allDeadlines: CaseDeadlineItem[] = [];

      for (const ev of rawEvents) {
        if (ev.type === "hearing") {
          allHearings.push({
            id: String(ev.id),
            case_id: String(ev.case_id || ""),
            hearing_at: String(ev.scheduled_at),
            court_name: String(ev.forum || "Court"),
            bench_or_coram: (ev.lawyer_details as { bench?: string })?.bench || null,
            status: "SCHEDULED",
            purpose: String(ev.title || ""),
            notes: String(ev.action_tip || ""),
          } as CaseHearingItem);
        } else if (ev.type === "limitation" || ev.type === "task") {
          allDeadlines.push({
            id: String(ev.id),
            case_id: String(ev.case_id || ""),
            title: String(ev.title),
            deadline_at: String(ev.scheduled_at),
            status: ev.is_urgent ? "DUE" : "UPCOMING",
            description: String(ev.action_tip || ""),
          } as CaseDeadlineItem);
        }
      }

      // 2. Parallel secondary fetch for top 3 active matters (brief, doc requests, messages)
      if (caseItems.length > 0) {
        const topCases = caseItems.slice(0, 3);
        const matterDetailsPromises = topCases.map(async (c) => {
          const [brief, reqs, msgs] = await Promise.all([
            apiClient.get(`/api/v1/cases/${c.id}/collaboration/brief`).catch(() => null),
            apiClient.get(`/api/v1/cases/${c.id}/collaboration/requests?status=PENDING`).catch(() => []),
            apiClient.get(`/api/v1/cases/${c.id}/collaboration/messages?limit=3`).catch(() => []),
          ]);
          return {
            caseId: c.id,
            brief,
            reqs: Array.isArray(reqs) ? reqs : [],
            msgs: Array.isArray(msgs) ? msgs : [],
          };
        });

        const matterResults = await Promise.all(matterDetailsPromises);

        const newBriefs: Record<string, MatterBriefItem> = {};
        const allDocReqs: MatterRequestItem[] = [];
        const allMsgs: CaseMessageItem[] = [];

        for (const item of matterResults) {
          if (item.brief) {
            newBriefs[item.caseId] = item.brief;
          }
          if (item.reqs) {
            allDocReqs.push(...item.reqs);
          }
          if (item.msgs) {
            allMsgs.push(...item.msgs);
          }
        }

        setBriefsByCaseId(newBriefs);
        setHearings(allHearings);
        setDeadlines(allDeadlines);
        setDocumentRequests(allDocReqs);
        setRecentMessages(allMsgs);
      } else {
        setHearings(allHearings);
        setDeadlines(allDeadlines);
      }
    } catch (err: unknown) {
      console.error("Dashboard fetch error:", err);
      setFetchError("Unable to synchronize your dashboard matters. Please verify your connection.");
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    } else if (user?.role === "LAWYER") {
      router.push("/lawyer/dashboard");
    } else if (user?.role === "ADMIN") {
      router.push("/admin/dashboard");
    } else if (user) {
      void fetchDashboardData();
    }
  }, [user, loading, router, fetchDashboardData]);

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || creating) return;
    setCreating(true);
    try {
      const res = await apiClient.post("/api/v1/cases", {
        title: newTitle.trim(),
        description: newDesc.trim(),
      });
      setCreateModalOpen(false);
      setNewTitle("");
      setNewDesc("");
      router.push(`/cases/${res.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create case";
      alert(`Matter creation error: ${msg}`);
    } finally {
      setCreating(false);
    }
  };

  // Build the prioritized Attention Items queue
  const attentionItems: DashboardAttentionItem[] = useMemo(() => {
    const items: DashboardAttentionItem[] = [];
    const now = new Date();

    // 1. Urgent Hearings (scheduled in the future, prioritized within 7 days)
    const upcomingHearings = hearings
      .filter((h) => h.status === "SCHEDULED" && new Date(h.hearing_at).getTime() >= now.getTime())
      .sort((a, b) => new Date(a.hearing_at).getTime() - new Date(b.hearing_at).getTime());

    for (const h of upcomingHearings) {
      const hearingDate = new Date(h.hearing_at);
      const diffDays = Math.ceil((hearingDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
      const isUrgent = diffDays <= 7;
      const associatedCase = cases.find((c) => c.id === h.case_id);

      const headerText =
        diffDays === 0
          ? "YOUR HEARING IS TODAY"
          : diffDays === 1
          ? "YOUR HEARING IS TOMORROW"
          : `YOUR HEARING IS IN ${diffDays} DAYS`;

      items.push({
        id: `hearing-${h.id}`,
        priority: isUrgent ? 1 : 1.5,
        type: "HEARING",
        headerText,
        badgeLabel: isUrgent ? "Urgent Hearing" : "Court Hearing",
        badgeColor: "#ef4444",
        isUrgent,
        matterTitle: associatedCase?.title,
        caseId: h.case_id,
        detailsContent: (
          <div>
            <div style={{ fontWeight: 600, color: "#fff", fontSize: "14px", marginBottom: "4px" }}>
              {h.court_name} {h.bench_or_coram ? `· Court ${h.bench_or_coram}` : ""}
            </div>
            <div style={{ color: "#94a3b8", fontSize: "13px", marginBottom: "6px" }}>
              {formatDateTime(h.hearing_at)}
            </div>
            <div style={{ fontSize: "12px", color: "#cbd5e1" }}>
              <strong>What to prepare:</strong>{" "}
              {h.notes || h.purpose || "Bring the requested documents."}
            </div>
          </div>
        ),
        actionLabel: "View hearing →",
        actionHref: `/cases/${h.case_id}?tab=hearings`,
      });
    }

    // 2. Important Deadlines (due soon or overdue)
    const activeDeadlines = deadlines
      .filter((d) => d.status === "UPCOMING" || d.status === "DUE" || d.status === "OVERDUE")
      .sort((a, b) => new Date(a.deadline_at).getTime() - new Date(b.deadline_at).getTime());

    for (const d of activeDeadlines) {
      const isOverdue = d.status === "OVERDUE" || new Date(d.deadline_at).getTime() < now.getTime();
      const associatedCase = cases.find((c) => c.id === d.case_id);

      items.push({
        id: `deadline-${d.id}`,
        priority: isOverdue ? 1.2 : 2,
        type: "DEADLINE",
        headerText: isOverdue ? "DEADLINE OVERDUE" : "IMPORTANT DEADLINE",
        badgeLabel: isOverdue ? "Overdue" : "Filing Deadline",
        badgeColor: isOverdue ? "#ef4444" : "#f59e0b",
        isUrgent: isOverdue,
        matterTitle: associatedCase?.title,
        caseId: d.case_id,
        detailsContent: (
          <div>
            <div style={{ fontWeight: 600, color: "#fff", fontSize: "14px", marginBottom: "4px" }}>
              {d.title}
            </div>
            <div style={{ color: isOverdue ? "#fca5a5" : "#94a3b8", fontSize: "13px" }}>
              Due: {formatDate(d.deadline_at)}
            </div>
            {d.description && (
              <div style={{ fontSize: "12px", color: "#cbd5e1", marginTop: "4px" }}>
                {d.description}
              </div>
            )}
          </div>
        ),
        actionLabel: "View deadline →",
        actionHref: `/cases/${d.case_id}?tab=tasks`,
      });
    }

    // 3. Document Requests (from lawyer)
    const pendingDocRequests = documentRequests.filter(
      (r) => r.status === "PENDING" && r.request_type === "DOCUMENT_UPLOAD"
    );

    // Group by case if multiple
    const reqsByCase: Record<string, MatterRequestItem[]> = {};
    for (const r of pendingDocRequests) {
      if (!reqsByCase[r.case_id]) reqsByCase[r.case_id] = [];
      reqsByCase[r.case_id].push(r);
    }

    for (const [caseId, reqList] of Object.entries(reqsByCase)) {
      const associatedCase = cases.find((c) => c.id === caseId);
      const lawyerName = reqList[0].requesting_user_name || "Advocate";
      const count = reqList.length;

      items.push({
        id: `docreq-${caseId}`,
        priority: 3,
        type: "DOCUMENT_REQUEST",
        headerText: count === 1 ? "YOUR LAWYER NEEDS 1 DOCUMENT" : `YOUR LAWYER NEEDS ${count} DOCUMENTS`,
        badgeLabel: "Document Request",
        badgeColor: "#818cf8",
        matterTitle: associatedCase?.title,
        caseId,
        detailsContent: (
          <div>
            <div style={{ color: "#f8fafc", fontSize: "14px", fontWeight: 500, marginBottom: "4px" }}>
              Adv. {lawyerName} requested documents for your case.
            </div>
            <div style={{ fontSize: "12px", color: "#94a3b8" }}>
              {reqList.map((r) => r.title).join(" · ")}
            </div>
          </div>
        ),
        actionLabel: "Upload documents →",
        actionHref: `/cases/${caseId}?tab=documents`,
      });
    }

    // 4. Lawyer Messages (recent formal notes / messages)
    const unreadMsgs = recentMessages.filter((m) => m.sender_role === "LAWYER" || m.sender_role === "PRIMARY_LAWYER");
    for (const msg of unreadMsgs.slice(0, 2)) {
      const associatedCase = cases.find((c) => c.id === msg.case_id);
      items.push({
        id: `msg-${msg.id}`,
        priority: 4,
        type: "MESSAGE",
        headerText: "NEW LAWYER MESSAGE",
        badgeLabel: "Counsel Update",
        badgeColor: "#38bdf8",
        matterTitle: associatedCase?.title,
        caseId: msg.case_id,
        detailsContent: (
          <div>
            <div style={{ color: "#f8fafc", fontSize: "13px", fontStyle: "italic", marginBottom: "4px" }}>
              &ldquo;{msg.content.slice(0, 140)}...&rdquo;
            </div>
            <div style={{ fontSize: "11px", color: "#94a3b8" }}>
              From Adv. {msg.sender_name} · {formatDate(msg.created_at)}
            </div>
          </div>
        ),
        actionLabel: "Open message →",
        actionHref: `/cases/${msg.case_id}?tab=overview`,
      });
    }

    // 5. Pending Payments (consultations needing client payment)
    const pendingPaymentConsultations = consultations.filter(
      (c) => (c.status === "REQUESTED" || c.status === "ACCEPTED") && (c.fee_amount ?? 0) > 0
    );

    for (const consult of pendingPaymentConsultations) {
      const fee = consult.fee_amount || 0;
      const gst = Math.round(fee * 0.18 * 100) / 100;
      const total = Math.round((fee + gst) * 100) / 100;

      items.push({
        id: `pay-${consult.id}`,
        priority: 5,
        type: "PAYMENT",
        headerText: "PAYMENT PENDING",
        badgeLabel: "Payment Due",
        badgeColor: "#eab308",
        detailsContent: (
          <div>
            <div style={{ color: "#f8fafc", fontSize: "13px", marginBottom: "6px" }}>
              Consultation with Adv. {consult.lawyer_name || "Assigned Counsel"}
            </div>
            <div className={styles.paymentBreakdown}>
              <div className={styles.paymentRow}>
                <span>Consultation fee:</span>
                <span>₹{fee.toLocaleString("en-IN")}</span>
              </div>
              <div className={styles.paymentRow}>
                <span>GST (18%):</span>
                <span>₹{gst.toFixed(2)}</span>
              </div>
              <div className={styles.paymentTotalRow}>
                <span>Total:</span>
                <span>₹{total.toFixed(2)}</span>
              </div>
            </div>
          </div>
        ),
        actionLabel: "Pay securely →",
        onActionClick: () => setCheckoutConsultation(consult),
      });
    }

    // 6. Scheduled Consultations
    const scheduledConsultations = consultations.filter(
      (c) => c.status === "PAID" || c.status === "SCHEDULED"
    );

    for (const consult of scheduledConsultations.slice(0, 2)) {
      items.push({
        id: `consult-${consult.id}`,
        priority: 6,
        type: "CONSULTATION",
        headerText: "SCHEDULED CONSULTATION",
        badgeLabel: "Confirmed Session",
        badgeColor: "#10b981",
        detailsContent: (
          <div>
            <div style={{ color: "#f8fafc", fontSize: "14px", fontWeight: 500, marginBottom: "4px" }}>
              Adv. {consult.lawyer_name || "Counsel"}
            </div>
            <div style={{ fontSize: "12px", color: "#94a3b8" }}>
              {formatDateTime(consult.scheduled_start)}
            </div>
          </div>
        ),
        actionLabel: "Join consultation →",
        actionHref: `/consultations/${consult.id}`,
      });
    }

    return items.sort((a, b) => a.priority - b.priority);
  }, [hearings, deadlines, documentRequests, recentMessages, consultations, cases]);

  // Greeting logic
  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
  }, []);

  const clientName = useMemo(() => {
    if (user?.full_name) return user.full_name;
    if (user?.email) {
      const local = user.email.split("@")[0];
      return local.replace(/[._]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    }
    return "Client";
  }, [user]);

  // Filtered cases
  const filteredCases = useMemo(() => {
    return cases.filter((c) => {
      const matchesStatus = statusFilter === "ALL" ? true : c.status === statusFilter;
      const matchesSearch =
        searchQuery === ""
          ? true
          : c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (c.description && c.description.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchesStatus && matchesSearch;
    });
  }, [cases, searchQuery, statusFilter]);

  if (loading || (!user && fetching)) {
    return (
      <div className={styles.dashboardPage}>
        <div className="container" style={{ textAlign: "center", paddingTop: "100px" }}>
          <div className={styles.eyebrow}>
            <span className={styles.eyebrowDot} /> Synchronizing Secure Workspace
          </div>
          <p style={{ color: "#7b8596", marginTop: "12px" }}>
            Authenticating credentials and retrieving matter records...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.dashboardPage}>
      <div className="container">
        {/* Top Greeting Header */}
        <div className={styles.dashboardHeader}>
          <div className={styles.headerTitleSection}>
            <div className={styles.eyebrow}>
              <span className={styles.eyebrowDot} /> Client Attention Center
            </div>
            <h1 className={styles.pageHeading}>
              {greeting}, {clientName}
            </h1>
            <p className={styles.subHeading} style={{ fontSize: "16px", color: "#cbd5e1" }}>
              {attentionItems.length > 0
                ? `You have ${attentionItems.length} thing${attentionItems.length === 1 ? "" : "s"} to take care of.`
                : "You're all caught up. No pending actions need your attention today."}
            </p>
          </div>

          <div className={styles.headerActions}>
            <Link href="/lawyers" className={styles.secondaryActionBtn}>
              <span>⚖</span> Find a lawyer
            </Link>
            <button
              onClick={() => setCreateModalOpen(true)}
              className={styles.primaryActionBtn}
            >
              <span>+</span> Create a case
            </button>
          </div>
        </div>

        {/* Phase 9: What Changed Since Your Last Visit */}
        <WhatChangedBanner />

        {fetchError && (
          <div
            style={{
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              borderRadius: "8px",
              padding: "12px 16px",
              marginBottom: "24px",
              color: "#fca5a5",
              fontSize: "13px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>{fetchError}</span>
            <button
              onClick={() => void fetchDashboardData()}
              style={{
                background: "none",
                border: "none",
                color: "#fff",
                cursor: "pointer",
                textDecoration: "underline",
                fontSize: "12px",
              }}
            >
              Retry
            </button>
          </div>
        )}

        {/* 1. Client Attention Center (Cards) */}
        {attentionItems.length > 0 && (
          <div className={styles.attentionCenter}>
            <div className={styles.attentionHeader}>
              <div className={styles.attentionTitle}>
                <span>⚡</span> Things requiring your attention
              </div>
              <span
                style={{
                  fontSize: "11px",
                  color: "#fca5a5",
                  fontWeight: 700,
                  background: "rgba(239, 68, 68, 0.15)",
                  padding: "2px 8px",
                  borderRadius: "4px",
                }}
              >
                {attentionItems.length} Action{attentionItems.length === 1 ? "" : "s"} Required
              </span>
            </div>

            {attentionItems[0] && (
              <div style={{ marginBottom: "16px" }}>
                <NextStep
                  context={
                    attentionItems[0].type === "HEARING"
                      ? "HEARING"
                      : attentionItems[0].type === "DEADLINE"
                      ? "CASE"
                      : attentionItems[0].type === "DOCUMENT_REQUEST"
                      ? "DOCUMENT"
                      : attentionItems[0].type === "PAYMENT"
                      ? "PAYMENT"
                      : "DASHBOARD"
                  }
                  headline={`${attentionItems[0].headerText}: ${attentionItems[0].matterTitle || "Attention Required"}`}
                  detail={
                    attentionItems[0].type === "HEARING"
                      ? "Your next scheduled court hearing date has been confirmed. Ensure your filings are in order."
                      : attentionItems[0].type === "DEADLINE"
                      ? "A critical procedural deadline requires timely action."
                      : attentionItems[0].type === "DOCUMENT_REQUEST"
                      ? "Your legal counsel has requested supporting documents for your active matter."
                      : "Action required on your matter."
                  }
                  provenance="LCC INFORMATION"
                  urgency={attentionItems[0].isUrgent ? "CRITICAL" : "HIGH"}
                  action={{
                    label: attentionItems[0].actionLabel,
                    href: attentionItems[0].actionHref,
                    onClick: attentionItems[0].onActionClick,
                  }}
                  secondaryAction={{
                    label: "View Calendar",
                    href: "/calendar",
                  }}
                />
              </div>
            )}

            <div className={styles.attentionCards}>
              {attentionItems.map((item) => (
                <div key={item.id} className={styles.attentionCard}>
                  <div className={styles.attentionCardTop}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                      <span
                        style={{
                          fontSize: "10px",
                          color: item.badgeColor,
                          fontWeight: 800,
                          textTransform: "uppercase",
                          letterSpacing: "0.08em",
                        }}
                      >
                        {item.headerText}
                      </span>
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: 700,
                          padding: "1px 6px",
                          borderRadius: "4px",
                          background: `${item.badgeColor}20`,
                          color: item.badgeColor,
                        }}
                      >
                        {item.badgeLabel}
                      </span>
                    </div>

                    {item.matterTitle && (
                      <div style={{ fontSize: "11px", color: "var(--brand-primary, #818cf8)", marginBottom: "4px" }}>
                        Case: <strong>{item.matterTitle}</strong>
                      </div>
                    )}

                    {item.detailsContent}
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "10px" }}>
                    {item.onActionClick ? (
                      <button
                        onClick={item.onActionClick}
                        className={`${styles.attentionCardBtn} ${item.isUrgent ? styles.urgentBtn : ""}`}
                        style={{ cursor: "pointer" }}
                      >
                        {item.actionLabel}
                      </button>
                    ) : item.actionHref ? (
                      <Link
                        href={item.actionHref}
                        className={`${styles.attentionCardBtn} ${item.isUrgent ? styles.urgentBtn : ""}`}
                      >
                        {item.actionLabel}
                      </Link>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 2. My Cases Section */}
        <div style={{ marginTop: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
            <h2 className={styles.myCasesHeading}>
              <span>📁</span> My cases
            </h2>

            {cases.length > 0 && (
              <div className={styles.filterControls}>
                <div className={styles.searchBox}>
                  <span className={styles.searchIcon}>🔍</span>
                  <input
                    type="text"
                    placeholder="Search your cases..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className={styles.searchInput}
                  />
                </div>

                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className={styles.filterSelect}
                  aria-label="Filter cases by status"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="OPEN">Open</option>
                  <option value="IN_PROGRESS">In Progress</option>
                  <option value="IN_REVIEW">Under Review</option>
                  <option value="CLOSED">Closed</option>
                </select>
              </div>
            )}
          </div>

          {cases.length === 0 ? (
            /* 3. Empty State for First-Time Clients */
            <div className={styles.emptyStateContainer}>
              <div className={styles.emptyStateIcon}>⚖</div>
              <h2 className={styles.emptyStateHeading}>You don&apos;t have a case yet.</h2>
              <p className={styles.emptyStateText}>
                Create a case to keep your documents, hearings, lawyer and important updates together.
              </p>
              <div className={styles.emptyStateActions}>
                <button
                  onClick={() => setCreateModalOpen(true)}
                  className={styles.primaryActionBtn}
                >
                  <span>+</span> Create a case
                </button>
                <Link href="/lawyers" className={styles.secondaryActionBtn}>
                  <span>⚖</span> Find a lawyer
                </Link>
              </div>
            </div>
          ) : filteredCases.length === 0 ? (
            <div className={styles.emptyStateContainer} style={{ padding: "32px 20px" }}>
              <p style={{ color: "#94a3b8", fontSize: "14px" }}>
                No matters match &ldquo;{searchQuery}&rdquo;. Try resetting your search filter.
              </p>
            </div>
          ) : (
            <div className={styles.matterGrid}>
              {filteredCases.map((c) => {
                const brief = briefsByCaseId[c.id];
                const courtDisplay = brief?.next_hearing_court || "Official Court Record";
                const nextEventDisplay = brief?.next_hearing_date
                  ? `Next hearing: ${formatDate(brief.next_hearing_date)}`
                  : "Waiting for next hearing date";
                const lawyerDisplay = brief?.lead_counsel_name
                  ? `Adv. ${brief.lead_counsel_name}`
                  : "Not assigned yet";

                return (
                  <div key={c.id} className={styles.clientMatterCard}>
                    <div className={styles.matterCardTop}>
                      <div className={styles.matterCardHeaderRow}>
                        <div>
                          <div className={styles.matterCardCourt}>
                            <span>🏛</span> {courtDisplay}
                          </div>
                          <h3 className={styles.matterCardTitle}>{c.title}</h3>
                        </div>
                      </div>

                      {/* Plain-Language Status with LegalTerm */}
                      <div style={{ marginTop: "4px" }}>
                        <LegalTerm term={c.status} layout="stacked" showBadge={false} />
                      </div>

                      {/* Next Important Event */}
                      <div className={styles.matterCardNextEvent}>
                        <span className={styles.matterCardNextEventLabel}>Next Event</span>
                        <span className={styles.matterCardNextEventValue}>{nextEventDisplay}</span>
                      </div>
                    </div>

                    <div className={styles.matterCardFooter}>
                      <div className={styles.matterCardMeta}>
                        <div>
                          <strong>Lawyer:</strong> {lawyerDisplay}
                        </div>
                        <div>
                          Last update: {formatDate(c.updated_at || c.created_at)}
                        </div>
                      </div>

                      <Link href={`/cases/${c.id}`} className={styles.openCaseBtn}>
                        Open case →
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Create Case Modal */}
        {createModalOpen && (
          <div
            className={styles.modalOverlay}
            onClick={() => setCreateModalOpen(false)}
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-matter-title"
          >
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 id="create-matter-title">Create a new legal matter</h3>
                <button
                  onClick={() => setCreateModalOpen(false)}
                  className={styles.modalClose}
                  aria-label="Close"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleCreateCase} className={styles.modalBody}>
                <div className={styles.formGroup}>
                  <label htmlFor="matter-title" className={styles.label}>
                    Matter Title *
                  </label>
                  <input
                    id="matter-title"
                    type="text"
                    required
                    placeholder="e.g., Property dispute · DLF Phase 2"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    className={styles.inputField}
                  />
                  <span style={{ fontSize: "11px", color: "#8c97ad", marginTop: "4px" }}>
                    Give your case a clear name so you can recognize it easily.
                  </span>
                </div>

                <div className={styles.formGroup}>
                  <label htmlFor="matter-desc" className={styles.label}>
                    Brief description (optional)
                  </label>
                  <textarea
                    id="matter-desc"
                    rows={3}
                    placeholder="Describe what happened or what help you need..."
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                    className={styles.textareaField}
                  />
                </div>

                <div className={styles.modalFooter}>
                  <button
                    type="button"
                    onClick={() => setCreateModalOpen(false)}
                    className={styles.secondaryActionBtn}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creating || !newTitle.trim()}
                    className={styles.primaryActionBtn}
                  >
                    {creating ? "Creating..." : "Create matter"}
                  </button>
                </div>
              </form>
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
              void fetchDashboardData();
            }}
          />
        )}

        {/* Consultation Action Modal (Reschedule / Cancel) */}
        {actionConsultationModal && (
          <ConsultationActionModal
            type={actionConsultationModal.type}
            consultation={actionConsultationModal.consultation}
            onClose={() => setActionConsultationModal(null)}
            onSuccess={() => {
              setActionConsultationModal(null);
              void fetchDashboardData();
            }}
          />
        )}
      </div>
    </div>
  );
}
