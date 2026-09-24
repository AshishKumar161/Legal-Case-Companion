"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { apiClient } from "@/api/client";
import styles from "./WhatChangedBanner.module.css";
import {
  BellIcon,
  CalendarIcon,
  CourthouseIcon,
  DocumentIcon,
  ChatIcon,
  LawyerIcon,
  ClockIcon,
  CheckCircleIcon,
  ArrowRightIcon,
  ScalesIcon,
} from "@/components/ui/Icons";

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

function cleanDescription(desc: string): string {
  if (!desc) return "";
  // Strip emojis and unneeded raw delimiters
  let text = desc.replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, "").trim();
  // Strip quotes wrapping around messages like '...'
  text = text.replace(/^['"]|['"]$/g, "").trim();
  // Format video call notifications cleanly
  if (text.toLowerCase().includes("video call started") || text.toLowerCase().includes("joined the video room")) {
    const match = text.match(/for case ['"]?([^'"]+)['"]?/i);
    const caseName = match ? match[1] : "matter";
    return `Live video consultation initiated for case '${caseName}'. Click below to join the room.`;
  }
  return text;
}

export function WhatChangedBanner() {
  const [data, setData] = useState<WhatChangedResponse | null>(null);
  const [acknowledging, setAcknowledging] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  const fetchChanges = useCallback(async () => {
    try {
      const res = (await apiClient.get("/api/v1/feed/what-changed?limit=8")) as WhatChangedResponse;
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

  // Deduplicate identical consecutive events (e.g. repeated ping webhooks)
  const events = data?.events;
  const displayEvents = useMemo(() => {
    if (!events) return [];
    const seen = new Set<string>();
    const unique: DeltaEvent[] = [];
    for (const ev of events) {
      const key = `${ev.category}-${ev.title}-${ev.description.slice(0, 40)}`;
      if (!seen.has(key)) {
        seen.add(key);
        unique.push(ev);
      }
    }
    return unique;
  }, [events]);

  if (dismissed || !data || !data.has_unacknowledged_changes || displayEvents.length === 0) {
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
        return <CalendarIcon size={16} color="#2563EB" />;
      case "COURT_TRACKING":
        return <CourthouseIcon size={16} color="#7C3AED" />;
      case "DOCUMENT":
      case "DOCUMENT_REQUEST":
        return <DocumentIcon size={16} color="#059669" />;
      case "COMMUNICATION":
        return <ChatIcon size={16} color="#D97706" />;
      case "CONSULTATION":
        return <LawyerIcon size={16} color="#2563EB" />;
      case "DEADLINE":
        return <ClockIcon size={16} color="#DC2626" />;
      default:
        return <ScalesIcon size={16} color="#475569" />;
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
          <div className={styles.sparkleIcon} aria-hidden="true">
            <BellIcon size={18} color="#2563eb" />
          </div>
          <div>
            <h3 className={styles.heading}>
              What changed since your last visit?
              <span className={styles.newBadge}>{data.total_new_changes} new</span>
            </h3>
            <p className={styles.subtext}>
              Real-time court updates, orders, evidence, and client messages since your last session.
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
          <CheckCircleIcon size={14} color="currentColor" />
          <span>{acknowledging ? "Acknowledging..." : "Mark All Seen"}</span>
        </button>
      </div>

      <div className={styles.eventList}>
        {displayEvents.map((ev) => (
          <div key={ev.id} className={styles.eventCard}>
            <div className={styles.eventLeft}>
              <div className={styles.eventIcon} aria-hidden="true">
                {getCategoryIcon(ev.category)}
              </div>
              <div className={styles.eventInfo}>
                <div className={styles.eventMetaRow}>
                  <span className={`${styles.categoryTag} ${getCategoryTagClass(ev.category)}`}>
                    {ev.category.replace(/_/g, " ")}
                  </span>
                  <span className={styles.provenanceBadge}>Source: {ev.provenance}</span>
                  <span className={styles.eventTime}>{formatEventTime(ev.timestamp)}</span>
                </div>
                <div className={styles.eventTitle}>{ev.title}</div>
                <div className={styles.eventDesc}>{cleanDescription(ev.description)}</div>
              </div>
            </div>

            <Link href={ev.source_url} className={styles.actionLink}>
              <span>Take Action</span>
              <ArrowRightIcon size={12} color="currentColor" />
            </Link>
          </div>
        ))}
      </div>
    </aside>
  );
}
