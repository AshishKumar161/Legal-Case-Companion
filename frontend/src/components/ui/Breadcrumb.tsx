"use client";

import React from "react";
import Link from "next/link";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbProps {
  items: BreadcrumbItem[];
  className?: string;
  style?: React.CSSProperties;
}

export function Breadcrumb({ items, className, style }: BreadcrumbProps) {
  if (!items || items.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className={className} style={{ ...style }}>
      <ol
        style={{
          display: "flex",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "8px",
          listStyle: "none",
          padding: 0,
          margin: 0,
          fontSize: "var(--font-size-xs, 12px)",
          color: "var(--text-muted, #64748b)",
        }}
      >
        {items.map((item, idx) => {
          const isLast = idx === items.length - 1;

          return (
            <li
              key={idx}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              {item.href && !isLast ? (
                <Link
                  href={item.href}
                  style={{
                    color: "var(--text-secondary, #94a3b8)",
                    textDecoration: "none",
                    transition: "var(--transition-fast, 0.15s ease)",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.color = "var(--text-primary, #f8fafc)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.color = "var(--text-secondary, #94a3b8)")
                  }
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  aria-current={isLast ? "page" : undefined}
                  style={{
                    color: isLast ? "var(--text-primary, #f8fafc)" : "inherit",
                    fontWeight: isLast ? 600 : 400,
                  }}
                >
                  {item.label}
                </span>
              )}

              {!isLast && (
                <span style={{ color: "rgba(255, 255, 255, 0.2)" }} aria-hidden="true">
                  /
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
