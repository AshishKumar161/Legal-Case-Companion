"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { apiClient } from "@/api/client";
import styles from "./WhatChangedBanner.module.css";

interface DeltaEvent {
  id: string;
  event_type: string;
  category: string;
  title: string;
  description: string;
  source_url: string;
  provenance: string;
  timestamp: string;
  entity_id?: string;
  case_id?: string;
}

interface WhatChangedResponse {
  since: string;
  total_new_changes: number;
  events: DeltaEvent[];
  has_unacknowledged_changes: boolean;
}

export function WhatChangedBanner() {
  const [data, setData] = useState<WhatChangedResponse | null>(null);
  const [acknowledging, setAcknowledging] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const fetchChanges = useCallback(async () => {
    try {
      const res = (await apiClient.get("/api/v1/feed/what-changed?limit=5")) as WhatChangedResponse;
      setData(res);
    } catch {
      // Graceful degradation if feed is temporarily unreachable
      setData(null);
    }
  }, []);

  useEffect(() => {
    void fetchChanges();
  }, [fetchChanges]);

  const handleAcknowledge = async () => {
    setAcknowledging(true);
    try {
      await apiClient.post("/api/v1/feed/what-changed/acknowledge", {});
      setDismissed(true);
    } catch {
      // fallback to optimistic dismissal
      setDismissed(true);
    } finally {
      setAcknowledging(false);
    }
  };

  if (dismissed || !data || !data.has_unacknowledged_changes || data.events.length === 0) {
    return null;
  }

  const getCategoryTagClass = (category: string) => {
    switch (category) {
      case "HEARING":
        return styles.tagHearing;
      case "COURT_TRACKING":
        return styles.tagCourt;
      case "DOCUMENT":
      case "DOCUMENT_REQUEST":
        return styles.tagDocument;
      case "COMMUNICATION":
        return styles.tagMessage;
      default:
        return styles.tagGeneral;
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "HEARING":
        return "📅";
      case "COURT_TRACKING":
        return "🏛️";
      case "DOCUMENT":
      case "DOCUMENT_REQUEST":
        return "📄";
      case "COMMUNICATION":
        return "💬";
      case "CONSULTATION":
        return "🧑‍⚖️";
      case "DEADLINE":
        return "⏳";
      default:
        return "⚡";
    }
  };

  const formatEventTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  };

  return (
    <aside className={styles.bannerContainer} aria-label="What changed since your last visit">
      <div className={styles.headerRow}>
        <div className={styles.titleArea}>
          <span className={styles.sparkleIcon} aria-hidden="true">🔔</span>
          <div>
            <h3 className={styles.heading}>
              What changed since your last visit?
              <span className={styles.newBadge}>{data.total_new_changes} new</span>
            </h3>
            <p className={styles.subtext}>
              Real-time court updates, orders, evidence, and messages since your last session.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleAcknowledge}
          disabled={acknowledging}
          className={styles.ackButton}
          title="Mark all as seen"
        >
          {acknowledging ? "Acknowledging..." : "✓ Mark All Seen"}
        </button>
      </div>

      <div className={styles.eventList}>
        {data.events.map((ev) => (
          <div key={ev.id} className={styles.eventCard}>
            <div className={styles.eventLeft}>
              <span className={styles.eventIcon} aria-hidden="true">
                {getCategoryIcon(ev.category)}
              </span>
              <div className={styles.eventInfo}>
                <div className={styles.eventMetaRow}>
                  <span className={`${styles.categoryTag} ${getCategoryTagClass(ev.category)}`}>
                    {ev.category.replace(/_/g, " ")}
                  </span>
                  <span className={styles.provenanceBadge}>Source: {ev.provenance}</span>
                  <span className={styles.eventTime}>{formatEventTime(ev.timestamp)}</span>
                </div>
                <div className={styles.eventTitle}>{ev.title}</div>
                <div className={styles.eventDesc}>{ev.description}</div>
              </div>
            </div>

            <Link href={ev.source_url} className={styles.actionLink}>
              Take Action →
            </Link>
          </div>
        ))}
      </div>
    </aside>
  );
}
