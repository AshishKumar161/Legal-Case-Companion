"use client";

import React from "react";

export interface AlertProps {
  variant?: "info" | "warning" | "urgent" | "success";
  title?: React.ReactNode;
  children: React.ReactNode;
  onDismiss?: () => void;
  icon?: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export function Alert({
  variant = "info",
  title,
  children,
  onDismiss,
  icon,
  className,
  style,
}: AlertProps) {
  const isUrgent = variant === "urgent";

  const config: Record<
    string,
    { bg: string; text: string; border: string; defaultIcon: string; titleColor: string }
  > = {
    info: {
      bg: "rgba(6, 182, 212, 0.1)",
      text: "#cffafe",
      border: "rgba(6, 182, 212, 0.3)",
      titleColor: "var(--info, #06B6D4)",
      defaultIcon: "ℹ",
    },
    warning: {
      bg: "rgba(245, 158, 11, 0.1)",
      text: "#fef3c7",
      border: "rgba(245, 158, 11, 0.35)",
      titleColor: "var(--warning, #F59E0B)",
      defaultIcon: "⚠",
    },
    urgent: {
      bg: "rgba(239, 68, 68, 0.12)",
      text: "#fee2e2",
      border: "rgba(239, 68, 68, 0.4)",
      titleColor: "var(--urgent, #EF4444)",
      defaultIcon: "⚡",
    },
    success: {
      bg: "rgba(16, 185, 129, 0.1)",
      text: "#d1fae5",
      border: "rgba(16, 185, 129, 0.32)",
      titleColor: "var(--success, #10B981)",
      defaultIcon: "✓",
    },
  };

  const c = config[variant] || config.info;

  return (
    <div
      role={isUrgent ? "alert" : "status"}
      aria-live={isUrgent ? "assertive" : "polite"}
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "12px",
        padding: "14px 16px",
        borderRadius: "var(--radius-md, 8px)",
        background: c.bg,
        border: `1px solid ${c.border}`,
        color: c.text,
        fontSize: "var(--font-size-sm, 14px)",
        lineHeight: 1.5,
        ...style,
      }}
      className={className}
    >
      <span
        style={{
          fontSize: "16px",
          lineHeight: 1,
          marginTop: "2px",
          color: c.titleColor,
          fontWeight: 700,
        }}
        aria-hidden="true"
      >
        {icon || c.defaultIcon}
      </span>

      <div style={{ flex: 1 }}>
        {title && (
          <h4
            style={{
              margin: "0 0 4px 0",
              fontSize: "var(--font-size-sm, 14px)",
              fontWeight: 600,
              color: c.titleColor,
            }}
          >
            {title}
          </h4>
        )}
        <div>{children}</div>
      </div>

      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss alert"
          style={{
            background: "transparent",
            border: "none",
            color: "currentColor",
            opacity: 0.7,
            cursor: "pointer",
            padding: "4px",
            minHeight: "36px",
            minWidth: "36px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: "var(--radius-xs, 4px)",
          }}
        >
          ✕
        </button>
      )}
    </div>
  );
}
