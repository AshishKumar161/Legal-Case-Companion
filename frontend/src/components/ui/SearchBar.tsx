"use client";

import React from "react";

export interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  style?: React.CSSProperties;
}

export function SearchBar({
  value,
  onChange,
  placeholder = "Search...",
  className,
  style,
}: SearchBarProps) {
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        width: "100%",
        ...style,
      }}
      className={className}
    >
      <span
        style={{
          position: "absolute",
          left: "14px",
          color: "var(--text-muted, #7B8794)",
          display: "flex",
          alignItems: "center",
          pointerEvents: "none",
        }}
        aria-hidden="true"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
      </span>

      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width: "100%",
          padding: "10px 38px 10px 42px",
          background: "var(--surface-card, #FFFFFF)",
          border: "1px solid var(--border-subtle, #D9E2EC)",
          borderRadius: "var(--radius-md, 10px)",
          fontSize: "14px",
          color: "var(--text-primary, #17212B)",
          fontFamily: "var(--font-sans, sans-serif)",
          outline: "none",
          transition: "all var(--transition-fast, 0.15s ease)",
          minHeight: "44px",
          boxShadow: "var(--shadow-sm)",
        }}
      />

      {value && (
        <button
          onClick={() => onChange("")}
          style={{
            position: "absolute",
            right: "12px",
            background: "transparent",
            border: "none",
            color: "var(--text-muted, #7B8794)",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            padding: "4px",
          }}
          aria-label="Clear search"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      )}
    </div>
  );
}
