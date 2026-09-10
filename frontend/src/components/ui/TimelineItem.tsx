"use client";

import React from "react";
import { StatusChip } from "./StatusChip";

export interface TimelineItemProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  timestamp: string;
  actor?: string;
  status?: string;
  provenance?: "OFFICIAL COURT DATA" | "LAWYER ENTERED" | "YOU ADDED" | "SYSTEM" | string;
  eventCategory?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  isLast?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export function TimelineItem({
  title,
  description,
  timestamp,
  actor,
  status,
  provenance,
  eventCategory,
  action,
  icon = "⚖",
  isLast = false,
  className,
  style,
}: TimelineItemProps) {
  return (
    <div
      style={{
        display: "flex",
        gap: "16px",
        position: "relative",
        ...style,
      }}
      className={className}
    >
      {/* Left Column: Icon Marker and Connecting Spine */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: "32px",
            height: "32px",
            borderRadius: "50%",
            background: "var(--surface-elevated, #151A24)",
            border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.12))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "14px",
            color: "var(--brand-primary, #6366f1)",
            zIndex: 1,
          }}
          aria-hidden="true"
        >
          {icon}
        </div>

        {!isLast && (
          <div
            style={{
              width: "2px",
              flex: 1,
              background: "var(--border-subtle, rgba(255, 255, 255, 0.08))",
              margin: "4px 0",
              minHeight: "36px",
            }}
            aria-hidden="true"
          />
        )}
      </div>

      {/* Right Column: Event Content */}
      <div
        style={{
          flex: 1,
          paddingBottom: isLast ? "0" : "24px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "8px",
            marginBottom: "4px",
          }}
        >
          {eventCategory && (
            <span
              style={{
                fontSize: "10px",
                fontWeight: 800,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: "var(--brand-primary, #818cf8)",
                background: "rgba(99, 102, 241, 0.12)",
                padding: "1px 6px",
                borderRadius: "var(--radius-xs, 4px)",
              }}
            >
              {eventCategory}
            </span>
          )}

          <h4
            style={{
              margin: 0,
              fontSize: "var(--font-size-sm, 14px)",
              fontWeight: 600,
              color: "var(--text-primary, #f8fafc)",
            }}
          >
            {title}
          </h4>

          {status && <StatusChip status={status} />}

          {provenance && (
            <span
              style={{
                fontSize: "9px",
                fontWeight: 700,
                letterSpacing: "0.05em",
                textTransform: "uppercase",
                padding: "2px 6px",
                borderRadius: "4px",
                background:
                  provenance.includes("COURT")
                    ? "rgba(56, 189, 248, 0.15)"
                    : provenance.includes("LAWYER")
                    ? "rgba(129, 140, 248, 0.15)"
                    : provenance.includes("YOU")
                    ? "rgba(52, 211, 153, 0.15)"
                    : "rgba(148, 163, 184, 0.15)",
                color:
                  provenance.includes("COURT")
                    ? "#38bdf8"
                    : provenance.includes("LAWYER")
                    ? "#a5b4fc"
                    : provenance.includes("YOU")
                    ? "#34d399"
                    : "#94a3b8",
                border:
                  provenance.includes("COURT")
                    ? "1px solid rgba(56, 189, 248, 0.3)"
                    : provenance.includes("LAWYER")
                    ? "1px solid rgba(129, 140, 248, 0.3)"
                    : provenance.includes("YOU")
                    ? "1px solid rgba(52, 211, 153, 0.3)"
                    : "1px solid rgba(148, 163, 184, 0.25)",
              }}
            >
              {provenance}
            </span>
          )}
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "8px",
            fontSize: "var(--font-size-xs, 12px)",
            color: "var(--text-muted, #64748b)",
            marginBottom: "6px",
          }}
        >
          <span>{timestamp}</span>
          {actor && (
            <>
              <span aria-hidden="true">•</span>
              <span style={{ color: "var(--text-secondary, #94a3b8)" }}>By {actor}</span>
            </>
          )}
        </div>

        {description && (
          <div
            style={{
              fontSize: "var(--font-size-sm, 14px)",
              color: "var(--text-secondary, #cbd5e1)",
              lineHeight: 1.5,
              background: "var(--surface-card, #0E121A)",
              border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.06))",
              borderRadius: "var(--radius-md, 8px)",
              padding: "10px 14px",
              marginTop: "6px",
            }}
          >
            {description}
          </div>
        )}

        {action && (
          <div style={{ marginTop: "8px" }}>
            {action}
          </div>
        )}
      </div>
    </div>
  );
}
