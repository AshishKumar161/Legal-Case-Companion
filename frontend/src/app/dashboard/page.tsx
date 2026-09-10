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
import { PaymentCheckoutModal } from "@/components/Payment/PaymentCheckoutModal";
import { ConsultationActionModal } from "@/components/Consultation/ConsultationActionModal";
import { WhatChangedBanner } from "@/components/WhatChangedBanner";
import {
  CaseIcon,
  CalendarIcon,
  LawyerIcon,
  PlusIcon,
  SearchIcon,
  ArrowRightIcon,
} from "@/components/ui/Icons";
import styles from "./dashboard.module.css";

interface DashboardAttentionItem {
  id: string;
  priority: number; // 1: Urgent Hearing, 2: Deadline, 3: Document Request, 4: Message, 5: Payment, 6: Consultation
  type: "HEARING" | "DEADLINE" | "DOCUMENT_REQUEST" | "MESSAGE" | "PAYMENT" | "CONSULTATION";
  headerText: string;
  badgeLabel: string;
  badgeType: "urgent" | "warning" | "success" | "info";
  matterTitle?: string;
  caseId?: string;
  headline: string;
  detail: string;
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
      month: "short",
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

      // Fetch Cases, Consultations, and Aggregated Calendar Events in parallel
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

      // Extract hearings and deadlines directly from calendar events
      const rawEvents = (calEventsRes as { events?: Array<Record<string, unknown>> })?.events || [];
      const extractedHearings: CaseHearingItem[] = [];
      const extractedDeadlines: CaseDeadlineItem[] = [];

      for (const ev of rawEvents) {
        if (ev.event_type === "hearing") {
          extractedHearings.push({
            id: String(ev.id),
            case_id: String(ev.case_id || ""),
            hearing_at: String(ev.start_time || ev.event_date || new Date().toISOString()),
            court_name: String(ev.location || "Official Court"),
            bench_or_coram: ev.courtroom ? String(ev.courtroom) : undefined,
            purpose: String(ev.description || "Court hearing"),
            status: "SCHEDULED",
            is_confirmed: true,
            created_at: String(ev.start_time || new Date().toISOString()),
          });
        } else if (ev.event_type === "limitation" || ev.event_type === "deadline") {
          extractedDeadlines.push({
            id: String(ev.id),
            case_id: String(ev.case_id || ""),
            title: String(ev.title || "Legal Deadline"),
            deadline_at: String(ev.start_time || ev.event_date || new Date().toISOString()),
            deadline_type: "PROCEDURAL" as any,
            is_confirmed: true,
            status: "UPCOMING",
            description: ev.description ? String(ev.description) : undefined,
            created_at: String(ev.start_time || new Date().toISOString()),
          });
        }
      }

      setHearings(extractedHearings);
      setDeadlines(extractedDeadlines);

