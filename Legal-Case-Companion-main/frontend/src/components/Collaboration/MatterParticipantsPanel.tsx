"use client";

import React from "react";
import { MatterParticipantDetailItem } from "@/types";

interface MatterParticipantsPanelProps {
  participants: MatterParticipantDetailItem[];
  loading?: boolean;
}

export function MatterParticipantsPanel({
  participants,
  loading,
}: MatterParticipantsPanelProps) {
  if (loading) {
    return (
      <div style={{ color: "var(--text-muted)", fontSize: "13px", padding: "20px" }}>
        Loading participant directory...
      </div>
    );
  }

  const roleBadgeStyle = (role: string) => {
    switch (role) {
      case "LAWYER":
        return { background: "rgba(59, 130, 246, 0.15)", color: "#60a5fa" };
      case "OWNER":
        return { background: "rgba(16, 185, 129, 0.15)", color: "#34d399" };
      default:
        return { background: "rgba(148, 163, 184, 0.15)", color: "#94a3b8" };
    }
  };

  return (
    <div
      style={{
        background: "var(--surface-card)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-md)",
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
      }}
    >
      <div>
        <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0 }}>
          Authorized Matter Participants ({participants.length})
        </h3>
        <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
          Verified advocates, instructing clients, and authorized observers bound by confidentiality obligations.
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "14px",
        }}
      >
        {participants.map((p) => {
          const badge = roleBadgeStyle(p.participant_role);
          const isCounsel = p.participant_role === "LAWYER";

          return (
            <div
              key={p.id}
              style={{
                background: "#131722",
                border: "1px solid #202738",
                borderRadius: "8px",
                padding: "16px",
                display: "flex",
                flexDirection: "column",
                gap: "8px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <h4 style={{ fontSize: "14px", fontWeight: 600, color: "#fff", margin: 0 }}>
                    {p.full_name}
                  </h4>
                  <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>{p.email}</span>
                </div>
                <span
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    padding: "2px 8px",
                    borderRadius: "4px",
                    background: badge.background,
                    color: badge.color,
                  }}
                >
                  {p.participant_role}
                </span>
              </div>

              {isCounsel ? (
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "2px", marginTop: "4px" }}>
                  {p.lawyer_bar_number && (
                    <span>
                      🏛️ Bar Enrollment: <strong style={{ color: "#e2e8f0" }}>{p.lawyer_bar_number}</strong>
                    </span>
                  )}
                  {p.lawyer_specialization && (
                    <span>Specialization: {p.lawyer_specialization}</span>
                  )}
                  {p.lawyer_firm_name && (
                    <span>Chambers / Jurisdiction: {p.lawyer_firm_name}</span>
                  )}
                </div>
              ) : (
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "4px" }}>
                  🏢 Client Entity / Location: {p.client_organization || "Individual Matter Principal"}
                </div>
              )}

              <div
                style={{
                  borderTop: "1px solid rgba(255, 255, 255, 0.05)",
                  paddingTop: "8px",
                  marginTop: "4px",
                  fontSize: "10px",
                  color: "var(--text-muted)",
                }}
              >
                Access Granted: {new Date(p.joined_at).toLocaleDateString("en-IN")} • Status:{" "}
                <span style={{ color: "#10b981", fontWeight: 600 }}>{p.status}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
