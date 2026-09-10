"use client";

import React, { useEffect, useId, useRef } from "react";

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}

export function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: ModalProps) {
  const generatedId = useId();
  const titleId = `${generatedId}-title`;
  const descId = `${generatedId}-desc`;
  const dialogRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Trap focus inside modal
  useEffect(() => {
    if (!isOpen) return;
    const originalStyle = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Focus the first focusable element
    const focusableElements = dialogRef.current?.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (focusableElements && focusableElements.length > 0) {
      focusableElements[0].focus();
    }

    return () => {
      document.body.style.overflow = originalStyle;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const sizeWidths: Record<string, string> = {
    sm: "420px",
    md: "540px",
    lg: "680px",
    xl: "860px",
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        zIndex: "var(--z-modal, 1400)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "16px",
      }}
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        style={{
          background: "var(--surface-elevated, #151A24)",
          border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.12))",
          borderRadius: "var(--radius-xl, 16px)",
          boxShadow: "var(--shadow-xl)",
          width: "100%",
          maxWidth: sizeWidths[size],
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          color: "var(--text-primary, #f8fafc)",
          position: "relative",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: "20px 24px",
            borderBottom: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "16px",
          }}
        >
          <div>
            <h2
              id={titleId}
              style={{
                margin: 0,
                fontSize: "var(--font-size-lg, 18px)",
                fontWeight: 700,
                color: "var(--text-primary, #f8fafc)",
                fontFamily: "var(--font-display, sans-serif)",
              }}
            >
              {title}
            </h2>
            {description && (
              <p
                id={descId}
                style={{
                  margin: "4px 0 0 0",
                  fontSize: "var(--font-size-xs, 12px)",
                  color: "var(--text-secondary, #94a3b8)",
                }}
              >
                {description}
              </p>
            )}
          </div>

          <button
            onClick={onClose}
            aria-label="Close dialog"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-secondary, #94a3b8)",
              fontSize: "18px",
              cursor: "pointer",
              padding: "4px 8px",
              borderRadius: "var(--radius-sm, 6px)",
              minHeight: "36px",
              minWidth: "36px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "var(--transition-fast, 0.15s ease)",
            }}
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div
          style={{
            padding: "20px 24px",
            overflowY: "auto",
            flex: 1,
          }}
        >
          {children}
        </div>

        {/* Modal Footer */}
        {footer && (
          <div
            style={{
              padding: "16px 24px",
              borderTop: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
              background: "var(--surface-card, #0E121A)",
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              gap: "12px",
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
