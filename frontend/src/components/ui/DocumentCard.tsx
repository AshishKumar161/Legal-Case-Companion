"use client";

import React from "react";
import { Badge } from "./Badge";

export interface DocumentCardProps {
  id: string;
  title: string;
  categoryLabel?: string;
  uploadedDate?: string;
  fileSize?: string;
  fileType?: string;
  onView?: () => void;
  onDownload?: () => void;
  className?: string;
}

export function DocumentCard({
  title,
  categoryLabel = "Document",
  uploadedDate,
  fileSize,
  fileType = "PDF",
  onView,
  onDownload,
  className,
}: DocumentCardProps) {
  const isPdf = fileType.toUpperCase().includes("PDF") || title.toLowerCase().endsWith(".pdf");

  return (
    <div
      style={{
        background: "var(--surface-card, #FFFFFF)",
        border: "1px solid var(--border-subtle, #D9E2EC)",
        borderRadius: "var(--radius-lg, 14px)",
        padding: "16px 20px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
        boxShadow: "var(--shadow-sm)",
        transition: "all var(--transition-fast, 0.15s ease)",
      }}
      className={className}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "14px", minWidth: 0, flex: 1 }}>
        {/* Document Icon */}
        <div
          style={{
            width: "42px",
            height: "42px",
            borderRadius: "var(--radius-md, 10px)",
            background: isPdf ? "rgba(197, 48, 48, 0.08)" : "var(--surface-subtle, #EAF4FB)",
            color: isPdf ? "var(--status-urgent, #C53030)" : "var(--navy-primary, #17324D)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            border: `1px solid ${isPdf ? "rgba(197, 48, 48, 0.2)" : "rgba(59, 130, 182, 0.2)"}`,
          }}
          aria-hidden="true"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="8" y1="13" x2="16" y2="13" />
            <line x1="8" y1="17" x2="14" y2="17" />
          </svg>
        </div>

        {/* Text details */}
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", marginBottom: "3px" }}>
            <h4
              style={{
                margin: 0,
                fontSize: "var(--font-size-base, 15px)",
                fontWeight: 600,
                color: "var(--text-primary, #17212B)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                maxWidth: "100%",
              }}
              title={title}
            >
              {title}
            </h4>
            {categoryLabel && (
              <Badge variant="primary" size="sm">
                {categoryLabel}
              </Badge>
            )}
          </div>

          <div
            style={{
              fontSize: "var(--font-size-xs, 13px)",
              color: "var(--text-secondary, #52606D)",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            {uploadedDate && <span>Uploaded {uploadedDate}</span>}
            {uploadedDate && fileSize && <span>·</span>}
            {fileSize && <span>{fileSize}</span>}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0 }}>
        {onView && (
          <button
            onClick={onView}
            className="btn btn-secondary"
            style={{
              minHeight: "38px",
              padding: "6px 14px",
              fontSize: "13px",
              cursor: "pointer",
            }}
            aria-label={`View ${title}`}
          >
            View
          </button>
        )}
        {onDownload && (
          <button
            onClick={onDownload}
            className="btn btn-secondary"
            style={{
              minHeight: "38px",
              padding: "6px 12px",
              fontSize: "13px",
              cursor: "pointer",
            }}
            title="Download document"
            aria-label={`Download ${title}`}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
