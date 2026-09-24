"use client";

import React from "react";
import Link from "next/link";
import { Badge } from "./Badge";

export interface LawyerCardProps {
  id: string;
  name: string;
  verified?: boolean;
  practiceAreas: string[];
  experienceYears?: number;
  location?: string | null;
  languages?: string[];
  availability?: string | null;
  consultationFee?: number | null;
  avatarUrl?: string | null;
  matchExplanation?: string | null;
  onBook?: () => void;
  onViewProfile?: () => void;
  profileHref?: string;
  className?: string;
}

export function LawyerCard({
  id,
  name,
  verified = true,
  practiceAreas = [],
  experienceYears,
  location,
  languages = [],
  availability = "Available this week",
  consultationFee,
  avatarUrl,
  matchExplanation,
  onBook,
  onViewProfile,
  profileHref,
  className,
}: LawyerCardProps) {
  const targetHref = profileHref || `/lawyers/${id}`;
  const initials = name
    ? name
        .split(" ")
        .map((p) => p[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "AD";

  return (
    <div
      style={{
        background: "var(--surface-card, #FFFFFF)",
        border: "1px solid var(--border-subtle, #D9E2EC)",
        borderRadius: "var(--radius-lg, 14px)",
        padding: "22px 24px",
        boxShadow: "var(--shadow-sm)",
        display: "flex",
        flexDirection: "column",
        gap: "18px",
        transition: "all var(--transition-fast, 0.15s ease)",
      }}
      className={className}
    >
      {/* Header with Avatar, Name, Verified Badge & Location */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: "16px" }}>
        {/* Avatar */}
        <div
          style={{
            width: "52px",
            height: "52px",
            borderRadius: "var(--radius-md, 10px)",
            background: "var(--navy-primary, #17324D)",
            color: "#FFFFFF",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 700,
            fontSize: "18px",
            flexShrink: 0,
            boxShadow: "var(--shadow-sm)",
          }}
          aria-hidden="true"
        >
          {avatarUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={avatarUrl}
              alt={name}
              style={{ width: "100%", height: "100%", borderRadius: "inherit", objectFit: "cover" }}
            />
          ) : (
            <span>{initials}</span>
          )}
        </div>

        {/* Lawyer Meta */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", marginBottom: "2px" }}>
            <h3
              style={{
                margin: 0,
                fontSize: "var(--font-size-lg, 17px)",
                fontWeight: 700,
                color: "var(--text-primary, #17212B)",
                fontFamily: "var(--font-display, sans-serif)",
              }}
            >
              {name}
            </h3>
            {verified && (
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "var(--status-success, #2F855A)",
                  background: "rgba(47, 133, 90, 0.08)",
                  border: "1px solid rgba(47, 133, 90, 0.25)",
                  borderRadius: "9999px",
                  padding: "2px 8px",
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>Bar Verified</span>
              </span>
            )}
          </div>

          <p
            style={{
              margin: "2px 0 0 0",
              fontSize: "var(--font-size-xs, 13px)",
              color: "var(--text-secondary, #52606D)",
            }}
          >
            {[location, experienceYears ? `${experienceYears} yrs experience` : null]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      </div>

      {/* Practice areas */}
      {practiceAreas.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {practiceAreas.slice(0, 4).map((area, idx) => (
            <Badge key={idx} variant="primary" size="sm">
              {area}
            </Badge>
          ))}
          {practiceAreas.length > 4 && (
            <span style={{ fontSize: "12px", color: "var(--text-muted, #7B8794)", alignSelf: "center" }}>
              +{practiceAreas.length - 4} more
            </span>
          )}
        </div>
      )}

      {matchExplanation && (
        <div
          style={{
            fontSize: "12px",
            color: "var(--navy-primary, #17324D)",
            background: "var(--navy-50, #EAF4FB)",
            border: "1px solid var(--border-subtle, #D9E2EC)",
            padding: "4px 10px",
            borderRadius: "var(--radius-sm, 6px)",
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            width: "fit-content",
            fontWeight: 500,
          }}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>{matchExplanation}</span>
        </div>
      )}

      {/* Languages & Availability */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "var(--font-size-xs, 13px)",
          color: "var(--text-secondary, #52606D)",
          borderTop: "1px solid var(--border-subtle, #D9E2EC)",
          paddingTop: "12px",
        }}
      >
        <div>
          {languages.length > 0 ? (
            <span>Speaks {languages.join(", ")}{availability ? ` · ${availability}` : ""}</span>
          ) : (
            availability && <span>{availability}</span>
          )}
        </div>
        <div>
          {consultationFee !== undefined && consultationFee !== null && (
            <span style={{ fontWeight: 600, color: "var(--text-primary, #17212B)" }}>
              {consultationFee === 0 ? "Free initial talk" : `₹${consultationFee.toLocaleString("en-IN")} / session`}
            </span>
          )}
        </div>
      </div>

      {/* Card actions */}
      <div style={{ display: "flex", gap: "10px", marginTop: "auto" }}>
        {onViewProfile ? (
          <button
            onClick={onViewProfile}
            className="btn btn-secondary"
            style={{ flex: 1, minHeight: "42px", fontSize: "14px" }}
          >
            View profile
          </button>
        ) : (
          <Link
            href={targetHref}
            className="btn btn-secondary"
            style={{ flex: 1, minHeight: "42px", fontSize: "14px", textAlign: "center" }}
          >
            View profile
          </Link>
        )}

        {onBook ? (
          <button
            onClick={onBook}
            className="btn btn-primary"
            style={{ flex: 1, minHeight: "42px", fontSize: "14px" }}
          >
            Book consultation
          </button>
        ) : (
          <Link
            href={`/consultations/new?lawyerId=${id}`}
            className="btn btn-primary"
            style={{ flex: 1, minHeight: "42px", fontSize: "14px", textAlign: "center" }}
          >
            Book consultation
          </Link>
        )}
      </div>
    </div>
  );
}
