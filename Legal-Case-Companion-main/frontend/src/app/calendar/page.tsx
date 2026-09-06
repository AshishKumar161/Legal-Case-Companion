"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/api/client";
import { CalendarEventItem, CalendarEventsResponse, CaseItem } from "@/types";
import {
  CalendarIcon,
  CourthouseIcon,
  CheckCircleIcon,
  AssistantIcon,
  ArrowRightIcon,
} from "@/components/ui/Icons";
import styles from "./page.module.css";

function formatDateParts(dateString?: string | null): { dateStr: string; timeStr: string } {
  if (!dateString) return { dateStr: "Not scheduled", timeStr: "Time TBA" };
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return { dateStr: "Not scheduled", timeStr: "Time TBA" };
    const dateStr = d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
    const timeStr = d.toLocaleTimeString("en-IN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
    return { dateStr, timeStr };
  } catch {
    return { dateStr: "Not scheduled", timeStr: "Time TBA" };
  }
}

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEventItem[]>([]);
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // "Ask LCC" Guidance Modal State (Section 10)
  const [askLccEvent, setAskLccEvent] = useState<CalendarEventItem | null>(null);

  const fetchCalendarEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [calData, casesData] = await Promise.all([
        apiClient.get<CalendarEventsResponse>("/api/v1/calendar/events?timeframe=upcoming"),
        apiClient.get<any>("/api/v1/cases").catch(() => []),
      ]);

      const casesList: CaseItem[] = Array.isArray(casesData)
        ? casesData
        : casesData?.items || [];
      setCases(casesList);

      const allEvents = calData?.events || [];
      // Filter primarily for hearings and court listings
      const hearingEvents = allEvents.filter(
        (e) => e.type === "hearing" || e.type === "limitation"
      );
      setEvents(hearingEvents.length > 0 ? hearingEvents : allEvents);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiError ? err.message : "Unable to retrieve upcoming hearings.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchCalendarEvents();
  }, [fetchCalendarEvents]);

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <h1 className={styles.title}>Upcoming Hearings</h1>
        <p className={styles.subtitle}>
          Know when you need to be in court, where to go, and what to bring.
        </p>
      </div>

      {loading ? (
        <div style={{ padding: "60px 0", textAlign: "center", color: "var(--text-secondary)" }}>
          Loading your hearing schedule...
        </div>
      ) : error ? (
        <div style={{ padding: "20px", background: "rgba(220, 38, 38, 0.08)", color: "var(--status-urgent)", borderRadius: "8px" }}>
          {error}
        </div>
      ) : events.length === 0 ? (
        /* Empty State */
        <div className={styles.emptyContainer}>
          <div className={styles.emptyIcon}>
            <CalendarIcon size={28} />
          </div>
          <h3 className={styles.emptyTitle}>No hearings currently scheduled</h3>
          <p className={styles.emptyDesc}>
            When a court date is assigned by the judge or entered by your lawyer, it will appear here with step-by-step preparation instructions.
          </p>
          <Link href="/dashboard" className="btn btn-primary">
            Return to Dashboard
          </Link>
        </div>
      ) : (
        /* Action-Oriented Hearings List (Section 10) */
        <div className={styles.hearingList}>
          {events.map((ev) => {
            const eventDate = ev.scheduled_at || ev.start_at || "";
            const { dateStr, timeStr } = formatDateParts(eventDate);
            const associatedCase = cases.find((c) => c.id === ev.case_id);
            const caseTitle = associatedCase?.title || ev.case_name || ev.title;
            const courtRoom = ev.lawyer_details?.court_room;

            // Calculate urgency (within 7 days)
            const isUrgent =
              ev.is_urgent ||
              (eventDate &&
              new Date(eventDate).getTime() - new Date().getTime() <= 7 * 24 * 60 * 60 * 1000 &&
              new Date(eventDate).getTime() >= new Date().getTime());

            return (
              <div
                key={ev.id}
                className={`${styles.hearingCard} ${isUrgent ? styles.hearingCardUrgent : ""}`}
              >
                <div className={styles.cardTopRow}>
                  <span className={`${styles.badge} ${isUrgent ? styles.badgeUrgent : styles.badgeNormal}`}>
                    {isUrgent ? "Upcoming Hearing · Due Soon" : "Scheduled Court Hearing"}
                  </span>
                  {courtRoom && (
                    <span style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 600 }}>
                      Courtroom: <strong>{courtRoom}</strong>
                    </span>
                  )}
                </div>

                <div className={styles.cardMainGrid}>
                  {/* WHEN & WHERE & WHY */}
                  <div className={styles.dateTimeLocation}>
                    <div className={styles.dateRow}>
                      <CalendarIcon size={22} color="var(--navy-primary)" />
                      <span>{dateStr}</span>
                    </div>

                    <div className={styles.timeRow}>
                      <span>⏰ {ev.time_display || timeStr}</span>
                    </div>

                    <div className={styles.locationRow}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <CourthouseIcon size={16} color="var(--navy-secondary)" />
                        <strong>{ev.forum || ev.lawyer_details?.court || "District Court Complex"}</strong>
                      </div>
                      {(ev.action_tip || ev.technical_term) && (
                        <div style={{ marginTop: "4px", fontSize: "13px", color: "var(--text-secondary)" }}>
                          Purpose: {ev.action_tip || ev.technical_term}
                        </div>
                      )}
                    </div>

                    <div className={styles.caseTitleTag}>
                      Case: <strong>{caseTitle}</strong>
                    </div>
                  </div>

                  {/* WHAT YOU NEED TO DO (Section 10) */}
                  <div className={styles.checklistCard}>
                    <div className={styles.checklistHeading}>What you need to know</div>
                    <div className={styles.checkItem}>
                      <span className={styles.checkIcon}>✓</span>
                      <span>Bring your physical Government Photo ID (Aadhaar / PAN / Voter ID)</span>
                    </div>
                    <div className={styles.checkItem}>
                      <span className={styles.checkIcon}>✓</span>
                      <span>Bring requested case documents and agreement copies</span>
                    </div>
                    <div className={styles.checkItem}>
                      <span className={styles.checkIcon}>✓</span>
                      <span>Speak with your lawyer beforehand to confirm courtroom number</span>
                    </div>
                  </div>
                </div>

                {/* Actions: [ View Details ] and [ Ask LCC ] (Section 10) */}
                <div className={styles.cardActions}>
                  {ev.case_id ? (
                    <Link
                      href={`/cases/${ev.case_id}?tab=hearings`}
                      className={styles.actionBtnPrimary}
                    >
                      <span>View Details</span>
                      <ArrowRightIcon size={14} />
                    </Link>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => setAskLccEvent(ev)}
                    className={styles.actionBtnSecondary}
                  >
                    <AssistantIcon size={16} color="var(--accent-gold)" />
                    <span>Ask LCC Legal Assistant</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Ask LCC Guidance Modal (Section 10) */}
      {askLccEvent && (
        <div className={styles.modalBackdrop} onClick={() => setAskLccEvent(null)}>
          <div className={styles.modalBox} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div>
                <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--accent-gold)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "4px" }}>
                  ⚖ Hearing Preparation Guide
                </div>
                <h3 className={styles.modalTitle}>What to Expect at Your Hearing</h3>
              </div>
              <button
                onClick={() => setAskLccEvent(null)}
                className={styles.closeBtn}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "14px", fontSize: "14px", color: "var(--text-secondary)", lineHeight: "1.55" }}>
              <div>
                <strong style={{ color: "var(--navy-primary)" }}>1. What happens at this hearing?</strong>
                <p style={{ marginTop: "4px" }}>
                  The judge will take up listed matters by sequence. Your advocate will stand when your item is called and present the status or arguments.
                </p>
              </div>

              <div>
                <strong style={{ color: "var(--navy-primary)" }}>2. Do I need to speak?</strong>
                <p style={{ marginTop: "4px" }}>
                  Usually, you do not need to address the court directly unless specifically asked by the judge. Your lawyer represents and speaks for you.
                </p>
              </div>

              <div>
                <strong style={{ color: "var(--navy-primary)" }}>3. What should I ask my lawyer?</strong>
                <ul style={{ paddingLeft: "20px", marginTop: "4px" }}>
                  <li>&ldquo;What is the realistic outcome expected on this date?&rdquo;</li>
                  <li>&ldquo;Are we seeking an order or an adjournment for filing documents?&rdquo;</li>
                  <li>&ldquo;Do you have all original copies ready for inspection?&rdquo;</li>
                </ul>
              </div>

              <div style={{ marginTop: "10px", padding: "12px", background: "var(--surface-subtle)", borderRadius: "8px", fontSize: "12px", color: "var(--text-muted)" }}>
                Note: LCC provides procedural guidance to help you stay calm and organized. For advice on specific case strategies, consult your assigned advocate.
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "20px" }}>
              <button
                onClick={() => setAskLccEvent(null)}
                className="btn btn-primary"
              >
                Close Guidance
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
