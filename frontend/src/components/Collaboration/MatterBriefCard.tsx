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
        background: "var(--surface-card, #ffffff)",
        border: "1px solid var(--border-subtle, #e2e8f0)",
        borderRadius: "12px",
        padding: "22px 24px",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
            <span
              style={{
                fontSize: "11px",
                fontWeight: 700,
                padding: "2px 8px",
                borderRadius: "4px",
                background: "#eff6ff",
                color: "#1d4ed8",
                border: "1px solid #bfdbfe",
                letterSpacing: "0.05em",
              }}
            >
              MATTER BRIEF
            </span>
            <span style={{ fontSize: "12px", color: "#64748b" }}>
              Initiated {new Date(brief.created_at).toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" })}
            </span>
          </div>
          <h2 style={{ fontSize: "20px", fontWeight: 700, color: "#0f172a", margin: 0 }}>
            {brief.title}
          </h2>
          <p style={{ fontSize: "13px", color: "#475569", marginTop: "4px" }}>
            Lead Counsel: <strong style={{ color: "#0f172a" }}>{brief.lead_counsel_name || "Unassigned"}</strong> • Status:{" "}
            <span style={{ color: brief.status === "OPEN" ? "#059669" : "#d97706", fontWeight: 600 }}>{brief.status}</span>
          </p>
        </div>

        {brief.next_hearing_date && daysToHearing !== null && (
          <div
            style={{
              padding: "10px 16px",
              borderRadius: "8px",
              background: daysToHearing <= 7 ? "#fef2f2" : "#eff6ff",
              border: daysToHearing <= 7 ? "1px solid #fecaca" : "1px solid #bfdbfe",
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-end",
            }}
          >
            <span style={{ fontSize: "11px", fontWeight: 700, color: daysToHearing <= 7 ? "#dc2626" : "#1d4ed8" }}>
              {daysToHearing === 0 ? "LISTED TODAY" : `COURT LISTING IN ${daysToHearing} DAYS`}
            </span>
            <span style={{ fontSize: "12px", color: "#475569", marginTop: "2px" }}>
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
          borderTop: "1px solid #f1f5f9",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Participants</span>
          <span style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a" }}>{brief.participants_count}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Open Requests</span>
          <span style={{ fontSize: "18px", fontWeight: 700, color: brief.open_requests_count > 0 ? "#d97706" : "#059669" }}>
            {brief.open_requests_count}
          </span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Evidence Records</span>
          <span style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a" }}>{brief.recent_documents_count}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Active Tasks</span>
          <span style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a" }}>{brief.pending_tasks_count}</span>
        </div>
      </div>
    </div>
  );
}