      // Fetch case briefs and document requests
      if (caseItems.length > 0) {
        const topCases = caseItems.slice(0, 8);
        const briefs = await Promise.all(
          topCases.map(async (c) => {
            const brief = await apiClient.get(`/api/v1/cases/${c.id}/collaboration/brief`).catch(() => null);
            return { caseId: c.id, brief };
          })
        );
        const newBriefs: Record<string, MatterBriefItem> = {};
        for (const b of briefs) {
          if (b.brief) newBriefs[b.caseId] = b.brief;
        }
        setBriefsByCaseId(newBriefs);

        const allDocRequests: MatterRequestItem[] = [];
        const allMsgs: CaseMessageItem[] = [];

        await Promise.all(
          topCases.map(async (c) => {
            try {
              const reqs = await apiClient.get(`/api/v1/cases/${c.id}/collaboration/requests`).catch(() => []);
              if (Array.isArray(reqs)) {
                allDocRequests.push(...reqs);
              }
              const msgs = await apiClient.get(`/api/v1/cases/${c.id}/collaboration/messages`).catch(() => []);
              if (Array.isArray(msgs)) {
                allMsgs.push(...msgs);
              }
            } catch {
              // Ignore per-case non-critical errors
            }
          })
        );

        setDocumentRequests(allDocRequests);
        setRecentMessages(allMsgs);
      }
    } catch {
      setFetchError("Unable to load case details. Please try refreshing.");
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    } else if (user) {
      void fetchDashboardData();
    }
  }, [user, loading, router, fetchDashboardData]);

  // Handle Creating a New Case
  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || creating) return;
    try {
      setCreating(true);
      const res: any = await apiClient.post("/api/v1/cases", {
        title: newTitle.trim(),
        description: newDesc.trim(),
      });
      setCreateModalOpen(false);
      setNewTitle("");
      setNewDesc("");
      router.push(`/cases/${res.id}`);
    } catch {
      alert("Failed to create case. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  // Compile Prioritized Attention Items (Section 6)
  const attentionItems = useMemo(() => {
    const items: DashboardAttentionItem[] = [];
    const now = new Date();

    // 1. Upcoming Hearings (Red/Urgent)
    const upcomingHearings = hearings
      .filter((h) => h.status === "SCHEDULED" && new Date(h.hearing_at).getTime() >= now.getTime())
      .sort((a, b) => new Date(a.hearing_at).getTime() - new Date(b.hearing_at).getTime());

    for (const h of upcomingHearings.slice(0, 2)) {
      const hearingDate = new Date(h.hearing_at);
      const diffDays = Math.ceil((hearingDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
      const associatedCase = cases.find((c) => c.id === h.case_id);

      const headerText =
        diffDays === 0
          ? "Hearing is today"
          : diffDays === 1
          ? "Hearing is tomorrow"
          : `Hearing coming up in ${diffDays} days`;

      items.push({
        id: `hearing-${h.id}`,
        priority: 1,
        type: "HEARING",
        headerText,
        badgeLabel: diffDays <= 3 ? "Urgent Hearing" : "Court Hearing",
        badgeType: "urgent",
        isUrgent: diffDays <= 3,
        matterTitle: associatedCase?.title,
        caseId: h.case_id,
        headline: `${h.court_name} ${h.bench_or_coram ? `· Court ${h.bench_or_coram}` : ""}`,
        detail: `${formatDateTime(h.hearing_at)} · What to prepare: ${h.notes || h.purpose || "Bring your ID and requested documents."}`,
        actionLabel: "View Hearing",
        actionHref: `/cases/${h.case_id}?tab=hearings`,
      });
    }

    // 2. Lawyer Document Requests (Yellow/Warning)
    const pendingDocRequests = documentRequests.filter(
      (r) => r.status === "PENDING" && r.request_type === "DOCUMENT_UPLOAD"
    );

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
        priority: 2,
        type: "DOCUMENT_REQUEST",
        headerText: count === 1 ? "Document requested" : `${count} documents requested`,
        badgeLabel: "Lawyer Request",
        badgeType: "warning",
        matterTitle: associatedCase?.title,
        caseId,
        headline: `Your lawyer needs ${count === 1 ? "one document" : `${count} documents`}`,
        detail: `Adv. ${lawyerName} requested: ${reqList.map((r) => r.title).join(", ")}.`,
        actionLabel: "Upload Document",
        actionHref: `/cases/${caseId}?tab=documents`,
      });
    }

    // 3. Important Deadlines (Legal Deadlines)
    const activeDeadlines = deadlines
      .filter((d) => d.status === "UPCOMING" || d.status === "DUE" || d.status === "OVERDUE")
      .sort((a, b) => new Date(a.deadline_at).getTime() - new Date(b.deadline_at).getTime());

    for (const d of activeDeadlines.slice(0, 1)) {
      const isOverdue = d.status === "OVERDUE" || new Date(d.deadline_at).getTime() < now.getTime();
      const associatedCase = cases.find((c) => c.id === d.case_id);

      items.push({
        id: `deadline-${d.id}`,
        priority: 3,
        type: "DEADLINE",
        headerText: isOverdue ? "Legal deadline overdue" : "Important legal deadline",
        badgeLabel: isOverdue ? "Overdue" : "Legal Deadline",
        badgeType: isOverdue ? "urgent" : "warning",
        isUrgent: isOverdue,
        matterTitle: associatedCase?.title,
        caseId: d.case_id,
        headline: d.title,
        detail: `Due: ${formatDate(d.deadline_at)} ${d.description ? `· ${d.description}` : ""}`,
        actionLabel: "View Details",
        actionHref: `/cases/${d.case_id}?tab=tasks`,
      });
    }

    // 4. Case Updates / Messages (Green/Success)
    const unreadMsgs = recentMessages.filter((m) => m.sender_role === "LAWYER" || m.sender_role === "PRIMARY_LAWYER");
    for (const msg of unreadMsgs.slice(0, 1)) {
      const associatedCase = cases.find((c) => c.id === msg.case_id);
      items.push({
        id: `msg-${msg.id}`,
        priority: 4,
        type: "MESSAGE",
        headerText: "Case update from lawyer",
        badgeLabel: "Case Update",
        badgeType: "success",
        matterTitle: associatedCase?.title,
        caseId: msg.case_id,
        headline: `New message from Adv. ${msg.sender_name}`,
        detail: `"${msg.content.slice(0, 110)}..."`,
        actionLabel: "View Update",
        actionHref: `/cases/${msg.case_id}?tab=overview`,
      });
    }

    // 5. Scheduled Consultations (Info/Blue)
    const scheduledConsultations = consultations.filter(
      (c) => c.status === "PAID" || c.status === "SCHEDULED"
    );

    for (const consult of scheduledConsultations.slice(0, 1)) {
      items.push({
        id: `consult-${consult.id}`,
        priority: 5,
        type: "CONSULTATION",
        headerText: "Upcoming lawyer consultation",
        badgeLabel: "Confirmed Session",
        badgeType: "info",
        headline: `Adv. ${consult.lawyer_name || "Advocate"}`,
        detail: `Scheduled for ${formatDateTime(consult.scheduled_start)}. Ensure you have your questions ready.`,
        actionLabel: "Join Consultation",
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
    return "there";
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
          <p style={{ color: "var(--text-secondary)", fontSize: "16px" }}>
            Loading your case assistant...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.dashboardPage}>
      <div className="container">
        {/* Top Greeting Header (Section 6) */}
        <div className={styles.dashboardHeader}>
          <div className={styles.headerTitleSection}>
            <div className={styles.eyebrow}>
              <span className={styles.eyebrowDot} /> Your Legal Assistant
            </div>
            <h1 className={styles.pageHeading}>
              {greeting}, {clientName}.
            </h1>
            <p className={styles.subHeading}>
              {attentionItems.length > 0
                ? "Here's what needs your attention today."
                : "You're all caught up. No urgent actions need your attention today."}
            </p>
          </div>

          <div className={styles.headerActions}>
            <Link href="/lawyers" className={styles.secondaryActionBtn}>
              <LawyerIcon size={16} />
              <span>Find a Lawyer</span>
            </Link>
            <button
              onClick={() => setCreateModalOpen(true)}
              className={styles.primaryActionBtn}
            >
              <PlusIcon size={16} color="#FFFFFF" />
              <span>Start a Case</span>
            </button>
          </div>
        </div>

        {/* Phase 9: What Changed Notice */}
        <WhatChangedBanner />

        {fetchError && (
          <div
            style={{
              background: "rgba(220, 38, 38, 0.06)",
              border: "1px solid rgba(220, 38, 38, 0.25)",
              borderRadius: "8px",
              padding: "12px 16px",
              marginBottom: "24px",
              color: "var(--status-urgent)",
              fontSize: "14px",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span>{fetchError}</span>
            <button
              onClick={() => void fetchDashboardData()}
              style={{
                textDecoration: "underline",
                color: "inherit",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Retry
            </button>
          </div>
        )}

        {/* 1. What Needs My Attention? (Section 6) */}
        {attentionItems.length > 0 && (
          <section className={styles.attentionCenter} aria-label="What needs your attention">
            <div className={styles.attentionHeader}>
              <h2 className={styles.attentionTitle}>
                What needs your attention
              </h2>
              <span
                className={styles.attentionBadge}
                style={{
                  background: "rgba(15, 30, 54, 0.08)",
                  color: "var(--navy-primary)",
                }}
              >
                {attentionItems.length} {attentionItems.length === 1 ? "Item" : "Items"}
              </span>
            </div>

            <div className={styles.attentionCards}>
              {attentionItems.map((item) => {
                const cardClass =
                  item.badgeType === "urgent"
                    ? styles.attentionCardUrgent
                    : item.badgeType === "warning"
                    ? styles.attentionCardWarning
                    : item.badgeType === "success"
                    ? styles.attentionCardSuccess
                    : styles.attentionCardInfo;

                const dotColor =
                  item.badgeType === "urgent"
                    ? "var(--status-urgent)"
                    : item.badgeType === "warning"
                    ? "var(--status-warning)"
                    : item.badgeType === "success"
                    ? "var(--status-success)"
                    : "var(--status-info)";

                return (
                  <div key={item.id} className={`${styles.attentionCard} ${cardClass}`}>
                    <div className={styles.attentionCardContent}>
                      <div className={styles.attentionStatusRow}>
                        <span className={styles.statusDot} style={{ background: dotColor }} />
                        <span
                          className={styles.attentionCardHeading}
                          style={{ color: dotColor }}
                        >
                          {item.headerText}
                        </span>
                        {item.matterTitle && (
                          <>
                            <span style={{ color: "var(--border-hover)" }}>•</span>
                            <span className={styles.attentionCaseTag}>
                              Case: <strong>{item.matterTitle}</strong>
                            </span>
                          </>
                        )}
                      </div>

                      <div className={styles.attentionMainText}>{item.headline}</div>
                      <div className={styles.attentionSubText}>{item.detail}</div>
                    </div>

                    <div className={styles.attentionCardAction}>
                      {item.onActionClick ? (
                        <button
                          onClick={item.onActionClick}
                          className={`${styles.actionBtn} ${
                            item.isUrgent ? styles.actionBtnUrgent : styles.actionBtnPrimary
                          }`}
                        >
                          <span>{item.actionLabel}</span>
                          <ArrowRightIcon size={14} />
                        </button>
                      ) : item.actionHref ? (
                        <Link
                          href={item.actionHref}
                          className={`${styles.actionBtn} ${
                            item.isUrgent ? styles.actionBtnUrgent : styles.actionBtnPrimary
                          }`}
                        >
                          <span>{item.actionLabel}</span>
                          <ArrowRightIcon size={14} />
                        </Link>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* 2. My Cases Section */}
        <section style={{ marginTop: "32px" }}>
          <div className={styles.sectionHeadingRow}>
            <h2 className={styles.myCasesHeading}>
              <CaseIcon size={22} color="var(--navy-primary)" />
              <span>My Cases</span>
            </h2>

            {cases.length > 0 && (
              <div className={styles.filterControls}>
                <div className={styles.searchBox}>
                  <SearchIcon size={14} />
                  <input
                    type="text"
                    placeholder="Search your cases..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className={styles.searchInput}
                    aria-label="Search cases"
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
            /* Empty State for First-Time Clients */
            <div className={styles.emptyContainer}>
              <div className={styles.emptyIcon}>
                <CaseIcon size={28} />
              </div>
              <h3 className={styles.emptyHeading}>You don&apos;t have a case yet.</h3>
              <p className={styles.emptyDesc}>
                Create a case to keep your documents, hearings, lawyer, and important updates together in one simple place.
              </p>
              <div className={styles.emptyActions}>
                <button
                  onClick={() => setCreateModalOpen(true)}
                  className="btn btn-primary"
                >
                  <PlusIcon size={16} />
                  <span>Start a Case</span>
                </button>
                <Link href="/lawyers" className="btn btn-secondary">
                  <LawyerIcon size={16} />
                  <span>Find a Lawyer</span>
                </Link>
              </div>
            </div>
          ) : filteredCases.length === 0 ? (
            <div className={styles.emptyContainer}>
              <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
                No cases match &ldquo;{searchQuery}&rdquo;. Try clearing your search.
              </p>
            </div>
          ) : (
            <div className={styles.caseGrid}>
              {filteredCases.map((c) => {
                const brief = briefsByCaseId[c.id];
                const courtDisplay = brief?.next_hearing_court || "Court Record";
                const nextEventDisplay = brief?.next_hearing_date
                  ? `Next hearing: ${formatDate(brief.next_hearing_date)}`
                  : "Waiting for next hearing date";
                const lawyerDisplay = brief?.lead_counsel_name
                  ? `Adv. ${brief.lead_counsel_name}`
                  : "Lawyer not assigned yet";

                return (
                  <Link key={c.id} href={`/cases/${c.id}`} className={styles.caseCard}>
                    <div className={styles.caseTop}>
                      <div className={styles.caseBadgeRow}>
                        <span
                          style={{
                            fontSize: "12px",
                            fontWeight: 600,
                            padding: "2px 8px",
                            borderRadius: "var(--radius-full)",
                            background:
                              c.status === "CLOSED"
                                ? "var(--surface-subtle)"
                                : "var(--status-safe-bg)",
                            color:
                              c.status === "CLOSED"
                                ? "var(--text-muted)"
                                : "var(--status-safe-text)",
                            border: `1px solid ${
                              c.status === "CLOSED"
                                ? "var(--border-subtle)"
                                : "var(--status-safe-border)"
                            }`,
                          }}
                        >
                          ● {c.status === "CLOSED" ? "Closed Case" : "Active Case"}
                        </span>
                        <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>
                          REF #{c.id.slice(0, 8).toUpperCase()}
                        </span>
                      </div>

                      <h3 className={styles.caseTitle}>{c.title}</h3>

                      <div className={styles.caseMeta}>
                        <div><strong>Court:</strong> {courtDisplay}</div>
                        <div><strong>Lawyer:</strong> {lawyerDisplay}</div>
                      </div>

                      <div className={styles.caseNextEvent}>
                        <CalendarIcon size={14} color="var(--navy-primary)" />
                        <span>{nextEventDisplay}</span>
                      </div>
                    </div>

                    <div className={styles.caseFooter}>
                      <span>View Case Details</span>
                      <ArrowRightIcon size={14} />
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* Start Case Modal */}
      {createModalOpen && (
        <div className={styles.modalBackdrop} onClick={() => setCreateModalOpen(false)}>
          <div className={styles.modalBox} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3 className={styles.modalTitle}>Start a New Case</h3>
              <button
                className={styles.closeBtn}
                onClick={() => setCreateModalOpen(false)}
                aria-label="Close dialog"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateCase}>
              <div className="input-group">
                <label className="input-label">What is this case about?</label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. Property boundary dispute, Rent agreement issue"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  required
                />
              </div>

              <div className="input-group">
                <label className="input-label">Briefly explain what happened (Optional)</label>
                <textarea
                  className="input-field"
                  rows={3}
                  placeholder="Describe your situation in plain words..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "20px" }}>
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
                  className="btn btn-secondary"
                  disabled={creating}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={creating}
                >
                  {creating ? "Creating Case..." : "Continue →"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Consultation Action & Checkout Modals */}
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
  );
}
