"use client";

import React, { forwardRef } from "react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "tertiary" | "outline" | "ghost" | "danger" | "success";
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
        padding: "6px 14px",
        fontSize: "var(--font-size-xs, 13px)",
        minHeight: "36px",
        borderRadius: "var(--radius-md, 10px)",
      },
      md: {
        padding: "10px 18px",
        fontSize: "var(--font-size-sm, 14px)",
        minHeight: "44px", // Mobile touch target minimum
        borderRadius: "var(--radius-md, 10px)",
      },
      lg: {
        padding: "13px 24px",
        fontSize: "var(--font-size-base, 16px)",
        minHeight: "48px",
        borderRadius: "var(--radius-lg, 14px)",
      },
    };

    // Colors per variant
    const variantStyles: Record<string, React.CSSProperties> = {
      primary: {
        background: "var(--navy-primary, #17324D)",
        color: "#FFFFFF",
        border: "1px solid var(--navy-primary, #17324D)",
        boxShadow: "var(--shadow-sm)",
      },
      secondary: {
        background: "var(--surface-card, #FFFFFF)",
        color: "var(--text-primary, #17324D)",
        border: "1px solid var(--border-subtle, #D9E2EC)",
        boxShadow: "var(--shadow-sm)",
      },
      tertiary: {
        background: "transparent",
        color: "var(--blue-soft, #3B82B6)",
        border: "1px solid transparent",
        padding: "6px 10px",
      },
      outline: {
        background: "transparent",
        color: "var(--navy-primary, #17324D)",
        border: "1px solid var(--border-subtle, #D9E2EC)",
      },
      ghost: {
        background: "transparent",
        color: "var(--text-secondary, #52606D)",
        border: "1px solid transparent",
      },
      danger: {
        background: "var(--surface-card, #FFFFFF)",
        color: "var(--status-urgent, #C53030)",
        border: "1px solid var(--status-urgent, #C53030)",
      },
      success: {
        background: "rgba(47, 133, 90, 0.1)",
        color: "var(--status-success, #2F855A)",
        border: "1px solid rgba(47, 133, 90, 0.3)",
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
