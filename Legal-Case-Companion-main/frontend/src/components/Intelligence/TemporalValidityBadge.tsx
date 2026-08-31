import React from "react";

interface TemporalValidityBadgeProps {
  isCurrent?: boolean;
  effectiveFrom?: string | null;
  effectiveTo?: string | null;
  authorityLevel?: number;
  jurisdiction?: string;
  size?: "sm" | "md";
}

export function TemporalValidityBadge({
  isCurrent = true,
  effectiveFrom,
  effectiveTo,
  authorityLevel,
  jurisdiction,
  size = "sm",
}: TemporalValidityBadgeProps) {
  const isExpired = effectiveTo && new Date(effectiveTo) < new Date();
  const statusLabel = isExpired ? "HISTORICAL / SUPERSEDED" : isCurrent ? "CURRENT IN FORCE" : "AMENDED / QUALIFIED";

  const statusBg = isExpired
    ? "rgba(239, 68, 68, 0.15)"
    : isCurrent
    ? "rgba(16, 185, 129, 0.15)"
    : "rgba(245, 158, 11, 0.15)";

  const statusColor = isExpired ? "#ef4444" : isCurrent ? "#10b981" : "#f59e0b";
  const statusBorder = isExpired
    ? "rgba(239, 68, 68, 0.3)"
    : isCurrent
    ? "rgba(16, 185, 129, 0.3)"
    : "rgba(245, 158, 11, 0.3)";

  const getTierLabel = (lvl?: number) => {
    switch (lvl) {
      case 10:
        return "Supreme Court of India (Binding Pan-India)";
      case 8:
        return "High Court Precedent";
      case 7:
        return "Primary Parliamentary Statute";
      case 5:
        return "State Legislation / Regulation";
      default:
        return "Authoritative Enactment";
    }
  };

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        flexWrap: "wrap",
        gap: "6px",
        fontSize: size === "sm" ? "11px" : "12px",
      }}
    >
      <span
        style={{
          padding: size === "sm" ? "2px 6px" : "3px 8px",
          borderRadius: "4px",
          background: statusBg,
          color: statusColor,
          border: `1px solid ${statusBorder}`,
          fontWeight: 700,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          display: "inline-flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        <span>●</span> {statusLabel}
      </span>

      {effectiveFrom && (
        <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>
          Eff: {effectiveFrom}
          {effectiveTo ? ` to ${effectiveTo}` : " - Present"}
        </span>
      )}

      {jurisdiction && (
        <span
          style={{
            padding: "2px 6px",
            borderRadius: "4px",
            background: "rgba(109, 124, 255, 0.1)",
            color: "#8d98ff",
            border: "1px solid rgba(109, 124, 255, 0.25)",
            fontSize: "10px",
            fontWeight: 600,
          }}
        >
          {jurisdiction}
        </span>
      )}

      {authorityLevel && (
        <span
          style={{
            color: "var(--text-secondary)",
            fontSize: "11px",
          }}
          title={getTierLabel(authorityLevel)}
        >
          • Tier {authorityLevel} Authority
        </span>
      )}
    </div>
  );
}
