import React from "react";

export type StatusBadgeVariant =
  | "OPEN"
  | "IN_PROGRESS"
  | "IN_REVIEW"
  | "PENDING_COURT"
  | "CLOSED"
  | "ARCHIVED"
  | "SAFE"
  | "CLEAN"
  | "VALIDATING"
  | "PENDING"
  | "QUARANTINED"
  | "REJECTED"
  | "INDEXED"
  | "STATUTORY_LIMITATION"
  | "URGENT"
  | "HIGH"
  | "MEDIUM"
  | "LOW"
  | "VERIFIED"
  | "CONFIRMED";

interface StatusBadgeProps {
  status: string;
  variant?: StatusBadgeVariant;
  label?: string;
  pulse?: boolean;
}

export function StatusBadge({ status, variant, label, pulse = false }: StatusBadgeProps) {
  const norm = (variant || status || "").toUpperCase().replace(/[\s-]/g, "_");

  let bg = "rgba(100, 116, 139, 0.15)";
  let text = "#94a3b8";
  let border = "rgba(100, 116, 139, 0.3)";
  let dotColor = "#94a3b8";
  let displayLabel = label || status;

  switch (norm) {
    case "OPEN":
    case "IN_PROGRESS":
    case "SAFE":
    case "CLEAN":
    case "VERIFIED":
    case "CONFIRMED":
    case "INDEXED":
    case "PAID":
    case "SUCCEEDED":
      bg = "rgba(16, 185, 129, 0.12)";
      text = "#10b981";
      border = "rgba(16, 185, 129, 0.3)";
      dotColor = "#10b981";
      break;

    case "IN_REVIEW":
    case "SCHEDULED":
    case "ACTIVE":
    case "ACCEPTED":
      bg = "rgba(59, 130, 246, 0.12)";
      text = "#60a5fa";
      border = "rgba(59, 130, 246, 0.3)";
      dotColor = "#60a5fa";
      break;

    case "PENDING":
    case "PENDING_COURT":
    case "VALIDATING":
    case "MEDIUM":
    case "REQUESTED":
    case "CREATED":
      bg = "rgba(245, 158, 11, 0.12)";
      text = "#f59e0b";
      border = "rgba(245, 158, 11, 0.3)";
      dotColor = "#f59e0b";
      break;

    case "URGENT":
    case "HIGH":
    case "QUARANTINED":
    case "REJECTED":
    case "OVERDUE":
    case "FAILED":
    case "CANCELLED":
      bg = "rgba(239, 68, 68, 0.12)";
      text = "#ef4444";
      border = "rgba(239, 68, 68, 0.3)";
      dotColor = "#ef4444";
      break;

    case "REFUNDED":
      bg = "rgba(168, 85, 247, 0.12)";
      text = "#c084fc";
      border = "rgba(168, 85, 247, 0.3)";
      dotColor = "#c084fc";
      break;

    case "STATUTORY_LIMITATION":
      bg = "rgba(220, 38, 38, 0.18)";
      text = "#f87171";
      border = "rgba(220, 38, 38, 0.4)";
      dotColor = "#f87171";
      displayLabel = label || "Statutory Limitation";
      break;

    case "CLOSED":
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
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "3px 9px",
        borderRadius: "20px",
        fontSize: "11px",
        fontWeight: 600,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        background: bg,
        color: text,
        border: `1px solid ${border}`,
        whiteSpace: "nowrap",
      }}
    >
      <span
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          backgroundColor: dotColor,
          boxShadow: pulse ? `0 0 8px ${dotColor}` : "none",
        }}
      />
      {displayLabel}
    </span>
  );
}
