"use client";

import React, { useEffect, useState, useCallback } from "react";
import { apiClient } from "@/api/client";
import { NextStep, NextStepProps } from "@/components/NextStep";
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

      {/* 2. 6-Dimension Deterministic Attention Matrix */}
      <section className={styles.matrixCard} aria-label="Operational Case Attention Matrix">
        <div className={styles.matrixHeader}>
          <div className={styles.titleArea}>
            <span style={{ fontSize: "18px" }}>📊</span>
            <div>
              <span className={styles.kicker}>Deterministic Operational Status</span>
              <h3 className={styles.matrixTitle}>Case Health & Compliance Dimensions</h3>
            </div>
          </div>
          <span style={{ fontSize: "11px", color: "#64748b" }}>
            Last verified: {new Date(data.evaluated_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>

        <div className={styles.grid}>
          {/* Hearing */}
          <div className={styles.dimensionCard}>
            <div className={styles.dimTopRow}>
              <span className={styles.dimLabel}>📅 Hearing</span>
              <span className={`${styles.stateBadge} ${getBadgeClass(data.dimensions.hearing.state)}`}>
                {formatStateLabel(data.dimensions.hearing.state)}
              </span>
            </div>
            <p className={styles.dimReason}>{data.dimensions.hearing.reason}</p>
          </div>

          {/* Documents */}
          <div className={styles.dimensionCard}>
            <div className={styles.dimTopRow}>
              <span className={styles.dimLabel}>📄 Documents</span>
              <span className={`${styles.stateBadge} ${getBadgeClass(data.dimensions.documents.state)}`}>
                {formatStateLabel(data.dimensions.documents.state)}
              </span>
            </div>
            <p className={styles.dimReason}>{data.dimensions.documents.reason}</p>
          </div>

          {/* Tasks & Deadlines */}
          <div className={styles.dimensionCard}>
            <div className={styles.dimTopRow}>
              <span className={styles.dimLabel}>⏳ Tasks & Deadlines</span>
              <span className={`${styles.stateBadge} ${getBadgeClass(data.dimensions.tasks.state)}`}>
                {formatStateLabel(data.dimensions.tasks.state)}
              </span>
            </div>
            <p className={styles.dimReason}>{data.dimensions.tasks.reason}</p>
          </div>

          {/* Court Sync */}
          <div className={styles.dimensionCard}>
            <div className={styles.dimTopRow}>
              <span className={styles.dimLabel}>🏛️ Court Sync</span>
              <span className={`${styles.stateBadge} ${getBadgeClass(data.dimensions.court_sync.state)}`}>
                {formatStateLabel(data.dimensions.court_sync.state)}
              </span>
            </div>
            <p className={styles.dimReason}>{data.dimensions.court_sync.reason}</p>
          </div>

          {/* Communication */}
          <div className={styles.dimensionCard}>
            <div className={styles.dimTopRow}>
              <span className={styles.dimLabel}>💬 Communication</span>
              <span className={`${styles.stateBadge} ${getBadgeClass(data.dimensions.communication.state)}`}>
                {formatStateLabel(data.dimensions.communication.state)}
              </span>
            </div>
            <p className={styles.dimReason}>{data.dimensions.communication.reason}</p>
          </div>

          {/* Payment */}
          <div className={styles.dimensionCard}>
            <div className={styles.dimTopRow}>
              <span className={styles.dimLabel}>💳 Payment</span>
              <span className={`${styles.stateBadge} ${getBadgeClass(data.dimensions.payment.state)}`}>
                {formatStateLabel(data.dimensions.payment.state)}
              </span>
            </div>
            <p className={styles.dimReason}>{data.dimensions.payment.reason}</p>
          </div>
        </div>

        <div className={styles.footerDisclaimer}>
          <span>⚖️ Deterministic Evaluation · Zero AI Risk Scoring</span>
          <span>Status derived directly from statutory deadlines, court dockets, and verified evidence</span>
        </div>
      </section>
    </div>
  );
}
