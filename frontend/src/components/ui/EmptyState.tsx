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
  icon,
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
        background: "var(--surface-card, #FFFFFF)",
        border: "1px solid var(--border-subtle, #D9E2EC)",
        borderRadius: "var(--radius-lg, 14px)",
        padding: "48px 24px",
        textAlign: "center",
        maxWidth: "540px",
        margin: "0 auto",
        color: "var(--text-primary, #17212B)",
        boxShadow: "var(--shadow-sm)",
        ...style,
      }}
      className={className}
    >
      <div
        style={{
          width: "56px",
          height: "56px",
          margin: "0 auto 16px",
          borderRadius: "var(--radius-lg, 14px)",
          background: "var(--surface-subtle, #EAF4FB)",
          border: "1px solid rgba(59, 130, 182, 0.2)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--navy-primary, #17324D)",
        }}
        aria-hidden="true"
      >
        {icon || (
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="8" y1="13" x2="16" y2="13" />
            <line x1="8" y1="17" x2="14" y2="17" />
          </svg>
        )}
      </div>

      <h3
        style={{
          fontSize: "var(--font-size-lg, 18px)",
          fontWeight: 600,
          color: "var(--text-primary, #17212B)",
          fontFamily: "var(--font-display, sans-serif)",
          marginBottom: "8px",
        }}
      >
        {title}
      </h3>

      <p
        style={{
          color: "var(--text-secondary, #52606D)",
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
