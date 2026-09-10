"use client";

import React, { forwardRef, useId } from "react";

export interface RadioProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: React.ReactNode;
  description?: React.ReactNode;
}

export const Radio = forwardRef<HTMLInputElement, RadioProps>(
  ({ label, description, id, disabled, checked, onChange, style, className, ...props }, ref) => {
    const generatedId = useId();
    const radioId = id || generatedId;

    return (
      <label
        htmlFor={radioId}
        style={{
          display: "inline-flex",
          alignItems: "flex-start",
          gap: "10px",
          minHeight: "44px", // Mobile touch target
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.5 : 1,
          userSelect: "none",
          padding: "8px 0",
          ...style,
        }}
        className={className}
      >
        <div style={{ position: "relative", display: "flex", alignItems: "center", marginTop: "2px" }}>
          <input
            ref={ref}
            type="radio"
            id={radioId}
            disabled={disabled}
            checked={checked}
            onChange={onChange}
            style={{
              position: "absolute",
              opacity: 0,
              width: "20px",
              height: "20px",
              margin: 0,
              cursor: disabled ? "not-allowed" : "pointer",
            }}
            {...props}
          />
          <div
            style={{
              width: "20px",
              height: "20px",
              borderRadius: "50%",
              background: "var(--surface-base, #07090E)",
              border: `2px solid ${
                checked
                  ? "var(--brand-primary, #6366f1)"
                  : "var(--border-subtle, rgba(255, 255, 255, 0.2))"
              }`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "var(--transition-fast, 0.15s ease)",
            }}
            aria-hidden="true"
          >
            {checked && (
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: "var(--brand-primary, #6366f1)",
                }}
              />
            )}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <span
            style={{
              fontSize: "var(--font-size-sm, 14px)",
              color: "var(--text-primary, #f8fafc)",
              fontWeight: 500,
              lineHeight: 1.4,
            }}
          >
            {label}
          </span>
          {description && (
            <span
              style={{
                fontSize: "var(--font-size-xs, 12px)",
                color: "var(--text-muted, #64748b)",
                lineHeight: 1.4,
              }}
            >
              {description}
            </span>
          )}
        </div>
      </label>
    );
  }
);

Radio.displayName = "Radio";
