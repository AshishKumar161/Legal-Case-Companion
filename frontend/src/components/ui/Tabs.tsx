"use client";

import React, { useRef } from "react";

export interface TabItem {
  id: string;
  label: React.ReactNode;
  icon?: React.ReactNode;
  badge?: string | number;
  disabled?: boolean;
}

export interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  className?: string;
  style?: React.CSSProperties;
}

export function Tabs({ tabs, activeTab, onChange, className, style }: TabsProps) {
  const tabListRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    let nextIndex = index;
    if (e.key === "ArrowRight") {
      nextIndex = (index + 1) % tabs.length;
    } else if (e.key === "ArrowLeft") {
      nextIndex = (index - 1 + tabs.length) % tabs.length;
    } else if (e.key === "Home") {
      nextIndex = 0;
    } else if (e.key === "End") {
      nextIndex = tabs.length - 1;
    } else {
      return;
    }

    e.preventDefault();
    const nextTab = tabs[nextIndex];
    if (!nextTab.disabled) {
      onChange(nextTab.id);
      const buttons = tabListRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
      buttons?.[nextIndex]?.focus();
    }
  };

  return (
    <div
      ref={tabListRef}
      role="tablist"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "4px",
        borderBottom: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
        overflowX: "auto",
        scrollbarWidth: "none",
        ...style,
      }}
      className={className}
    >
      {tabs.map((tab, idx) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            aria-controls={`panel-${tab.id}`}
            id={`tab-${tab.id}`}
            tabIndex={isActive ? 0 : -1}
            disabled={tab.disabled}
            onClick={() => !tab.disabled && onChange(tab.id)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 16px",
              background: "transparent",
              border: "none",
              borderBottom: `2px solid ${
                isActive ? "var(--brand-primary, #6366f1)" : "transparent"
              }`,
              color: isActive
                ? "var(--text-primary, #f8fafc)"
                : "var(--text-secondary, #94a3b8)",
              fontSize: "var(--font-size-sm, 14px)",
              fontWeight: isActive ? 600 : 500,
              cursor: tab.disabled ? "not-allowed" : "pointer",
              opacity: tab.disabled ? 0.4 : 1,
              whiteSpace: "nowrap",
              minHeight: "44px", // Mobile touch target
              transition: "var(--transition-fast, 0.15s ease)",
            }}
          >
            {tab.icon && <span style={{ fontSize: "16px" }}>{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.badge !== undefined && (
              <span
                style={{
                  background: isActive
                    ? "rgba(99, 102, 241, 0.2)"
                    : "rgba(255, 255, 255, 0.06)",
                  color: isActive ? "#a5b4fc" : "#94a3b8",
                  padding: "1px 6px",
                  borderRadius: "var(--radius-full, 9999px)",
                  fontSize: "11px",
                  fontWeight: 600,
                }}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
