"use client";

import React, { forwardRef, useId } from "react";

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      label,
      error,
      helperText,
      id,
      required,
      disabled,
      rows = 4,
      style,
      className,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const textareaId = id || generatedId;
    const errorId = `${textareaId}-error`;
    const helperId = `${textareaId}-helper`;

    const describedBy = error
      ? errorId
      : helperText
      ? helperId
      : undefined;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "6px", width: "100%" }}>
        {label && (
          <label
            htmlFor={textareaId}
            style={{
              fontSize: "var(--font-size-xs, 12px)",
              fontWeight: 600,
              color: error ? "var(--urgent, #EF4444)" : "var(--text-secondary, #94a3b8)",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              display: "flex",
              alignItems: "center",
              gap: "4px",
            }}
          >
            {label}
            {required && (
              <span style={{ color: "var(--urgent, #EF4444)" }} aria-hidden="true">
                *
              </span>
            )}
          </label>
        )}

        <textarea
          ref={ref}
          id={textareaId}
          rows={rows}
          required={required}
          disabled={disabled}
          aria-invalid={!!error}
          aria-describedby={describedBy}
          style={{
            width: "100%",
            background: "var(--surface-base, #07090E)",
            border: `1px solid ${
              error
                ? "var(--urgent, #EF4444)"
                : "var(--border-subtle, rgba(255, 255, 255, 0.08))"
            }`,
            borderRadius: "var(--radius-md, 8px)",
            padding: "12px 14px",
            color: "var(--text-primary, #f8fafc)",
            fontSize: "var(--font-size-sm, 14px)",
            fontFamily: "var(--font-sans, sans-serif)",
            outline: "none",
            resize: "vertical",
            lineHeight: 1.5,
            cursor: disabled ? "not-allowed" : "text",
            opacity: disabled ? 0.5 : 1,
            ...style,
          }}
          className={className}
          {...props}
        />

        {error && (
          <span
            id={errorId}
            role="alert"
            style={{
              fontSize: "var(--font-size-xs, 12px)",
              color: "var(--urgent, #EF4444)",
              fontWeight: 500,
            }}
          >
            {error}
          </span>
        )}

        {!error && helperText && (
          <span
            id={helperId}
            style={{
              fontSize: "var(--font-size-xs, 12px)",
              color: "var(--text-muted, #64748b)",
            }}
          >
            {helperText}
          </span>
        )}
      </div>
    );
  }
);

Textarea.displayName = "Textarea";
