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
      bg: "#F0F4F8",
      text: "#52606D",
      border: "#D9E2EC",
      dot: "#7B8794",
    },
    primary: {
      bg: "#EAF4FB",
      text: "#17324D",
      border: "rgba(59, 130, 182, 0.3)",
      dot: "#3B82B6",
    },
    success: {
      bg: "rgba(47, 133, 90, 0.08)",
      text: "#2F855A",
      border: "rgba(47, 133, 90, 0.25)",
      dot: "#2F855A",
    },
    warning: {
      bg: "rgba(194, 120, 3, 0.08)",
      text: "#C27803",
      border: "rgba(194, 120, 3, 0.25)",
      dot: "#C27803",
    },
    urgent: {
      bg: "rgba(197, 48, 48, 0.08)",
      text: "#C53030",
      border: "rgba(197, 48, 48, 0.25)",
      dot: "#C53030",
    },
    info: {
      bg: "#EAF4FB",
      text: "#3182CE",
      border: "rgba(49, 130, 206, 0.25)",
      dot: "#3182CE",
    },
    outline: {
      bg: "transparent",
      text: "#52606D",
      border: "#D9E2EC",
      dot: "#7B8794",
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
