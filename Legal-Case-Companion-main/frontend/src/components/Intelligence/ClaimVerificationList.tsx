import React from "react";
import { AIMessageClaim } from "@/types";

interface ClaimVerificationListProps {
  claims: AIMessageClaim[];
}

export function ClaimVerificationList({ claims }: ClaimVerificationListProps) {
  if (!claims || claims.length === 0) return null;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "SUPPORTED":
        return { bg: "rgba(16, 185, 129, 0.15)", color: "#10b981", border: "1px solid rgba(16, 185, 129, 0.3)", label: "Supported by Record" };
      case "PARTIALLY_SUPPORTED":
        return { bg: "rgba(245, 158, 11, 0.15)", color: "#f59e0b", border: "1px solid rgba(245, 158, 11, 0.3)", label: "Partially Supported" };
      case "CONTRADICTED":
      case "UNSUPPORTED":
        return { bg: "rgba(239, 68, 68, 0.15)", color: "#ef4444", border: "1px solid rgba(239, 68, 68, 0.3)", label: "Requires Verification" };
      default:
        return { bg: "rgba(148, 163, 184, 0.15)", color: "#94a3b8", border: "1px solid rgba(148, 163, 184, 0.3)", label: status };
    }
  };

  return (
    <div
      style={{
        marginTop: "12px",
        padding: "14px 16px",
        borderRadius: "var(--radius-sm)",
        background: "rgba(255, 255, 255, 0.02)",
        border: "1px solid var(--border-subtle)",
      }}
    >
      <div
        style={{
          fontSize: "11px",
          fontWeight: 700,
          color: "var(--text-secondary)",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          marginBottom: "10px",
          display: "flex",
          alignItems: "center",
          gap: "6px",
        }}
      >
        <span>✓</span> Post-Generation Factual Claim Verification Matrix ({claims.length})
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {claims.map((claim, idx) => {
          const badge = getStatusBadge(claim.status);
          return (
            <div
              key={idx}
              style={{
                padding: "10px 12px",
                borderRadius: "6px",
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                display: "flex",
                flexDirection: "column",
                gap: "4px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" }}>
                <span style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: 1.45 }}>
                  {claim.claim_text}
                </span>
                <span
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    padding: "2px 6px",
                    borderRadius: "4px",
                    background: badge.bg,
                    color: badge.color,
                    border: badge.border,
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                  }}
                >
                  {badge.label}
                </span>
              </div>

              {claim.explanation && (
                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                  Reason: {claim.explanation}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
