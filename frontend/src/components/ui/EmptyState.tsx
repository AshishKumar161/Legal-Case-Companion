"use client";

import React from "react";
import { Button } from "./Button";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryActionLabel?: string;
  onSecondaryAction?: () => void;
  className?: string;
  style?: React.CSSProperties;
}

export function EmptyState({
  icon = "⚖",
  title,
  description,
  actionLabel,
  onAction,
  secondaryActionLabel,
  onSecondaryAction,
  className,
  style,
}: EmptyStateProps) {
  return (
    <div
      style={{
        background: "var(--surface-card, #0E121A)",
        border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
        borderRadius: "var(--radius-lg, 12px)",
        padding: "48px 24px",
        textAlign: "center",
        maxWidth: "560px",
        margin: "0 auto",
        color: "var(--text-primary, #f8fafc)",
        ...style,
      }}
      className={className}
    >
      <div
        style={{
          width: "56px",
          height: "56px",
          margin: "0 auto 16px",
          borderRadius: "var(--radius-lg, 12px)",
          background: "var(--surface-elevated, #151A24)",
          border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.12))",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "24px",
          color: "var(--brand-primary, #6366f1)",
        }}
        aria-hidden="true"
      >
        {icon}
      </div>

      <h3
        style={{
          fontSize: "var(--font-size-lg, 18px)",
          fontWeight: 600,
          color: "var(--text-primary, #f8fafc)",
          fontFamily: "var(--font-display, sans-serif)",
          marginBottom: "8px",
        }}
      >
        {title}
      </h3>

      <p
        style={{
          color: "var(--text-secondary, #94a3b8)",
          fontSize: "var(--font-size-sm, 14px)",
          lineHeight: 1.6,
          maxWidth: "440px",
          margin: "0 auto 24px",
        }}
      >
        {description}
      </p>

      {(actionLabel || secondaryActionLabel) && (
        <div
          style={{
            display: "flex",
            gap: "12px",
            justifyContent: "center",
            flexWrap: "wrap",
          }}
        >
          {actionLabel && onAction && (
            <Button variant="primary" onClick={onAction}>
              {actionLabel}
            </Button>
          )}
          {secondaryActionLabel && onSecondaryAction && (
            <Button variant="secondary" onClick={onSecondaryAction}>
              {secondaryActionLabel}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
