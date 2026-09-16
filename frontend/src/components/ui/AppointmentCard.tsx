"use client";

import React from "react";
import { Badge } from "./Badge";

export interface AppointmentCardProps {
  id: string;
  type: "HEARING" | "CONSULTATION";
  title: string;
  dateStr: string;
  timeStr?: string;
  status?: string;
  partyOrCourt?: string;
  location?: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  className?: string;
}

export function AppointmentCard({
  type,
  title,
  dateStr,
  timeStr,
  status = "SCHEDULED",
  partyOrCourt,
  location,
  actionLabel,
  onAction,
  secondaryActionLabel,
  onSecondaryAction,
  className,
}: AppointmentCardProps) {
  const isHearing = type === "HEARING";

  const getBadgeVariant = (st: string) => {
    const s = st.toUpperCase();
    if (s.includes("CONFIRMED") || s.includes("SCHEDULED")) return "primary";
    if (s.includes("COMPLETED")) return "success";
    if (s.includes("CANCEL")) return "urgent";
    return "default";
  };

  return (
    <div
      style={{
        background: "var(--surface-card, #FFFFFF)",
        border: "1px solid var(--border-subtle, #D9E2EC)",
        borderRadius: "var(--radius-lg, 14px)",
        padding: "18px 20px",
        boxShadow: "var(--shadow-sm)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
        flexWrap: "wrap",
      }}
      className={className}
    >
      {/* Left side: Date Badge & Details */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px", minWidth: 0, flex: "1 1 280px" }}>
        {/* Date block */}
        <div
          style={{
            width: "56px",
            height: "56px",
            borderRadius: "var(--radius-md, 10px)",
            background: isHearing ? "rgba(23, 50, 77, 0.06)" : "rgba(47, 133, 90, 0.08)",
            border: `1px solid ${isHearing ? "rgba(23, 50, 77, 0.15)" : "rgba(47, 133, 90, 0.2)"}`,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            flexShrink: 0,
          }}
        >
          <span
            style={{
              fontSize: "11px",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: isHearing ? "var(--navy-primary, #17324D)" : "var(--status-success, #2F855A)",
              lineHeight: 1,
            }}
          >
            {dateStr.split(" ")[1] || "DATE"}
          </span>
          <span
            style={{
              fontSize: "18px",
              fontWeight: 800,
              color: "var(--text-primary, #17212B)",
              lineHeight: 1.2,
            }}
          >
            {dateStr.split(" ")[0] || "—"}
          </span>
        </div>

        {/* Text info */}
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", marginBottom: "3px" }}>
            <h4
              style={{
                margin: 0,
                fontSize: "var(--font-size-base, 15px)",
                fontWeight: 600,
                color: "var(--text-primary, #17212B)",
              }}
            >
              {title}
            </h4>
            <Badge variant={getBadgeVariant(status)} size="sm">
              {status.toLowerCase().replace(/_/g, " ")}
            </Badge>
          </div>

          <p
            style={{
              margin: 0,
              fontSize: "var(--font-size-xs, 13px)",
              color: "var(--text-secondary, #52606D)",
            }}
          >
            {[timeStr, partyOrCourt, location].filter(Boolean).join(" · ")}
          </p>
        </div>
      </div>

      {/* Right side: Action buttons */}
      {(actionLabel || secondaryActionLabel) && (
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flexShrink: 0 }}>
          {secondaryActionLabel && onSecondaryAction && (
            <button
              onClick={onSecondaryAction}
              className="btn btn-secondary"
              style={{ minHeight: "38px", padding: "6px 14px", fontSize: "13px" }}
            >
              {secondaryActionLabel}
            </button>
          )}
          {actionLabel && onAction && (
            <button
              onClick={onAction}
              className="btn btn-primary"
              style={{ minHeight: "38px", padding: "6px 16px", fontSize: "13px" }}
            >
              {actionLabel}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
