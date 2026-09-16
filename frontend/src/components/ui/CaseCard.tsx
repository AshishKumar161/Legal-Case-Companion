"use client";

import React from "react";
import Link from "next/link";
import { Badge } from "./Badge";

export interface CaseCardProps {
  id: string;
  title: string;
  status: string;
  courtName?: string | null;
  caseType?: string | null;
  nextImportantDate?: string | null;
  nextActionLabel?: string | null;
  lawyerName?: string | null;
  updatedAt?: string | null;
  href?: string;
  className?: string;
}

export function CaseCard({
  id,
  title,
  status,
  courtName,
  caseType,
  nextImportantDate,
  lawyerName,
  href,
  className,
}: CaseCardProps) {
  const caseHref = href || `/cases/${id}`;

  const getStatusVariant = (st: string) => {
    const s = st.toUpperCase();
    if (s.includes("ACTIVE") || s.includes("PROGRESS") || s.includes("OPEN")) return "success";
    if (s.includes("HEARING") || s.includes("URGENT")) return "urgent";
    if (s.includes("PENDING") || s.includes("REVIEW")) return "warning";
    if (s.includes("CLOSED") || s.includes("DISPOSED")) return "default";
    return "primary";
  };

  const formatStatusText = (st: string) => {
    const s = st.toUpperCase();
    if (s.includes("ACTIVE") || s.includes("IN_PROGRESS")) return "In progress";
    if (s.includes("HEARING")) return "Hearing listed";
    if (s.includes("CLOSED") || s.includes("DISPOSED")) return "Completed";
    return st.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <div
      style={{
        background: "var(--surface-card, #FFFFFF)",
        border: "1px solid var(--border-subtle, #D9E2EC)",
        borderRadius: "var(--radius-lg, 14px)",
        padding: "20px 24px",
        boxShadow: "var(--shadow-sm)",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        transition: "all var(--transition-fast, 0.15s ease)",
      }}
      className={className}
    >
      {/* Top row: Title and Status badge */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px" }}>
        <div>
          <Link
            href={caseHref}
            style={{
              fontSize: "var(--font-size-lg, 17px)",
              fontWeight: 700,
              color: "var(--text-primary, #17212B)",
              fontFamily: "var(--font-display, sans-serif)",
              textDecoration: "none",
              display: "inline-block",
            }}
          >
            {title ? (title.charAt(0).toUpperCase() + title.slice(1)) : ""}
          </Link>
          {(courtName || caseType) && (
            <p
              style={{
                margin: "4px 0 0 0",
                fontSize: "var(--font-size-xs, 13px)",
                color: "var(--text-secondary, #52606D)",
              }}
            >
              {[caseType, courtName].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
        <Badge variant={getStatusVariant(status)} size="md">
          {formatStatusText(status)}
        </Badge>
      </div>

      {/* Middle row: Key information */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: "12px",
          padding: "12px 14px",
          background: "var(--surface-base, #F7F9FC)",
          borderRadius: "var(--radius-md, 10px)",
          border: "1px solid var(--border-subtle, #E2E8F0)",
        }}
      >
        <div>
          <span style={{ display: "block", fontSize: "12px", color: "var(--text-muted, #7B8794)", marginBottom: "2px" }}>
            Next important date
          </span>
          <span style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-primary, #17212B)" }}>
            {nextImportantDate || "None scheduled"}
          </span>
        </div>

        {lawyerName && (
          <div>
            <span style={{ display: "block", fontSize: "12px", color: "var(--text-muted, #7B8794)", marginBottom: "2px" }}>
              Assigned advocate
            </span>
            <span style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-primary, #17212B)" }}>
              {lawyerName}
            </span>
          </div>
        )}
      </div>

      {/* Footer: View case action */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end" }}>
        <Link
          href={caseHref}
          className="btn btn-secondary"
          style={{
            padding: "8px 18px",
            fontSize: "14px",
            minHeight: "40px",
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <span>View case</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </Link>
      </div>
    </div>
  );
}
