"use client";

import React, { useEffect, useId, useRef } from "react";

export interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  children: React.ReactNode;
  placement?: "right" | "left" | "bottom";
  width?: string;
  footer?: React.ReactNode;
}

export function Drawer({
  isOpen,
  onClose,
  title,
  children,
  placement = "right",
  width = "420px",
  footer,
}: DrawerProps) {
  const generatedId = useId();
  const titleId = `${generatedId}-drawer-title`;
  const drawerRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    if (!isOpen) return;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const placementStyles: Record<string, React.CSSProperties> = {
    right: {
      top: 0,
      bottom: 0,
      right: 0,
      width: `min(${width}, 100vw)`,
      borderLeft: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.12))",
    },
    left: {
      top: 0,
      bottom: 0,
      left: 0,
      width: `min(${width}, 100vw)`,
      borderRight: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.12))",
    },
    bottom: {
      left: 0,
      right: 0,
      bottom: 0,
      maxHeight: "85vh",
      borderTop: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.12))",
      borderTopLeftRadius: "var(--radius-xl, 16px)",
      borderTopRightRadius: "var(--radius-xl, 16px)",
    },
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.7)",
        backdropFilter: "blur(4px)",
        zIndex: "var(--z-modal, 1400)",
      }}
      onClick={onClose}
    >
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{
          position: "fixed",
          background: "var(--surface-elevated, #151A24)",
          boxShadow: "var(--shadow-xl)",
          display: "flex",
          flexDirection: "column",
          color: "var(--text-primary, #f8fafc)",
          overflow: "hidden",
          ...placementStyles[placement],
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div
          style={{
            padding: "18px 20px",
            borderBottom: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <h2
            id={titleId}
            style={{
              margin: 0,
              fontSize: "var(--font-size-base, 16px)",
              fontWeight: 700,
              fontFamily: "var(--font-display, sans-serif)",
            }}
          >
            {title}
          </h2>

          <button
            onClick={onClose}
            aria-label="Close drawer"
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
            }}
          >
            ✕
          </button>
        </div>

        {/* Drawer Body */}
        <div
          style={{
            padding: "20px",
            overflowY: "auto",
            flex: 1,
          }}
        >
          {children}
        </div>

        {/* Drawer Footer */}
        {footer && (
          <div
            style={{
              padding: "16px 20px",
              borderTop: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
              background: "var(--surface-card, #0E121A)",
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
