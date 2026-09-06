"use client";

import React, { forwardRef, useId } from "react";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  error?: string;
  helperText?: string;
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      label,
      options,
      error,
      helperText,
      placeholder,
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
    const selectId = id || generatedId;
    const errorId = `${selectId}-error`;
    const helperId = `${selectId}-helper`;

    const describedBy = error
      ? errorId
      : helperText
      ? helperId
      : undefined;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "6px", width: "100%" }}>
        {label && (
          <label
            htmlFor={selectId}
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

        <div style={{ position: "relative", width: "100%" }}>
          <select
            ref={ref}
            id={selectId}
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
              padding: "10px 36px 10px 14px",
              color: "var(--text-primary, #f8fafc)",
              fontSize: "var(--font-size-sm, 14px)",
              fontFamily: "var(--font-sans, sans-serif)",
              outline: "none",
              appearance: "none",
              cursor: disabled ? "not-allowed" : "pointer",
              opacity: disabled ? 0.5 : 1,
              ...style,
            }}
            className={className}
            {...props}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {options.map((opt) => (
              <option
                key={opt.value}
                value={opt.value}
                disabled={opt.disabled}
                style={{
                  background: "var(--surface-card, #0E121A)",
                  color: "var(--text-primary, #f8fafc)",
                }}
              >
                {opt.label}
              </option>
            ))}
          </select>

          <span
            style={{
              position: "absolute",
              right: "14px",
              top: "50%",
              transform: "translateY(-50%)",
              pointerEvents: "none",
              color: "var(--text-muted, #64748b)",
              fontSize: "12px",
            }}
            aria-hidden="true"
          >
            ▼
          </span>
        </div>

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

Select.displayName = "Select";
