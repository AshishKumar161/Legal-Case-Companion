"use client";

import React from "react";

export interface SectionHeaderProps {
  title: string;
  count?: number;
  badge?: React.ReactNode;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export function SectionHeader({
  title,
  count,
  badge,
  description,
  actions,
  className,
  style,
}: SectionHeaderProps) {
  return (
    <div
      className={className}
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-end",
        gap: "16px",
        marginBottom: "16px",
        flexWrap: "wrap",
        borderBottom: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
        paddingBottom: "12px",
        ...style,
      }}
    >
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <h2
            style={{
              fontSize: "18px",
              fontWeight: 700,
              color: "var(--text-primary, #f8fafc)",
              margin: 0,
              letterSpacing: "-0.01em",
            }}
          >
            {title}
          </h2>
          {count !== undefined && (
            <span
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: "var(--text-muted, #64748b)",
                background: "rgba(255, 255, 255, 0.06)",
                padding: "2px 8px",
                borderRadius: "12px",
              }}
            >
              {count}
            </span>
          )}
          {badge}
        </div>
        {description && (
          <p
            style={{
              margin: "4px 0 0",
              fontSize: "13px",
              color: "var(--text-secondary, #94a3b8)",
            }}
          >
            {description}
          </p>
        )}
      </div>

      {actions && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          {actions}
        </div>
      )}
    </div>
  );
}
