"use client";

import React from "react";

export type LegalStatusType =
  | "OPEN"
  | "IN_PROGRESS"
  | "IN_REVIEW"
  | "PENDING_COURT"
  | "JUDGMENT_RESERVED"
  | "STATUTORY_LIMITATION"
  | "HEARING_SCHEDULED"
  | "CLOSED"
  | "DISPOSED"
  | "ARCHIVED"
  | "SAFE"
  | "VERIFIED"
  | "URGENT"
  | "HIGH"
  | "MEDIUM"
  | "LOW"
  | string;

export interface StatusChipProps {
  status: LegalStatusType;
  label?: string;
  pulse?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export function StatusChip({ status, label, pulse = false, className, style }: StatusChipProps) {
  const norm = (status || "").toUpperCase().replace(/[\s-]/g, "_");

  let bg = "rgba(148, 163, 184, 0.12)";
  let text = "#94a3b8";
  let border = "rgba(148, 163, 184, 0.25)";
  let dotColor = "#94a3b8";
  let displayLabel = label || status.replace(/_/g, " ");

  switch (norm) {
    case "OPEN":
    case "IN_PROGRESS":
    case "SAFE":
    case "CLEAN":
    case "VERIFIED":
    case "PAID":
    case "SUCCEEDED":
      bg = "rgba(16, 185, 129, 0.12)";
      text = "var(--success, #10B981)";
      border = "rgba(16, 185, 129, 0.32)";
      dotColor = "#10B981";
      break;

    case "IN_REVIEW":
    case "HEARING_SCHEDULED":
    case "SCHEDULED":
    case "ACTIVE":
    case "ACCEPTED":
      bg = "rgba(6, 182, 212, 0.12)";
      text = "var(--info, #06B6D4)";
      border = "rgba(6, 182, 212, 0.32)";
      dotColor = "#06B6D4";
      break;

    case "PENDING":
    case "PENDING_COURT":
    case "VALIDATING":
    case "MEDIUM":
      bg = "rgba(245, 158, 11, 0.14)";
      text = "var(--warning, #F59E0B)";
      border = "rgba(245, 158, 11, 0.35)";
      dotColor = "#F59E0B";
      break;

    case "JUDGMENT_RESERVED":
      bg = "rgba(99, 102, 241, 0.16)";
      text = "#a5b4fc";
      border = "rgba(99, 102, 241, 0.38)";
      dotColor = "#818cf8";
      displayLabel = label || "Judgment Reserved";
      break;

    case "STATUTORY_LIMITATION":
    case "URGENT":
    case "HIGH":
    case "OVERDUE":
    case "FAILED":
    case "REJECTED":
      bg = "rgba(239, 68, 68, 0.14)";
      text = "var(--urgent, #EF4444)";
      border = "rgba(239, 68, 68, 0.38)";
      dotColor = "#EF4444";
      if (norm === "STATUTORY_LIMITATION") {
        displayLabel = label || "Statutory Limitation";
      }
      break;

    case "CLOSED":
    case "DISPOSED":
    case "ARCHIVED":
    case "LOW":
      bg = "rgba(148, 163, 184, 0.12)";
      text = "#94a3b8";
      border = "rgba(148, 163, 184, 0.25)";
      dotColor = "#94a3b8";
      break;
  }

  return (
    <span
      role="status"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "3px 10px",
        borderRadius: "var(--radius-full, 9999px)",
        fontSize: "var(--font-size-2xs, 11px)",
        fontWeight: 600,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        background: bg,
        color: text,
        border: `1px solid ${border}`,
        whiteSpace: "nowrap",
        ...style,
      }}
      className={className}
    >
      <span
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          backgroundColor: dotColor,
          boxShadow: pulse ? `0 0 8px ${dotColor}` : "none",
        }}
        aria-hidden="true"
      />
      {displayLabel}
    </span>
  );
}
