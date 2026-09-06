"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/api/client";
import LegalTerm from "@/components/LegalTerm";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { trackFunnelEvent } from "@/lib/analytics";
import { CalendarEventItem, CalendarEventsResponse } from "@/types";
import styles from "./page.module.css";

type ViewTimeframe = "upcoming" | "today" | "this_week" | "later" | "all";
type EventTypeFilter = "all" | "hearing" | "limitation" | "consultation" | "task";
type PerspectiveView = "client" | "lawyer";

export default function CalendarPage() {
  const [viewTimeframe, setViewTimeframe] = useState<ViewTimeframe>("upcoming");
  const [typeFilter, setTypeFilter] = useState<EventTypeFilter>("all");
  const [perspective, setPerspective] = useState<PerspectiveView>("client");

  const [events, setEvents] = useState<CalendarEventItem[]>([]);
  const [nextAttention, setNextAttention] = useState<CalendarEventItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCalendarEvents = useCallback(
    async (timeframeParam: ViewTimeframe, typeParam: EventTypeFilter) => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        params.set("timeframe", timeframeParam);
        if (typeParam !== "all") params.set("event_type", typeParam);

        const data = (await apiClient.get(
          `/api/v1/calendar/events?${params.toString()}`
        )) as CalendarEventsResponse;

        setEvents(data.events || []);
        setNextAttention(data.next_attention_event || null);
      } catch (err: unknown) {
        const msg =
          err instanceof ApiError ? err.message : "Unable to retrieve calendar events.";
        setError(msg);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    fetchCalendarEvents(viewTimeframe, typeFilter);
  }, [fetchCalendarEvents, viewTimeframe, typeFilter]);

  const getTypeBadgeClass = (type: string) => {
    switch (type) {
      case "hearing":
        return styles.typeHearing;
      case "limitation":
        return styles.typeLimitation;
      case "consultation":
        return styles.typeConsultation;
      case "task":
        return styles.typeTask;
      default:
        return styles.typeHearing;
    }
  };

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div>
          <div className={styles.eyebrow}>
            <span>📅</span>
            <span>Indian Court Calendar & Deadlines</span>
          </div>
          <h1 className={styles.title}>Hearing & Limitation Center</h1>
          <p className={styles.subtitle}>
            Never miss a court date, limitation cutoff, or lawyer consultation. All events are explained in plain language with exact instructions on what you need to do.
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
          {/* View Perspective Toggle */}
          <div className={styles.viewToggle} role="group" aria-label="Perspective View">
            <button
              type="button"
              className={`${styles.viewToggleBtn} ${perspective === "client" ? styles.viewToggleBtnActive : ""}`}
              onClick={() => setPerspective("client")}
            >
              Client View
            </button>
            <button
              type="button"
              className={`${styles.viewToggleBtn} ${perspective === "lawyer" ? styles.viewToggleBtnActive : ""}`}
              onClick={() => setPerspective("lawyer")}
            >
              Advocate View
            </button>
          </div>

          <Link href="/court-tracking" className={styles.actionBtn} style={{ padding: "8px 16px" }}>
            🏛 Sync eCourts Registry
          </Link>
          <Link
            href="/cases/new"
            className={styles.actionBtn}
            style={{ padding: "8px 16px", background: "var(--accent-gradient, #6366f1)" }}
          >
            + New Legal Matter
          </Link>
        </div>
      </header>

      {/* UX North Star: Most Urgent Next Attention Banner */}
      {nextAttention && (
        <div className={styles.nextAttentionBanner}>
          <div>
            <div className={styles.bannerKicker}>
              <span>⚡</span> Urgent: Your Next Important Legal Date
            </div>
            <h2 className={styles.bannerTitle}>
              {nextAttention.type_label}: {nextAttention.title}
            </h2>
            <p className={styles.bannerDesc}>
              {nextAttention.time_display} · {nextAttention.forum} · <strong>{nextAttention.case_name}</strong> ({nextAttention.case_ref})
            </p>
            <div style={{ marginTop: "8px", fontSize: "13px", color: "#fca5a5" }}>
              <strong>What you need to do:</strong> {nextAttention.action_tip}
            </div>
          </div>

          <Link
            href={nextAttention.action_href}
            className={styles.bannerActionBtn}
            onClick={() => trackFunnelEvent("hearing_opened", { court_category: nextAttention.title })}
          >
            {nextAttention.action_label} →
          </Link>
        </div>
      )}

      {/* Navigation and Filters */}
      <div className={styles.controlsRow}>
        <div className={styles.viewTabs} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={viewTimeframe === "upcoming"}
            className={`${styles.tabBtn} ${viewTimeframe === "upcoming" ? styles.tabBtnActive : ""}`}
            onClick={() => setViewTimeframe("upcoming")}
          >
            All Upcoming
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewTimeframe === "today"}
            className={`${styles.tabBtn} ${viewTimeframe === "today" ? styles.tabBtnActive : ""}`}
            onClick={() => setViewTimeframe("today")}
          >
            Today
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewTimeframe === "this_week"}
            className={`${styles.tabBtn} ${viewTimeframe === "this_week" ? styles.tabBtnActive : ""}`}
            onClick={() => setViewTimeframe("this_week")}
          >
            This Week
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewTimeframe === "later"}
            className={`${styles.tabBtn} ${viewTimeframe === "later" ? styles.tabBtnActive : ""}`}
            onClick={() => setViewTimeframe("later")}
          >
            Later
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewTimeframe === "all"}
            className={`${styles.tabBtn} ${viewTimeframe === "all" ? styles.tabBtnActive : ""}`}
            onClick={() => setViewTimeframe("all")}
          >
            All Dates
          </button>
        </div>

        <div className={styles.filterGroup}>
          <label htmlFor="eventTypeSelect" style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
            Event Type:
          </label>
          <select
            id="eventTypeSelect"
            className={styles.filterSelect}
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as EventTypeFilter)}
          >
            <option value="all">All Event Categories</option>
            <option value="hearing">Court Hearings Only</option>
            <option value="limitation">Statutory Limitations Only</option>
            <option value="consultation">Lawyer Consultations Only</option>
            <option value="task">Chamber Tasks Only</option>
          </select>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div
          style={{
            background: "rgba(239, 68, 68, 0.12)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#fca5a5",
            padding: "12px 16px",
            borderRadius: "8px",
            marginBottom: "20px",
            fontSize: "13px",
          }}
        >
          {error}
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <LoadingSkeleton type="card" count={3} />
        </div>
      )}

      {/* Empty State */}
      {!loading && events.length === 0 && (
        <div className={styles.emptyCalendar}>
          <div className={styles.emptyCalendarIcon}>📅</div>
          <h2 className={styles.emptyCalendarTitle}>No legal events scheduled for this timeframe.</h2>
          <p className={styles.emptyCalendarDesc}>
            You have no upcoming court hearings, statutory limitation cutoffs, or consultations matching the selected filters.
          </p>
          <div style={{ display: "flex", justifyContent: "center", gap: "10px" }}>
            <button
              type="button"
              className={styles.actionBtn}
              onClick={() => {
                setViewTimeframe("all");
                setTypeFilter("all");
              }}
            >
              Show All Dates
            </button>
            <Link href="/court-tracking" className={styles.actionBtn} style={{ background: "var(--accent-gradient)" }}>
              Find & Track a Court Case
            </Link>
          </div>
        </div>
      )}

      {/* Events Feed */}
      {!loading && events.length > 0 && (
        <div className={styles.eventList}>
          {events.map((evt) => (
            <div key={evt.id} className={styles.eventCard}>
              {/* Date Box */}
              <div className={styles.dateBadge}>
                <span className={styles.dateMonth}>{evt.month}</span>
                <span className={styles.dateDay}>{evt.day}</span>
                <span className={styles.dateTime}>
                  {new Date(evt.scheduled_at).toLocaleTimeString("en-IN", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>

              {/* Event Body */}
              <div className={styles.eventBody}>
                <div className={styles.eventTopRow}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                    <span className={`${styles.typeBadge} ${getTypeBadgeClass(evt.type)}`}>
                      {evt.type_label}
                    </span>
                    {evt.technical_term && (
                      <LegalTerm term={evt.technical_term} source={evt.source} />
                    )}
                    {evt.is_urgent && (
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: 700,
                          color: "#f87171",
                          background: "rgba(239, 68, 68, 0.15)",
                          padding: "2px 6px",
                          borderRadius: "4px",
                          textTransform: "uppercase",
                        }}
                      >
                        ⚡ Action Required Soon
                      </span>
                    )}
                  </div>

                  <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                    {evt.time_display}
                  </span>
                </div>

                <h3 className={styles.eventTitle}>{evt.title}</h3>
                <div className={styles.caseName}>
                  {evt.case_name} · <strong>{evt.case_ref}</strong> · {evt.forum}
                </div>

                {/* Perspective 1: Client View */}
                {perspective === "client" && (
                  <div className={styles.actionTipBox}>
                    <strong style={{ display: "block", marginBottom: "3px", color: "#f8fafc" }}>
                      What should I know?
                    </strong>
                    {evt.action_tip}
                  </div>
                )}

                {/* Perspective 2: Lawyer View */}
                {perspective === "lawyer" && evt.lawyer_details && (
                  <div className={styles.lawyerDetailsGrid}>
                    {evt.lawyer_details.court && (
                      <div className={styles.lawyerDetailItem}>
                        <span>Court Forum</span>
                        <strong>{evt.lawyer_details.court}</strong>
                      </div>
                    )}
                    {evt.lawyer_details.court_room && (
                      <div className={styles.lawyerDetailItem}>
                        <span>Room & Item</span>
                        <strong>{evt.lawyer_details.court_room} ({evt.lawyer_details.item_number || "Board"})</strong>
                      </div>
                    )}
                    {evt.lawyer_details.bench && (
                      <div className={styles.lawyerDetailItem}>
                        <span>Bench / Coram</span>
                        <strong>{evt.lawyer_details.bench}</strong>
                      </div>
                    )}
                    {evt.lawyer_details.status && (
                      <div className={styles.lawyerDetailItem}>
                        <span>Listing Status</span>
                        <strong>{evt.lawyer_details.status}</strong>
                      </div>
                    )}
                    {evt.lawyer_details.petitioner_advocate && (
                      <div className={styles.lawyerDetailItem}>
                        <span>Counsel on Record</span>
                        <strong>{evt.lawyer_details.petitioner_advocate}</strong>
                      </div>
                    )}
                  </div>
                )}

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginTop: "12px",
                    flexWrap: "wrap",
                    gap: "8px",
                  }}
                >
                  <div className={styles.provenanceLine}>
                    <span>Source: {evt.source}</span>
                  </div>

                  <div style={{ display: "flex", gap: "8px" }}>
                    {evt.case_id && (
                      <Link
                        href={`/cases/${evt.case_id}`}
                        className={styles.actionBtn}
                      >
                        View Matter Workspace
                      </Link>
                    )}
                    <Link
                      href={evt.action_href}
                      className={styles.actionBtn}
                      style={{ background: "rgba(99, 102, 241, 0.2)", borderColor: "rgba(99, 102, 241, 0.4)" }}
                      onClick={() => trackFunnelEvent("hearing_opened", { court_category: evt.title })}
                    >
                      {evt.action_label} →
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
