"use client";

import React, { useState } from "react";
import { Button } from "./Button";

export interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  onGoBack?: () => void;
  supportEmail?: string;
  technicalError?: string;
  className?: string;
  style?: React.CSSProperties;
}

export function ErrorState({
  title = "Something went wrong while loading this information.",
  description = "We couldn't retrieve the latest case records. Please verify your connection or try again in a moment.",
  onRetry,
  onGoBack,
  supportEmail = "support@lcc.in",
  technicalError,
  className,
  style,
}: ErrorStateProps) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div
      role="alert"
      style={{
        background: "var(--surface-card, #0E121A)",
        border: "1px solid rgba(239, 68, 68, 0.25)",
        borderRadius: "var(--radius-lg, 12px)",
        padding: "40px 24px",
        textAlign: "center",
        maxWidth: "540px",
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
          background: "rgba(239, 68, 68, 0.12)",
          border: "1px solid rgba(239, 68, 68, 0.35)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "24px",
          color: "var(--urgent, #EF4444)",
        }}
        aria-hidden="true"
      >
        ⚠
      </div>

      <h3
        style={{
          fontSize: "var(--font-size-base, 16px)",
          fontWeight: 700,
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

      {/* Action Buttons: Try Again, Go Back, Contact Support */}
      <div
        style={{
          display: "flex",
          gap: "12px",
          justifyContent: "center",
          flexWrap: "wrap",
          marginBottom: "20px",
        }}
      >
        {onRetry && (
          <Button variant="primary" onClick={onRetry}>
            Try again
          </Button>
        )}
        {onGoBack ? (
          <Button variant="secondary" onClick={onGoBack}>
            Go back
          </Button>
        ) : (
          <Button
            variant="secondary"
            onClick={() => typeof window !== "undefined" && window.history.back()}
          >
            Go back
          </Button>
        )}
        <a
          href={`mailto:${supportEmail}?subject=Issue Report - Legal Case Companion`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "10px 18px",
            borderRadius: "var(--radius-md, 8px)",
            fontSize: "var(--font-size-sm, 14px)",
            fontWeight: 600,
            color: "var(--text-secondary, #94a3b8)",
            border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.1))",
            textDecoration: "none",
            minHeight: "44px",
          }}
        >
          Contact support
        </a>
      </div>

      {technicalError && (
        <div style={{ marginTop: "16px", textAlign: "left" }}>
          <button
            onClick={() => setShowDetails(!showDetails)}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted, #64748b)",
              fontSize: "var(--font-size-xs, 12px)",
              cursor: "pointer",
              padding: "4px 0",
              textDecoration: "underline",
            }}
          >
            {showDetails ? "Hide technical diagnostic" : "Show technical diagnostic"}
          </button>
          {showDetails && (
            <pre
              style={{
                marginTop: "8px",
                padding: "10px 12px",
                background: "var(--surface-base, #07090E)",
                border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                borderRadius: "var(--radius-sm, 6px)",
                fontSize: "11px",
                color: "#fca5a5",
                fontFamily: "var(--font-mono, monospace)",
                overflowX: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {technicalError}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
