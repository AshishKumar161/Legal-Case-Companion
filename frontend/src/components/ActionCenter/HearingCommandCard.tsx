"use client";

import React, { useState } from "react";
import { CaseHearingItem } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { apiClient } from "@/api/client";

interface HearingCommandCardProps {
  hearing: CaseHearingItem;
  caseId: string;
  onRefresh: () => void;
  onCreatePrepTask: (hearing: CaseHearingItem) => void;
}

export function HearingCommandCard({
  hearing,
  caseId,
  onRefresh,
  onCreatePrepTask,
}: HearingCommandCardProps) {
  const [confirming, setConfirming] = useState(false);

  const hearingDate = new Date(hearing.hearing_at);
  const now = new Date();
  const diffTime = hearingDate.getTime() - now.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  const isImminent = diffDays >= 0 && diffDays <= 7;
  const isPast = diffDays < 0;

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/hearings/${hearing.id}/confirm`, {});
      onRefresh();
    } catch (err) {
      console.error("Hearing confirmation error:", err);
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div
      style={{
        padding: "18px 20px",
        borderRadius: "var(--radius-md)",
        background: isImminent ? "rgba(239, 68, 68, 0.05)" : "var(--surface-card)",
        border: isImminent ? "1px solid rgba(239, 68, 68, 0.3)" : "1px solid var(--border-subtle)",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "10px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
            <span style={{ fontSize: "14px" }}>⚖</span>
            <h4 style={{ fontSize: "16px", fontWeight: 700, color: "#fff" }}>
              {hearing.court_name}
            </h4>
            <StatusBadge status={hearing.status} />
            {!hearing.is_confirmed && (
              <span
                style={{
                  fontSize: "10px",
                  fontWeight: 700,
                  padding: "2px 6px",
                  borderRadius: "4px",
                  background: "rgba(245, 158, 11, 0.15)",
                  color: "#f59e0b",
                  border: "1px solid rgba(245, 158, 11, 0.3)",
                }}
              >
                Suggested Listing (Unconfirmed)
              </span>
            )}
          </div>
          {hearing.bench_or_coram && (
            <div style={{ fontSize: "12px", color: "var(--accent-secondary)" }}>
              Coram / Bench: {hearing.bench_or_coram}
            </div>
          )}
        </div>

        {/* Countdown Badge */}
        <div style={{ textAlign: "right" }}>
          <div
            style={{
              fontSize: "13px",
              fontWeight: 700,
              color: isPast ? "var(--text-muted)" : isImminent ? "#ef4444" : "#60a5fa",
            }}
          >
            {isPast
              ? "Past Listing"
              : diffDays === 0
              ? "TODAY"
              : diffDays === 1
              ? "TOMORROW"
              : `In ${diffDays} days`}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
            {hearingDate.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" })}
            {" • "}
            {hearingDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </div>
        </div>
      </div>

      {/* Purpose & Notes */}
      <div style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: 1.5 }}>
        <span style={{ color: "var(--text-muted)" }}>Purpose of Listing: </span>
        {hearing.purpose}
      </div>

      {hearing.notes && (
        <div
          style={{
            padding: "8px 12px",
            borderRadius: "4px",
            background: "var(--surface-subtle)",
            fontSize: "12px",
            color: "var(--text-secondary)",
          }}
        >
          {hearing.notes}
        </div>
      )}

      {/* Operational Actions */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderTop: "1px solid var(--border-subtle)",
          paddingTop: "12px",
          marginTop: "4px",
          flexWrap: "wrap",
          gap: "8px",
        }}
      >
        <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
          Source: {hearing.source_type || "MANUAL"}
        </div>

        <div style={{ display: "flex", gap: "8px" }}>
          {!hearing.is_confirmed && (
            <button
              onClick={handleConfirm}
              disabled={confirming}
              className="btn btn-secondary"
              style={{ fontSize: "11px", padding: "4px 10px" }}
            >
              {confirming ? "Confirming..." : "✓ Confirm Listing"}
            </button>
          )}

          <button
            onClick={() => onCreatePrepTask(hearing)}
            className="btn btn-primary"
            style={{ fontSize: "11px", padding: "4px 10px" }}
          >
            + Create Preparation Task
          </button>
        </div>
      </div>
    </div>
  );
}
