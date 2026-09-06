"use client";

import React from "react";

export interface TableProps extends React.TableHTMLAttributes<HTMLTableElement> {
  headers?: React.ReactNode[];
  children: React.ReactNode;
  emptyState?: React.ReactNode;
  containerStyle?: React.CSSProperties;
}

export function Table({
  headers,
  children,
  emptyState,
  containerStyle,
  style,
  className,
  ...props
}: TableProps) {
  return (
    <div
      style={{
        width: "100%",
        overflowX: "auto",
        WebkitOverflowScrolling: "touch",
        border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
        borderRadius: "var(--radius-lg, 12px)",
        background: "var(--surface-card, #0E121A)",
        ...containerStyle,
      }}
    >
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          textAlign: "left",
          fontSize: "var(--font-size-sm, 14px)",
          color: "var(--text-primary, #f8fafc)",
          ...style,
        }}
        className={className}
        {...props}
      >
        {headers && headers.length > 0 && (
          <thead>
            <tr
              style={{
                borderBottom: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                background: "var(--surface-elevated, #151A24)",
              }}
            >
              {headers.map((h, i) => (
                <th
                  key={i}
                  scope="col"
                  style={{
                    padding: "12px 16px",
                    fontWeight: 600,
                    fontSize: "var(--font-size-xs, 12px)",
                    color: "var(--text-secondary, #94a3b8)",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>{children}</tbody>
      </table>

      {emptyState && (
        <div style={{ padding: "32px 16px", textAlign: "center" }}>
          {emptyState}
        </div>
      )}
    </div>
  );
}

export function TableRow({
  children,
  onClick,
  style,
  className,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  style?: React.CSSProperties;
  className?: string;
}) {
  return (
    <tr
      onClick={onClick}
      style={{
        borderBottom: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.06))",
        transition: "background var(--transition-fast, 0.15s ease)",
        cursor: onClick ? "pointer" : "default",
        ...style,
      }}
      className={className}
      onMouseEnter={(e) => {
        if (onClick) {
          e.currentTarget.style.backgroundColor = "var(--surface-hover, #1f273b)";
        }
      }}
      onMouseLeave={(e) => {
        if (onClick) {
          e.currentTarget.style.backgroundColor = "transparent";
        }
      }}
    >
      {children}
    </tr>
  );
}

export function TableCell({
  children,
  colSpan,
  style,
  className,
}: {
  children: React.ReactNode;
  colSpan?: number;
  style?: React.CSSProperties;
  className?: string;
}) {
  return (
    <td
      colSpan={colSpan}
      style={{
        padding: "14px 16px",
        verticalAlign: "middle",
        ...style,
      }}
      className={className}
    >
      {children}
    </td>
  );
}

Table.Row = TableRow;
Table.Cell = TableCell;
