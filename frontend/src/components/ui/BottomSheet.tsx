"use client";

import React, { useEffect } from "react";

export interface BottomSheetProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

export function BottomSheet({ isOpen, onClose, title, children }: BottomSheetProps) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1300,
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
      }}
      aria-modal="true"
      role="dialog"
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(16, 42, 67, 0.4)",
          backdropFilter: "blur(2px)",
          transition: "opacity 0.2s ease",
        }}
        aria-hidden="true"
      />

      {/* Sheet Container */}
      <div
        style={{
          position: "relative",
          zIndex: 1301,
          background: "var(--surface-card, #FFFFFF)",
          borderTopLeftRadius: "20px",
          borderTopRightRadius: "20px",
          padding: "16px 20px 32px",
          maxHeight: "85vh",
          overflowY: "auto",
          boxShadow: "0 -4px 24px rgba(0, 0, 0, 0.25)",
          animation: "lccSlideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        {/* Pull Indicator Bar */}
        <div
          style={{
            width: "36px",
            height: "4px",
            background: "var(--border-subtle, #D9E2EC)",
            borderRadius: "2px",
            margin: "0 auto 16px",
          }}
          aria-hidden="true"
        />

        {/* Title & Close */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "16px",
          }}
        >
          {title && (
            <h3
              style={{
                margin: 0,
                fontSize: "18px",
                fontWeight: 700,
                color: "var(--text-primary, #17212B)",
                fontFamily: "var(--font-display, sans-serif)",
              }}
            >
              {title}
            </h3>
          )}
          <button
            onClick={onClose}
            style={{
              padding: "8px",
              color: "var(--text-secondary, #52606D)",
              background: "transparent",
              border: "none",
              borderRadius: "50%",
              cursor: "pointer",
              marginLeft: "auto",
            }}
            aria-label="Close sheet"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Sheet Content */}
        <div>{children}</div>

        <style jsx>{`
          @keyframes lccSlideUp {
            from {
              transform: translateY(100%);
            }
            to {
              transform: translateY(0);
            }
          }
        `}</style>
      </div>
    </div>
  );
}
