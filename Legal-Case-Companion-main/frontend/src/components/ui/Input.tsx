"use client";

import React, { forwardRef, useId } from "react";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leadingIcon?: React.ReactNode;
  trailingIcon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      helperText,
      leadingIcon,
      trailingIcon,
      id,
      required,
      disabled,
      style,
      className,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const inputId = id || generatedId;
    const errorId = `${inputId}-error`;
    const helperId = `${inputId}-helper`;

    const describedBy = error
      ? errorId
      : helperText
      ? helperId
      : undefined;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "6px", width: "100%" }}>
        {label && (
          <label
            htmlFor={inputId}
            style={{
              fontSize: "var(--font-size-xs, 12px)",
              fontWeight: 600,
              color: error ? "var(--urgent, #EF4444)" : "var(--text-secondary, #94a3b8)",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
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

        <div
          style={{
            position: "relative",
            display: "flex",
            alignItems: "center",
            width: "100%",
          }}
        >
          {leadingIcon && (
            <div
              style={{
                position: "absolute",
                left: "12px",
                display: "flex",
                alignItems: "center",
                pointerEvents: "none",
                color: "var(--text-muted, #64748b)",
              }}
              aria-hidden="true"
            >
              {leadingIcon}
            </div>
          )}

          <input
            ref={ref}
            id={inputId}
            required={required}
            disabled={disabled}
            aria-invalid={!!error}
            aria-describedby={describedBy}
            style={{
              width: "100%",
              minHeight: "44px", // Mobile touch target
              background: "var(--surface-base, #07090E)",
              border: `1px solid ${
                error
                  ? "var(--urgent, #EF4444)"
                  : "var(--border-subtle, rgba(255, 255, 255, 0.08))"
              }`,
              borderRadius: "var(--radius-md, 8px)",
              padding: `10px ${trailingIcon ? "38px" : "14px"} 10px ${
                leadingIcon ? "38px" : "14px"
              }`,
              color: "var(--text-primary, #f8fafc)",
              fontSize: "var(--font-size-sm, 14px)",
              fontFamily: "var(--font-sans, sans-serif)",
              outline: "none",
              transition: "var(--transition-fast, 0.15s ease)",
              opacity: disabled ? 0.5 : 1,
              cursor: disabled ? "not-allowed" : "text",
              ...style,
            }}
            className={className}
            {...props}
          />

          {trailingIcon && (
            <div
              style={{
                position: "absolute",
                right: "12px",
                display: "flex",
                alignItems: "center",
                color: "var(--text-muted, #64748b)",
              }}
            >
              {trailingIcon}
            </div>
          )}
        </div>

        {error && (
          <span
            id={errorId}
            role="alert"
            style={{
              fontSize: "var(--font-size-xs, 12px)",
              color: "var(--urgent, #EF4444)",
              fontWeight: 500,
              display: "flex",
              alignItems: "center",
              gap: "4px",
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

Input.displayName = "Input";
