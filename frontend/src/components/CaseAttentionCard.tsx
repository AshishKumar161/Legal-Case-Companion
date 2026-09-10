"use client";

import React, { useEffect, useState, useCallback } from "react";
import { apiClient } from "@/api/client";
import { NextStep, NextStepProps } from "@/components/NextStep";
import {
  CalendarIcon,
  DocumentIcon,
  ClockIcon,
  CourthouseIcon,
  ChatIcon,
  ShieldIcon,
} from "@/components/ui/Icons";
import styles from "./CaseAttentionCard.module.css";

interface AttentionDimension {
  state: string;
  reason: string;
  data?: any;
}

interface CaseAttentionResponse {
  case_id: string;
  case_title: string;
  evaluated_at: string;
  dimensions: {
    hearing: AttentionDimension;
    documents: AttentionDimension;
    tasks: AttentionDimension;
    court_sync: AttentionDimension;
    communication: AttentionDimension;
    payment: AttentionDimension;
  };
  next_step: NextStepProps;
}

interface CaseAttentionCardProps {
  caseId: string;
}

export function CaseAttentionCard({ caseId }: CaseAttentionCardProps) {
  const [data, setData] = useState<CaseAttentionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDetailedDimensions, setShowDetailedDimensions] = useState(false);

  const fetchAttention = useCallback(async () => {
    try {
      const res = (await apiClient.get(`/api/v1/cases/${caseId}/attention`)) as CaseAttentionResponse;
      setData(res);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void fetchAttention();
  }, [fetchAttention]);

  if (loading || !data) {
    return null;
  }

  const getBadgeClass = (state: string) => {
    switch (state) {
      case "COMPLETE":
      case "UP_TO_DATE":
      case "CURRENT":
      case "NO_ACTION":
      case "PAID":
        return styles.badgeSuccess;
      case "UPCOMING":
      case "PENDING":
      case "STALE":
      case "REPLY_NEEDED":
        return styles.badgeWarning;
      case "URGENT":
      case "OVERDUE":
      case "FAILED":
        return styles.badgeDanger;
      default:
        return styles.badgeNeutral;
    }
  };

  const formatStateLabel = (state: string) => {
    return state.replace(/_/g, " ");
  };

  return (
    <div className={styles.container}>
      {/* 1. NextStep synthesized action item */}
      {data.next_step && (
        <NextStep
          context={data.next_step.context}
          headline={data.next_step.headline}
          detail={data.next_step.detail}
          provenance={data.next_step.provenance}
          action={data.next_step.action}
          urgency={data.next_step.urgency}
        />
      )}

      {/* 2. Progressive Disclosure for Detailed Dimensions */}
      <div>
        <button
          type="button"
          onClick={() => setShowDetailedDimensions((prev) => !prev)}
          className={styles.detailsToggleBtn}
        >
          <span>{showDetailedDimensions ? "▲ Hide Case Health Overview" : "▼ View Case Health Overview"}</span>
        </button>

        {showDetailedDimensions && (
          <section className={styles.matrixCard} aria-label="Case Status Dimensions">
            <div className={styles.matrixHeader}>
              <div className={styles.titleArea}>
                <div>
                  <span className={styles.kicker}>Status Overview</span>
                  <h3 className={styles.matrixTitle}>Case Health & Activity Status</h3>
                </div>
              </div>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                Verified: {new Date(data.evaluated_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>

            <div className={styles.grid}>
              {/* Hearing */}
              <div className={styles.dimensionCard}>
                <div className={styles.dimTopRow}>
                  <span className={styles.dimLabel}>
                    <CalendarIcon size={14} color="var(--navy-primary)" />
                    <span>Hearing</span>
                  </span>
                  <span className={`${styles.stateBadge} ${getBadgeClass(data.dimensions.hearing.state)}`}>
                    {formatStateLabel(data.dimensions.hearing.state)}
                  </span>
                </div>
                <p className={styles.dimReason}>{data.dimensions.hearing.reason}</p>
              </div>

              {/* Documents */}
              <div className={styles.dimensionCard}>
                <div className={styles.dimTopRow}>
                  <span className={styles.dimLabel}>
                    <DocumentIcon size={14} color="var(--navy-primary)" />
                    <span>Documents</span>
                  </span>
                  <span className={`${styles.stateBadge} ${getBadgeClass(data.dimensions.documents.state)}`}>
                    {formatStateLabel(data.dimensions.documents.state)}
                  </span>
                </div>
                <p className={styles.dimReason}>{data.dimensions.documents.reason}</p>
              </div>

              {/* Tasks & Deadlines */}
              <div className={styles.dimensionCard}>
                <div className={styles.dimTopRow}>
                  <span className={styles.dimLabel}>
                    <ClockIcon size={14} color="var(--navy-primary)" />
                    <span>Deadlines</span>
                  </span>
                  <span className={`${styles.stateBadge} ${getBadgeClass(data.dimensions.tasks.state)}`}>
                    {formatStateLabel(data.dimensions.tasks.state)}
                  </span>
                </div>
                <p className={styles.dimReason}>{data.dimensions.tasks.reason}</p>
              </div>

              {/* Court Sync */}
              <div className={styles.dimensionCard}>
                <div className={styles.dimTopRow}>
                  <span className={styles.dimLabel}>
                    <CourthouseIcon size={14} color="var(--navy-primary)" />
                    <span>Court Sync</span>
                  </span>
                  <span className={`${styles.stateBadge} ${getBadgeClass(data.dimensions.court_sync.state)}`}>
                    {formatStateLabel(data.dimensions.court_sync.state)}
                  </span>
                </div>
                <p className={styles.dimReason}>{data.dimensions.court_sync.reason}</p>
              </div>

              {/* Communication */}
              <div className={styles.dimensionCard}>
                <div className={styles.dimTopRow}>
                  <span className={styles.dimLabel}>
                    <ChatIcon size={14} color="var(--navy-primary)" />
                    <span>Lawyer Chat</span>
                  </span>
                  <span className={`${styles.stateBadge} ${getBadgeClass(data.dimensions.communication.state)}`}>
                    {formatStateLabel(data.dimensions.communication.state)}
                  </span>
                </div>
                <p className={styles.dimReason}>{data.dimensions.communication.reason}</p>
              </div>

              {/* Security / Protection */}
              <div className={styles.dimensionCard}>
                <div className={styles.dimTopRow}>
                  <span className={styles.dimLabel}>
                    <ShieldIcon size={14} color="var(--navy-primary)" />
                    <span>Security</span>
                  </span>
                  <span className={`${styles.stateBadge} ${styles.badgeSuccess}`}>
                    Protected
                  </span>
                </div>
                <p className={styles.dimReason}>Your documents and case information are protected.</p>
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
