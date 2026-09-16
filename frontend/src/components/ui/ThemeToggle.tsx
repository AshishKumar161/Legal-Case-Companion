"use client";

import React, { useEffect, useState } from "react";
import { useTheme } from "@/providers/ThemeProvider";
import { SunIcon, MoonIcon } from "@/components/ui/Icons";

interface ThemeToggleProps {
  className?: string;
  style?: React.CSSProperties;
  showLabel?: boolean;
}

export function ThemeToggle({ className, style, showLabel = false }: ThemeToggleProps) {
  const { resolvedTheme, toggleTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    // Avoid hydration mismatch by rendering a placeholder of identical dimensions
    return (
      <button
        type="button"
        aria-label="Toggle theme"
        disabled
        style={{
          width: "36px",
          height: "36px",
          borderRadius: "8px",
          border: "1px solid var(--border-subtle, #D9E2EC)",
          background: "var(--surface-card, #FFFFFF)",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "default",
          opacity: 0.6,
          ...style,
        }}
        className={className}
      >
        <span style={{ width: "16px", height: "16px" }} />
      </button>
    );
  }

  const isDark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      style={{
        width: showLabel ? "auto" : "36px",
        height: "36px",
        padding: showLabel ? "0 12px" : "0",
        borderRadius: "8px",
        border: "1px solid var(--border-subtle, #D9E2EC)",
        background: "var(--surface-card, #FFFFFF)",
        color: isDark ? "#CBD5E1" : "var(--navy-primary, #17324D)",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "8px",
        cursor: "pointer",
        transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
        boxShadow: "var(--shadow-sm)",
        flexShrink: 0,
        ...style,
      }}
      className={className}
    >
      <span
        style={{
          display: "inline-flex",
          transform: isDark ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform 0.3s ease",
        }}
      >
        {isDark ? (
          <SunIcon size={17} color="#CBD5E1" />
        ) : (
          <MoonIcon size={17} color="var(--navy-primary, #17324D)" />
        )}
      </span>
      {showLabel && (
        <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)" }}>
          {isDark ? "Light Mode" : "Dark Mode"}
        </span>
      )}
    </button>
  );
}
