"use client";

import React from "react";

export interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
  style?: React.CSSProperties;
}

export function Pagination({
  currentPage,
  totalPages,
  onPageChange,
  className,
  style,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const canGoPrev = currentPage > 1;
  const canGoNext = currentPage < totalPages;

  return (
    <nav
      aria-label="Pagination Navigation"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "8px",
        margin: "16px 0",
        ...style,
      }}
      className={className}
    >
      <button
        onClick={() => canGoPrev && onPageChange(currentPage - 1)}
        disabled={!canGoPrev}
        aria-label="Go to previous page"
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "44px", // Mobile touch target
          minWidth: "44px",
          padding: "8px 14px",
          borderRadius: "var(--radius-md, 8px)",
          background: "var(--surface-elevated, #151A24)",
          border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
          color: canGoPrev ? "var(--text-primary, #f8fafc)" : "var(--text-muted, #64748b)",
          cursor: canGoPrev ? "pointer" : "not-allowed",
          fontSize: "var(--font-size-sm, 14px)",
          opacity: canGoPrev ? 1 : 0.4,
          transition: "var(--transition-fast, 0.15s ease)",
        }}
      >
        ← Previous
      </button>

      <span
        style={{
          fontSize: "var(--font-size-xs, 12px)",
          color: "var(--text-secondary, #94a3b8)",
          padding: "0 8px",
        }}
      >
        Page <strong style={{ color: "var(--text-primary, #f8fafc)" }}>{currentPage}</strong> of{" "}
        <strong>{totalPages}</strong>
      </span>

      <button
        onClick={() => canGoNext && onPageChange(currentPage + 1)}
        disabled={!canGoNext}
        aria-label="Go to next page"
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "44px", // Mobile touch target
          minWidth: "44px",
          padding: "8px 14px",
          borderRadius: "var(--radius-md, 8px)",
          background: "var(--surface-elevated, #151A24)",
          border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
          color: canGoNext ? "var(--text-primary, #f8fafc)" : "var(--text-muted, #64748b)",
          cursor: canGoNext ? "pointer" : "not-allowed",
          fontSize: "var(--font-size-sm, 14px)",
          opacity: canGoNext ? 1 : 0.4,
          transition: "var(--transition-fast, 0.15s ease)",
        }}
      >
        Next →
      </button>
    </nav>
  );
}
