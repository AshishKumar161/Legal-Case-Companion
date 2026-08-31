"use client";

import React from "react";
import { MatterBriefItem } from "@/types";

interface MatterBriefCardProps {
  brief: MatterBriefItem | null;
  loading?: boolean;
}

export function MatterBriefCard({ brief, loading }: MatterBriefCardProps) {
  if (loading || !brief) {
    return (
      <div
        style={{
          background: "var(--surface-card)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
          padding: "20px",
          color: "var(--text-muted)",
          fontSize: "13px",
        }}
      >
        Loading matter brief...
      </div>
    );
  }

  const daysToHearing = brief.next_hearing_date
    ? Math.ceil((new Date(brief.next_hearing_date).getTime() - new Date().setHours(0, 0, 0, 0)) / (1000 * 60 * 60 * 24))
    : null;

  return (
    <div
      style={{
        background: "linear-gradient(135deg, rgba(17, 24, 39, 0.95), rgba(15, 23, 42, 0.98))",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-md)",
        padding: "22px 24px",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        boxShadow: "var(--shadow-md)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
            <span
              style={{
                fontSize: "11px",
                fontWeight: 700,
                padding: "2px 8px",
                borderRadius: "4px",
                background: "rgba(59, 130, 246, 0.15)",
                color: "#60a5fa",
                letterSpacing: "0.05em",
              }}
            >
              MATTER BRIEF
            </span>
            <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              Initiated {new Date(brief.created_at).toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" })}
            </span>
          </div>
          <h2 style={{ fontSize: "20px", fontWeight: 700, color: "#fff", margin: 0 }}>
            {brief.title}
          </h2>
          <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "4px" }}>
            Lead Counsel: <strong style={{ color: "#e2e8f0" }}>{brief.lead_counsel_name || "Unassigned"}</strong> • Status:{" "}
            <span style={{ color: brief.status === "OPEN" ? "#10b981" : "#f59e0b", fontWeight: 600 }}>{brief.status}</span>
          </p>
        </div>

        {brief.next_hearing_date && daysToHearing !== null && (
          <div
            style={{
              padding: "10px 16px",
              borderRadius: "8px",
              background: daysToHearing <= 7 ? "rgba(239, 68, 68, 0.12)" : "rgba(59, 130, 246, 0.12)",
              border: daysToHearing <= 7 ? "1px solid rgba(239, 68, 68, 0.3)" : "1px solid rgba(59, 130, 246, 0.3)",
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-end",
            }}
          >
            <span style={{ fontSize: "11px", fontWeight: 700, color: daysToHearing <= 7 ? "#ef4444" : "#60a5fa" }}>
              {daysToHearing === 0 ? "LISTED TODAY" : `COURT LISTING IN ${daysToHearing} DAYS`}
            </span>
            <span style={{ fontSize: "12px", color: "#e2e8f0", marginTop: "2px" }}>
              {brief.next_hearing_court || "Presiding Court"}
            </span>
          </div>
        )}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
          gap: "12px",
          paddingTop: "14px",
          borderTop: "1px solid rgba(255, 255, 255, 0.07)",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Participants</span>
          <span style={{ fontSize: "18px", fontWeight: 700, color: "#fff" }}>{brief.participants_count}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Open Requests</span>
          <span style={{ fontSize: "18px", fontWeight: 700, color: brief.open_requests_count > 0 ? "#f59e0b" : "#10b981" }}>
            {brief.open_requests_count}
          </span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Evidence Records</span>
          <span style={{ fontSize: "18px", fontWeight: 700, color: "#fff" }}>{brief.recent_documents_count}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>Active Tasks</span>
          <span style={{ fontSize: "18px", fontWeight: 700, color: "#fff" }}>{brief.pending_tasks_count}</span>
        </div>
      </div>
    </div>
  );
}
