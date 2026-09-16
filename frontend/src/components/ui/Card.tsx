"use client";

import React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "elevated" | "subtle" | "interactive";
  padding?: "none" | "sm" | "md" | "lg";
}

export function Card({
  variant = "default",
  padding = "md",
  children,
  style,
  className,
  ...props
}: CardProps) {
  const paddingStyles: Record<string, string> = {
    none: "0",
    sm: "12px",
    md: "20px",
    lg: "24px",
  };

  const variantStyles: Record<string, React.CSSProperties> = {
    default: {
      background: "var(--surface-card, #FFFFFF)",
      border: "1px solid var(--border-subtle, #D9E2EC)",
      boxShadow: "var(--shadow-sm)",
    },
    elevated: {
      background: "var(--surface-elevated, #FFFFFF)",
      border: "1px solid var(--border-subtle, #D9E2EC)",
      boxShadow: "var(--shadow-md)",
    },
    subtle: {
      background: "var(--surface-subtle, #EAF4FB)",
      border: "1px solid rgba(59, 130, 182, 0.2)",
    },
    interactive: {
      background: "var(--surface-card, #FFFFFF)",
      border: "1px solid var(--border-subtle, #D9E2EC)",
      boxShadow: "var(--shadow-sm)",
      cursor: "pointer",
      transition: "all var(--transition-fast, 0.15s ease)",
    },
  };

  return (
    <div
      style={{
        borderRadius: "var(--radius-lg, 14px)",
        padding: paddingStyles[padding],
        color: "var(--text-primary, #17212B)",
        ...variantStyles[variant],
        ...style,
      }}
      className={className}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  action,
  children,
  style,
  className,
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  children?: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: "16px",
        marginBottom: "16px",
        ...style,
      }}
      className={className}
    >
      <div>
        {title && (
          <h3
            style={{
              margin: 0,
              fontSize: "var(--font-size-base, 16px)",
              fontWeight: 600,
              color: "var(--text-primary, #17212B)",
              fontFamily: "var(--font-display, sans-serif)",
            }}
          >
            {title}
          </h3>
        )}
        {subtitle && (
          <p
            style={{
              margin: "4px 0 0 0",
              fontSize: "var(--font-size-xs, 13px)",
              color: "var(--text-secondary, #52606D)",
            }}
          >
            {subtitle}
          </p>
        )}
      </div>
      {action && <div>{action}</div>}
      {children}
    </div>
  );
}

export function CardBody({
  children,
  style,
  className,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}) {
  return (
    <div style={{ ...style }} className={className}>
      {children}
    </div>
  );
}

export function CardFooter({
  children,
  style,
  className,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}) {
  return (
    <div
      style={{
        marginTop: "16px",
        paddingTop: "14px",
        borderTop: "1px solid var(--border-subtle, #D9E2EC)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        ...style,
      }}
      className={className}
    >
      {children}
    </div>
  );
}

Card.Header = CardHeader;
Card.Body = CardBody;
Card.Footer = CardFooter;
