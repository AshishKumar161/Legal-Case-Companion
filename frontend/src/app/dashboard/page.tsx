"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiClient } from "@/api/client";
import {
  CaseItem,
  ConsultationItem,
  CaseHearingItem,
  MatterRequestItem,
  MatterBriefItem,
} from "@/types";
import { CaseCard } from "@/components/ui/CaseCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import {
  CaseIcon,
  PlusIcon,
  AssistantIcon,
  ArrowRightIcon,
} from "@/components/ui/Icons";
import styles from "./dashboard.module.css";

function formatDateShort(dateString?: string | null): string {
  if (!dateString) return "";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
    });
  } catch {
    return "";
  }
}

function formatDateFull(dateString?: string | null): string {
  if (!dateString) return "";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return "";
  }
}

export default function Dashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [cases, setCases] = useState<CaseItem[]>([]);
  const [briefsByCaseId, setBriefsByCaseId] = useState<Record<string, MatterBriefItem>>({});
  const [hearings, setHearings] = useState<CaseHearingItem[]>([]);
  const [documentRequests, setDocumentRequests] = useState<MatterRequestItem[]>([]);
  const [consultations, setConsultations] = useState<ConsultationItem[]>([]);
  const [currentTimestamp] = useState(() => Date.now());

  const [fetching, setFetching] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Start Case Modal State
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  // Time of day greeting
  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 17) return "Good afternoon";
    return "Good evening";
  }, []);

  const userName = useMemo(() => {
    if (!user) return "";
    if (user.full_name) return user.full_name.split(" ")[0];
    if (user.email) return user.email.split("@")[0];
    return "";
  }, [user]);

  const fetchDashboardData = useCallback(async () => {
    try {
      setFetching(true);
      setFetchError(null);

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

      const rawEvents = (calEventsRes as { events?: Array<Record<string, unknown>> })?.events || [];
      const extractedHearings: CaseHearingItem[] = [];

      for (const ev of rawEvents) {
        if (ev.event_type === "hearing") {
          extractedHearings.push({
            id: String(ev.id),
            case_id: String(ev.case_id || ""),
            hearing_at: String(ev.start_time || ev.event_date || new Date().toISOString()),
            court_name: String(ev.location || "District Court"),
            bench_or_coram: ev.courtroom ? String(ev.courtroom) : undefined,
            purpose: String(ev.description || "Court hearing"),
            status: "SCHEDULED",
            is_confirmed: true,
            created_at: String(ev.start_time || new Date().toISOString()),
          });
        }
      }

      setHearings(extractedHearings);

      if (caseItems.length > 0) {
        const topCases = caseItems.slice(0, 6);
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
        await Promise.all(
          topCases.map(async (c) => {
            try {
              const reqs = await apiClient.get(`/api/v1/cases/${c.id}/collaboration/requests`).catch(() => []);
              if (Array.isArray(reqs)) allDocRequests.push(...reqs);
            } catch {
              // Ignore non-critical request errors
            }
          })
        );
        setDocumentRequests(allDocRequests);
      }
    } catch {
      setFetchError("Unable to load case overview. Please check your connection.");
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    } else if (user?.role === "LAWYER") {
      router.push("/lawyer/dashboard");
    } else if (user) {
      void fetchDashboardData();
    }
  }, [user, loading, router, fetchDashboardData]);

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || creating) return;
    try {
      setCreating(true);
      const res = (await apiClient.post("/api/v1/cases", {
        title: newTitle.trim(),
        description: newDesc.trim(),
      })) as { id: string };
      setCreateModalOpen(false);
      setNewTitle("");
      setNewDesc("");
      router.push(`/cases/${res.id}`);
    } catch {
      alert("Unable to create case right now. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  // Next Step Resolution (Section 10)
  const nextStep = useMemo(() => {
    // 1. Pending document request
    const pendingReq = documentRequests.find((r) => r.status === "PENDING");
    if (pendingReq) {
      const associatedCase = cases.find((c) => c.id === pendingReq.case_id);
      return {
        title: pendingReq.title || "Upload the court notice you received",
        description: "This will help keep your case information and lawyer updated.",
        actionLabel: "Upload document",
        actionHref: `/cases/${pendingReq.case_id}?tab=documents`,
        badge: "Action needed",
        badgeVariant: "urgent" as const,
        caseTitle: associatedCase?.title,
      };
    }

    // 2. Upcoming hearing within 14 days
    const upcomingHearing = hearings
      .filter((h) => new Date(h.hearing_at).getTime() >= currentTimestamp)
      .sort((a, b) => new Date(a.hearing_at).getTime() - new Date(b.hearing_at).getTime())[0];

    if (upcomingHearing) {
      const dateFormatted = formatDateFull(upcomingHearing.hearing_at);
      const associatedCase = cases.find((c) => c.id === upcomingHearing.case_id);
      return {
        title: `Court hearing scheduled on ${dateFormatted}`,
        description: `Listing at ${upcomingHearing.court_name}. Check with your lawyer on required documents.`,
        actionLabel: "View hearing details",
        actionHref: `/cases/${upcomingHearing.case_id}?tab=dates`,
        badge: "Court hearing",
        badgeVariant: "primary" as const,
        caseTitle: associatedCase?.title,
      };
    }

    // 3. If cases exist but no urgent action
    if (cases.length > 0) {
      const firstCase = cases[0];
      return {
        title: "All current tasks are up to date",
        description: `Your matter "${firstCase.title}" is in progress. You can review saved documents or message your lawyer anytime.`,
        actionLabel: "View case overview",
        actionHref: `/cases/${firstCase.id}`,
        badge: "Up to date",
        badgeVariant: "success" as const,
        caseTitle: firstCase.title,
      };
    }

    // 4. No cases yet
    return null;
  }, [documentRequests, hearings, cases, currentTimestamp]);

  // Combined upcoming events list (hearings & consultations)
  const upcomingEvents = useMemo(() => {
    const list: Array<{
      id: string;
      dateShort: string;
      title: string;
      subtitle: string;
      href: string;
      type: "hearing" | "consultation";
    }> = [];

    const now = currentTimestamp;

    for (const h of hearings) {
      const time = new Date(h.hearing_at).getTime();
      if (time >= now) {
        list.push({
          id: `h-${h.id}`,
          dateShort: formatDateShort(h.hearing_at),
          title: "Court hearing",
          subtitle: h.court_name || "Official Court",
          href: `/cases/${h.case_id}?tab=dates`,
          type: "hearing",
        });
      }
    }

    for (const c of consultations) {
      const dateStr = c.scheduled_at || c.created_at;
      const time = new Date(dateStr).getTime();
      if (time >= now && c.status !== "CANCELLED") {
        list.push({
          id: `c-${c.id}`,
          dateShort: formatDateShort(dateStr),
          title: "Lawyer consultation",
          subtitle: c.lawyer_name ? `Adv. ${c.lawyer_name}` : "Scheduled consultation",
          href: "/consultations",
          type: "consultation",
        });
      }
    }

    return list.sort((a, b) => (a.dateShort > b.dateShort ? 1 : -1)).slice(0, 4);
  }, [hearings, consultations, currentTimestamp]);

  return (
    <div className={styles.dashboardPage}>
      <div className="container" style={{ maxWidth: "1080px" }}>
        {/* Top Header: 5-Second Greeting */}
        <div style={{ marginBottom: "32px" }}>
          <h1
            style={{
              fontSize: "clamp(1.75rem, 3.5vw, 2.3rem)",
              fontWeight: 800,
              color: "var(--navy-primary, #17324D)",
              letterSpacing: "-0.025em",
              marginBottom: "6px",
            }}
          >
            {greeting}, {userName || "there"}
          </h1>
          <p
            style={{
              fontSize: "1.05rem",
              color: "var(--text-secondary, #52606D)",
              margin: 0,
            }}
          >
            Here&apos;s what needs your attention.
          </p>
        </div>

        {fetching ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            <LoadingSkeleton type="card" count={2} />
          </div>
        ) : fetchError ? (
          <div
            style={{
              background: "var(--surface-card, #FFFFFF)",
              border: "1px solid var(--status-urgent, #C53030)",
              borderRadius: "14px",
              padding: "24px",
              marginBottom: "24px",
              color: "var(--text-primary, #17212B)",
            }}
          >
            <h3 style={{ color: "var(--status-urgent, #C53030)", margin: "0 0 8px 0" }}>
              Something went wrong
            </h3>
            <p style={{ margin: "0 0 16px 0", color: "var(--text-secondary, #52606D)" }}>
              {fetchError}
            </p>
            <Button variant="secondary" onClick={() => void fetchDashboardData()}>
              Try again
            </Button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
            {/* KYC Incomplete Alert Banner */}
            {!user?.is_kyc_completed && (
              <div
                style={{
                  background: "linear-gradient(135deg, rgba(234, 88, 12, 0.08) 0%, rgba(245, 158, 11, 0.05) 100%)",
                  border: "1px solid rgba(245, 158, 11, 0.35)",
                  borderRadius: "16px",
                  padding: "20px 24px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "20px",
                  flexWrap: "wrap",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "16px", flex: "1 1 300px" }}>
                  <div
                    style={{
                      width: "44px",
                      height: "44px",
                      borderRadius: "12px",
                      background: "rgba(245, 158, 11, 0.15)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "22px",
                      flexShrink: 0,
                    }}
                  >
                    🛡️
                  </div>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          textTransform: "uppercase",
                          padding: "2px 8px",
                          borderRadius: "4px",
                          background: "rgba(245, 158, 11, 0.2)",
                          color: "#D97706",
                        }}
                      >
                        Action Required
                      </span>
                      <h4 style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: "var(--text-primary, #0F172A)" }}>
                        Complete Your Profile & KYC Verification
                      </h4>
                    </div>
                    <p style={{ margin: 0, fontSize: "13px", color: "var(--text-secondary, #475569)" }}>
                      Authenticating your identity unlocks verified consultations, court document vaults, and seamless matter representation.
                    </p>
                  </div>
                </div>
                <Link
                  href="/kyc"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    background: "#0284C7",
                    color: "#FFFFFF",
                    padding: "10px 20px",
                    borderRadius: "10px",
                    fontSize: "14px",
                    fontWeight: 600,
                    textDecoration: "none",
                    boxShadow: "0 2px 8px rgba(2, 132, 199, 0.3)",
                    whiteSpace: "nowrap",
                  }}
                >
                  Complete KYC Now →
                </Link>
              </div>
            )}

            {/* Section 1: Your Next Step (Prominent, High Clarity) */}
            {nextStep && (
              <section aria-labelledby="next-step-title">
                <div
                  style={{
                    background: "var(--surface-card, #FFFFFF)",
                    border: "1px solid var(--border-subtle, #D9E2EC)",
                    borderRadius: "16px",
                    padding: "24px 28px",
                    boxShadow: "var(--shadow-sm)",
                    display: "flex",
                    alignItems: "flex-start",
                    justifyContent: "space-between",
                    gap: "24px",
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ flex: "1 1 360px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                      <span
                        style={{
                          fontSize: "12px",
                          fontWeight: 700,
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          color: "var(--navy-primary, #17324D)",
                        }}
                      >
                        Your next step
                      </span>
                      {nextStep.caseTitle && (
                        <span style={{ fontSize: "12px", color: "var(--text-muted, #7B8794)" }}>
                          · {nextStep.caseTitle}
                        </span>
                      )}
                    </div>

                    <h2
                      id="next-step-title"
                      style={{
                        margin: "0 0 8px 0",
                        fontSize: "1.25rem",
                        fontWeight: 700,
                        color: "var(--text-primary, #17212B)",
                        lineHeight: 1.35,
                      }}
                    >
                      {nextStep.title}
                    </h2>

                    <p
                      style={{
                        margin: 0,
                        fontSize: "0.9375rem",
                        color: "var(--text-secondary, #52606D)",
                        lineHeight: 1.5,
                      }}
                    >
                      {nextStep.description}
                    </p>
                  </div>

                  <div style={{ alignSelf: "center", flexShrink: 0 }}>
                    <Link
                      href={nextStep.actionHref}
                      className="btn btn-primary"
                      style={{
                        minHeight: "46px",
                        padding: "10px 24px",
                        fontSize: "15px",
                        boxShadow: "var(--shadow-sm)",
                      }}
                    >
                      <span>{nextStep.actionLabel}</span>
                      <ArrowRightIcon size={16} />
                    </Link>
                  </div>
                </div>
              </section>
            )}

            {/* Section 2: Your Cases */}
            <section aria-labelledby="your-cases-title">
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "16px",
                }}
              >
                <h2
                  id="your-cases-title"
                  style={{
                    fontSize: "1.2rem",
                    fontWeight: 700,
                    color: "var(--text-primary, #17212B)",
                    margin: 0,
                  }}
                >
                  Your Cases
                </h2>
                <div style={{ display: "flex", gap: "12px" }}>
                  <button
                    onClick={() => setCreateModalOpen(true)}
                    className="btn btn-secondary"
                    style={{
                      padding: "7px 14px",
                      fontSize: "13px",
                      minHeight: "38px",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <PlusIcon size={14} />
                    <span>Start a case</span>
                  </button>
                  {cases.length > 2 && (
                    <Link
                      href="/cases"
                      className="btn btn-tertiary"
                      style={{ fontSize: "13px", padding: "6px 8px" }}
                    >
                      View all ({cases.length})
                    </Link>
                  )}
                </div>
              </div>

              {cases.length === 0 ? (
                <EmptyState
                  icon={<CaseIcon size={28} color="var(--navy-primary, #17324D)" />}
                  title="No cases yet"
                  description="Your cases will appear here once you create or join a case."
                  actionLabel="Start a case"
                  onAction={() => setCreateModalOpen(true)}
                />
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "18px" }}>
                  {cases.slice(0, 4).map((c) => {
                    const brief = briefsByCaseId[c.id];
                    const nextDateStr = brief?.next_hearing_date ? formatDateFull(brief.next_hearing_date) : null;
                    const lawyer = brief?.lead_counsel_name || null;
                    const courtInfo = brief?.next_hearing_court || (c.case_number ? `Case #${c.case_number}` : null);

                    return (
                      <CaseCard
                        key={c.id}
                        id={c.id}
                        title={c.title}
                        status={c.status}
                        courtName={courtInfo}
                        nextImportantDate={nextDateStr}
                        lawyerName={lawyer}
                        href={`/cases/${c.id}`}
                      />
                    );
                  })}
                </div>
              )}
            </section>

            {/* Grid with 2 columns: Upcoming Dates & Need Help */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "24px" }}>
              {/* Section 3: Upcoming Dates */}
              <section aria-labelledby="upcoming-title">
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "14px",
                  }}
                >
                  <h2
                    id="upcoming-title"
                    style={{
                      fontSize: "1.15rem",
                      fontWeight: 700,
                      color: "var(--text-primary, #17212B)",
                      margin: 0,
                    }}
                  >
                    Upcoming
                  </h2>
                  <Link
                    href="/calendar"
                    className="btn btn-tertiary"
                    style={{ fontSize: "13px", padding: "4px 8px" }}
                  >
                    View calendar
                  </Link>
                </div>

                <div
                  style={{
                    background: "var(--surface-card, #FFFFFF)",
                    border: "1px solid var(--border-subtle, #D9E2EC)",
                    borderRadius: "14px",
                    padding: "16px 20px",
                    boxShadow: "var(--shadow-sm)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "14px",
                  }}
                >
                  {upcomingEvents.length === 0 ? (
                    <div style={{ padding: "16px 0", textAlign: "center", color: "var(--text-muted, #7B8794)" }}>
                      <p style={{ margin: 0, fontSize: "14px" }}>No upcoming court dates or consultations.</p>
                    </div>
                  ) : (
                    upcomingEvents.map((ev, idx) => (
                      <Link
                        key={ev.id}
                        href={ev.href}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "10px 0",
                          borderBottom: idx < upcomingEvents.length - 1 ? "1px solid var(--border-subtle, #D9E2EC)" : "none",
                          textDecoration: "none",
                          color: "inherit",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                          <span
                            style={{
                              fontSize: "13px",
                              fontWeight: 700,
                              color: "var(--navy-primary, #17324D)",
                              width: "60px",
                              flexShrink: 0,
                            }}
                          >
                            {ev.dateShort}
                          </span>
                          <div>
                            <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-primary, #17212B)" }}>
                              {ev.title}
                            </div>
                            <div style={{ fontSize: "12px", color: "var(--text-secondary, #52606D)" }}>
                              {ev.subtitle}
                            </div>
                          </div>
                        </div>

                        <span style={{ color: "var(--text-muted, #7B8794)" }}>
                          <ArrowRightIcon size={14} />
                        </span>
                      </Link>
                    ))
                  )}
                </div>
              </section>

              {/* Section 4: Need Help? (Ask LCC) */}
              <section aria-labelledby="help-title">
                <div style={{ marginBottom: "14px" }}>
                  <h2
                    id="help-title"
                    style={{
                      fontSize: "1.15rem",
                      fontWeight: 700,
                      color: "var(--text-primary, #17212B)",
                      margin: 0,
                    }}
                  >
                    Need help?
                  </h2>
                </div>

                <div
                  style={{
                    background: "var(--surface-card, #FFFFFF)",
                    border: "1px solid var(--border-subtle, #D9E2EC)",
                    borderRadius: "14px",
                    padding: "20px 24px",
                    boxShadow: "var(--shadow-sm)",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    height: "calc(100% - 34px)",
                    boxSizing: "border-box",
                  }}
                >
                  <div>
                    <h3
                      style={{
                        margin: "0 0 6px 0",
                        fontSize: "1rem",
                        fontWeight: 600,
                        color: "var(--text-primary, #17212B)",
                      }}
                    >
                      Not sure what to do next?
                    </h3>
                    <p
                      style={{
                        margin: "0 0 18px 0",
                        fontSize: "0.875rem",
                        color: "var(--text-secondary, #52606D)",
                        lineHeight: 1.5,
                      }}
                    >
                      Lex can answer questions about your case documents, timelines, and court procedures in plain words.
                    </p>
                  </div>

                  <div>
                    <Link
                      href="/ai-advisor"
                      className="btn btn-secondary"
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "8px",
                        minHeight: "42px",
                        fontSize: "14px",
                        width: "100%",
                        justifyContent: "center",
                      }}
                    >
                      <AssistantIcon size={16} color="var(--navy-primary, #102A43)" />
                      <span>Lex</span>
                    </Link>
                  </div>
                </div>
              </section>
            </div>
          </div>
        )}
      </div>

      {/* Start Case Modal */}
      <Modal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Start a new matter"
        size="md"
      >
        <form onSubmit={handleCreateCase}>
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <p style={{ fontSize: "14px", color: "var(--text-secondary, #52606D)", margin: 0 }}>
              Tell us what this matter is about in plain words. You can add documents and invite your advocate anytime.
            </p>

            <div>
              <label
                style={{
                  display: "block",
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "var(--text-primary, #17212B)",
                  marginBottom: "6px",
                }}
              >
                What is this matter about? *
              </label>
              <Input
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g. Property dispute regarding ancestral land"
                required
              />
            </div>

            <div>
              <label
                style={{
                  display: "block",
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "var(--text-primary, #17212B)",
                  marginBottom: "6px",
                }}
              >
                Brief description (optional)
              </label>
              <Textarea
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Mention any notices received, police complaints, or court names if known."
                rows={3}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "12px" }}>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setCreateModalOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" variant="primary" isLoading={creating}>
                Create matter
              </Button>
            </div>
          </div>
        </form>
      </Modal>
    </div>
  );
}
