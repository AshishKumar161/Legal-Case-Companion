"use client";

import React, { forwardRef } from "react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger" | "success";
  size?: "sm" | "md" | "lg";
  isLoading?: boolean;
  leadingIcon?: React.ReactNode;
  trailingIcon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      isLoading = false,
      leadingIcon,
      trailingIcon,
      disabled,
      children,
      style,
      className,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || isLoading;

    // Base button dimensions per size
    const sizeStyles: Record<string, React.CSSProperties> = {
      sm: {
        padding: "6px 12px",
        fontSize: "var(--font-size-xs, 12px)",
        minHeight: "36px",
        borderRadius: "var(--radius-sm, 6px)",
      },
      md: {
        padding: "10px 18px",
        fontSize: "var(--font-size-sm, 14px)",
        minHeight: "44px", // Mobile touch target minimum
        borderRadius: "var(--radius-md, 8px)",
      },
      lg: {
        padding: "14px 24px",
        fontSize: "var(--font-size-base, 16px)",
        minHeight: "48px",
        borderRadius: "var(--radius-lg, 12px)",
      },
    };

    // Colors per variant
    const variantStyles: Record<string, React.CSSProperties> = {
      primary: {
        background: "var(--accent-gradient, linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%))",
        color: "#ffffff",
        border: "1px solid rgba(255, 255, 255, 0.16)",
        boxShadow: "var(--shadow-sm)",
      },
      secondary: {
        background: "var(--surface-elevated, #151A24)",
        color: "var(--text-primary, #f8fafc)",
        border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
      },
      outline: {
        background: "transparent",
        color: "var(--text-primary, #f8fafc)",
        border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.18))",
      },
      ghost: {
        background: "transparent",
        color: "var(--text-secondary, #94a3b8)",
        border: "1px solid transparent",
      },
      danger: {
        background: "rgba(239, 68, 68, 0.16)",
        color: "#fca5a5",
        border: "1px solid rgba(239, 68, 68, 0.4)",
      },
      success: {
        background: "rgba(16, 185, 129, 0.16)",
        color: "#6ee7b7",
        border: "1px solid rgba(16, 185, 129, 0.4)",
      },
    };

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        aria-busy={isLoading}
        aria-disabled={isDisabled}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "8px",
          fontFamily: "var(--font-sans, sans-serif)",
          fontWeight: 600,
          lineHeight: 1,
          cursor: isDisabled ? "not-allowed" : "pointer",
          opacity: isDisabled ? 0.5 : 1,
          transition: "var(--transition-fast, 0.15s ease)",
          userSelect: "none",
          whiteSpace: "nowrap",
          ...sizeStyles[size],
          ...variantStyles[variant],
          ...style,
        }}
        className={className}
        {...props}
      >
        {isLoading ? (
          <span
            style={{
              width: "16px",
              height: "16px",
              border: "2px solid rgba(255, 255, 255, 0.25)",
              borderTopColor: "currentColor",
              borderRadius: "50%",
              animation: "lccSpin 0.7s linear infinite",
              display: "inline-block",
            }}
            aria-hidden="true"
          />
        ) : (
          leadingIcon
        )}
        <span>{children}</span>
        {!isLoading && trailingIcon}
        <style jsx>{`
          @keyframes lccSpin {
            to {
              transform: rotate(360deg);
            }
          }
        `}</style>
      </button>
    );
  }
);

Button.displayName = "Button";
