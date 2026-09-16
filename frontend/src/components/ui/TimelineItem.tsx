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
  icon,
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
            width: "28px",
            height: "28px",
            borderRadius: "50%",
            background: "var(--surface-subtle, #EAF4FB)",
            border: "2px solid var(--navy-primary, #17324D)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "12px",
            color: "var(--navy-primary, #17324D)",
            zIndex: 1,
          }}
          aria-hidden="true"
        >
          {icon || (
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: "var(--navy-primary, #17324D)",
              }}
            />
          )}
        </div>

        {!isLast && (
          <div
            style={{
              width: "2px",
              flex: 1,
              background: "var(--border-subtle, #D9E2EC)",
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
                fontSize: "11px",
                fontWeight: 600,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                color: "var(--navy-primary, #17324D)",
                background: "var(--surface-subtle, #EAF4FB)",
                padding: "1px 8px",
                borderRadius: "var(--radius-xs, 4px)",
              }}
            >
              {eventCategory}
            </span>
          )}

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

          {status && <StatusChip status={status} />}

          {provenance && (
            <span
              style={{
                fontSize: "11px",
                fontWeight: 600,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                padding: "2px 8px",
                borderRadius: "4px",
                background: "var(--surface-subtle, #EAF4FB)",
                color: "var(--navy-primary, #17324D)",
                border: "1px solid var(--border-subtle, #D9E2EC)",
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
              <span style={{ color: "var(--text-secondary, #52606D)" }}>By {actor}</span>
            </>
          )}
        </div>

        {description && (
          <div
            style={{
              fontSize: "var(--font-size-sm, 14px)",
              color: "var(--text-secondary, #52606D)",
              lineHeight: 1.5,
              background: "var(--surface-base, #F7F9FC)",
              border: "1px solid var(--border-subtle, #D9E2EC)",
              borderRadius: "var(--radius-md, 10px)",
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
