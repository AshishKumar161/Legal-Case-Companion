"use client";

import React from "react";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "primary" | "success" | "warning" | "urgent" | "info" | "outline";
  size?: "sm" | "md";
  dot?: boolean;
}

export function Badge({
  variant = "default",
  size = "md",
  dot = false,
  children,
  style,
  className,
  ...props
}: BadgeProps) {
  const sizeStyles: Record<string, React.CSSProperties> = {
    sm: {
      padding: "2px 6px",
      fontSize: "var(--font-size-2xs, 11px)",
      borderRadius: "var(--radius-xs, 4px)",
    },
    md: {
      padding: "3px 10px",
      fontSize: "var(--font-size-xs, 12px)",
      borderRadius: "var(--radius-full, 9999px)",
    },
  };

  const variantStyles: Record<string, { bg: string; text: string; border: string; dot: string }> = {
    default: {
      bg: "rgba(148, 163, 184, 0.12)",
      text: "#94a3b8",
      border: "rgba(148, 163, 184, 0.25)",
      dot: "#94a3b8",
    },
    primary: {
      bg: "rgba(99, 102, 241, 0.14)",
      text: "#818cf8",
      border: "rgba(99, 102, 241, 0.3)",
      dot: "#6366f1",
    },
    success: {
      bg: "var(--status-safe-bg, rgba(16, 185, 129, 0.12))",
      text: "var(--success, #10B981)",
      border: "var(--status-safe-border, rgba(16, 185, 129, 0.32))",
      dot: "#10B981",
    },
    warning: {
      bg: "var(--status-warning-bg, rgba(245, 158, 11, 0.14))",
      text: "var(--warning, #F59E0B)",
      border: "var(--status-warning-border, rgba(245, 158, 11, 0.35))",
      dot: "#F59E0B",
    },
    urgent: {
      bg: "var(--status-urgent-bg, rgba(239, 68, 68, 0.14))",
      text: "var(--urgent, #EF4444)",
      border: "var(--status-urgent-border, rgba(239, 68, 68, 0.38))",
      dot: "#EF4444",
    },
    info: {
      bg: "var(--status-info-bg, rgba(6, 182, 212, 0.12))",
      text: "var(--info, #06B6D4)",
      border: "var(--status-info-border, rgba(6, 182, 212, 0.32))",
      dot: "#06B6D4",
    },
    outline: {
      bg: "transparent",
      text: "var(--text-secondary, #94a3b8)",
      border: "var(--border-subtle, rgba(255, 255, 255, 0.15))",
      dot: "#94a3b8",
    },
  };

  const v = variantStyles[variant] || variantStyles.default;

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        fontFamily: "var(--font-sans, sans-serif)",
        fontWeight: 600,
        letterSpacing: "0.02em",
        whiteSpace: "nowrap",
        background: v.bg,
        color: v.text,
        border: `1px solid ${v.border}`,
        ...sizeStyles[size],
        ...style,
      }}
      className={className}
      {...props}
    >
      {dot && (
        <span
          style={{
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            backgroundColor: v.dot,
            display: "inline-block",
          }}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  );
}
