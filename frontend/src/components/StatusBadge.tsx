import React from "react";
import { resolveCanonicalStatus, CanonicalStatusDefinition } from "@/lib/canonicalStatus";

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

export interface StatusBadgeProps {
  status: string;
  variant?: StatusBadgeVariant | string;
  label?: string;
  pulse?: boolean;
  showMeaningTooltip?: boolean;
}

export function StatusBadge({
  status,
  variant,
  label,
  pulse = false,
  showMeaningTooltip = true,
}: StatusBadgeProps) {
  const canonicalDef: CanonicalStatusDefinition = resolveCanonicalStatus(variant || status);

  const displayLabel = label || canonicalDef.label;

  return (
    <span
      title={showMeaningTooltip ? canonicalDef.semanticMeaning : undefined}
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
        background: canonicalDef.bg,
        color: canonicalDef.text,
        border: `1px solid ${canonicalDef.border}`,
        whiteSpace: "nowrap",
        cursor: showMeaningTooltip ? "help" : "default",
      }}
    >
      <span
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          backgroundColor: canonicalDef.dotColor,
          boxShadow: pulse ? `0 0 8px ${canonicalDef.dotColor}` : "none",
          flexShrink: 0,
        }}
      />
      {displayLabel}
    </span>
  );
}
