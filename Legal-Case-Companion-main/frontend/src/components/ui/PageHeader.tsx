"use client";

import React from "react";

export interface PageHeaderProps {
  eyebrow?: string;
  eyebrowColor?: string;
  title: string;
  badge?: React.ReactNode;
  description?: string | React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export function PageHeader({
  eyebrow,
  eyebrowColor = "var(--accent-secondary, #8b5cf6)",
  title,
  badge,
  description,
  actions,
  className,
  style,
}: PageHeaderProps) {
  return (
    <div
      className={className}
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: "24px",
        marginBottom: "28px",
        flexWrap: "wrap",
        ...style,
      }}
    >
      <div style={{ maxWidth: "760px", flex: "1 1 320px" }}>
        {eyebrow && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              color: eyebrowColor,
              fontSize: "11px",
              fontWeight: 700,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              marginBottom: "8px",
            }}
          >
            <span
              style={{
                width: "7px",
                height: "7px",
                borderRadius: "50%",
                backgroundColor: eyebrowColor,
                display: "inline-block",
              }}
            />
            {eyebrow}
          </div>
        )}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            flexWrap: "wrap",
          }}
        >
          <h1
            style={{
              fontSize: "26px",
              fontWeight: 700,
              letterSpacing: "-0.03em",
              color: "var(--text-primary, #f8fafc)",
              margin: 0,
              lineHeight: 1.25,
            }}
          >
            {title}
          </h1>
          {badge}
        </div>
        {description && (
          <div
            style={{
              color: "var(--text-secondary, #94a3b8)",
              fontSize: "13px",
              marginTop: "6px",
              lineHeight: 1.55,
            }}
          >
            {description}
          </div>
        )}
      </div>

      {actions && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            flexWrap: "wrap",
          }}
        >
          {actions}
        </div>
      )}
    </div>
  );
}
