"use client";

import React, { useState } from "react";
import { LegalIssueItem, CaseFactItem } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";

interface EvidenceAuthorityMatrixProps {
  issues: LegalIssueItem[];
  facts: CaseFactItem[];
  caseId: string;
  onAskCopilot?: (prompt: string) => void;
}

export function EvidenceAuthorityMatrix({
  issues,
  facts,
  onAskCopilot,
}: EvidenceAuthorityMatrixProps) {
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(
    issues.length > 0 ? issues[0].id : null
  );

  const activeIssue = issues.find((i) => i.id === selectedIssueId) || issues[0];

  // Derive supporting facts based on supporting_fact_ids or textual similarity
  const supportingFacts = facts.filter((f) => {
    if (!activeIssue) return false;
    if (activeIssue.supporting_fact_ids && activeIssue.supporting_fact_ids.includes(f.id)) {
      return true;
    }
    // Fallback: Check if issue category matches fact category
    return (
      activeIssue.category &&
      f.category &&
      activeIssue.category.toUpperCase() === f.category.toUpperCase()
    );
  });

  if (issues.length === 0) {
    return (
      <div
        style={{
          padding: "40px 24px",
          textAlign: "center",
          color: "var(--text-muted)",
          background: "var(--surface-card)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
        }}
      >
        <div style={{ fontSize: "28px", marginBottom: "8px" }}>⚖</div>
        <h4 style={{ color: "var(--text-primary)", fontSize: "15px", marginBottom: "4px" }}>
          No Legal Issues Formally Identified
        </h4>
        <p style={{ fontSize: "13px", maxWidth: "460px", margin: "0 auto" }}>
          Upload case documents or execute a full intelligence refresh to detect actionable legal controversies and their governing Indian statutes.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 2fr",
        gap: "20px",
        alignItems: "start",
      }}
    >
      {/* Column 1: Identified Issues List */}
      <div
        style={{
          background: "var(--surface-card)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "10px",
        }}
      >
        <div
          style={{
            fontSize: "11px",
            fontWeight: 700,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            paddingBottom: "8px",
            borderBottom: "1px solid var(--border-subtle)",
          }}
        >
          Contested Legal Issues ({issues.length})
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "560px", overflowY: "auto" }}>
          {issues.map((iss) => {
            const isSelected = iss.id === activeIssue?.id;
            return (
              <div
                key={iss.id}
                onClick={() => setSelectedIssueId(iss.id)}
                style={{
                  padding: "12px 14px",
                  borderRadius: "var(--radius-sm)",
                  background: isSelected ? "rgba(79, 91, 247, 0.1)" : "var(--surface-subtle)",
                  border: isSelected ? "1px solid var(--accent-primary)" : "1px solid var(--border-subtle)",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" }}>
                  <span style={{ fontSize: "13px", fontWeight: 600, color: isSelected ? "#fff" : "var(--text-primary)" }}>
                    {iss.issue_text || iss.issue_title}
                  </span>
                  <StatusBadge status={iss.status} />
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                  Category: {iss.category || "General Controversy"}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Column 2: Dual-Source Evidence ↔ Authority Connector */}
      {activeIssue && (
        <div
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          {/* Active Issue Header */}
          <div style={{ borderBottom: "1px solid var(--border-subtle)", paddingBottom: "16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
              <div
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  color: "var(--accent-secondary)",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                }}
              >
                Selected Legal Issue
              </div>
              {onAskCopilot && (
                <button
                  onClick={() =>
                    onAskCopilot(
                      `Analyze our position regarding: "${activeIssue.issue_text || activeIssue.issue_title}". What evidence supports our claim and what authorities apply?`
                    )
                  }
                  className="btn btn-secondary"
                  style={{ fontSize: "11px", padding: "4px 10px" }}
                >
                  ✦ Inquire in Copilot
                </button>
              )}
            </div>
            <h3 style={{ fontSize: "18px", fontWeight: 700, color: "#fff", lineHeight: 1.4 }}>
              {activeIssue.issue_text || activeIssue.issue_title}
            </h3>
            {activeIssue.issue_description && (
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "6px", lineHeight: 1.5 }}>
                {activeIssue.issue_description}
              </p>
            )}
          </div>

          {/* Connected Case Evidence */}
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "12px",
                fontWeight: 700,
                color: "#60a5fa",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                marginBottom: "10px",
              }}
            >
              <span>📁</span> Connected Case Evidence ({supportingFacts.length})
            </div>

            {supportingFacts.length === 0 ? (
              <div
                style={{
                  padding: "16px",
                  borderRadius: "var(--radius-sm)",
                  background: "rgba(245, 158, 11, 0.06)",
                  border: "1px solid rgba(245, 158, 11, 0.2)",
                  fontSize: "12px",
                  color: "#fcd34d",
                }}
              >
                ⚠ Evidence Gap Detected: No verified document extract has been explicitly connected to this legal issue yet. Upload relevant contracts or agreements to ground this contention.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {supportingFacts.map((f) => (
                  <div
                    key={f.id}
                    style={{
                      padding: "12px 14px",
                      borderRadius: "var(--radius-sm)",
                      background: "var(--surface-subtle)",
                      border: "1px solid var(--border-subtle)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "4px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "12px", fontWeight: 600, color: "#93c5fd" }}>
                        📄 {f.source_filename || "Document Evidence Extract"}
                      </span>
                      <StatusBadge status={f.verification_status} />
                    </div>
                    <div style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: 1.5 }}>
                      {f.fact_text || f.fact_statement}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Governing Indian Legal Authorities */}
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "12px",
                fontWeight: 700,
                color: "#c4b5fd",
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                marginBottom: "10px",
              }}
            >
              <span>⚖</span> Governing Indian Statutory Authorities & Precedents
            </div>

            {activeIssue.relevant_authority_ids && activeIssue.relevant_authority_ids.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {activeIssue.relevant_authority_ids.map((authId, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: "12px 14px",
                      borderRadius: "var(--radius-sm)",
                      background: "rgba(109, 124, 255, 0.08)",
                      border: "1px solid rgba(109, 124, 255, 0.25)",
                    }}
                  >
                    <div style={{ fontWeight: 600, color: "#c4b5fd", fontSize: "13px" }}>
                      {authId}
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
                      Binding Statutory Authority • Supreme Court / High Court of India Jurisprudence
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div
                style={{
                  padding: "14px 16px",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--surface-subtle)",
                  border: "1px solid var(--border-subtle)",
                  fontSize: "12px",
                  color: "var(--text-secondary)",
                }}
              >
                No specific statutory provisions or precedents pinned yet. You can query governing statutory sections using the <b>Evidence Search</b> tab or Copilot Assistant.
              </div>
            )}
          </div>

          {/* Uncertainty Notice */}
          {activeIssue.uncertainties && activeIssue.uncertainties.length > 0 && (
            <div
              style={{
                padding: "12px 14px",
                borderRadius: "var(--radius-sm)",
                background: "rgba(239, 68, 68, 0.08)",
                border: "1px solid rgba(239, 68, 68, 0.25)",
              }}
            >
              <div style={{ fontSize: "11px", fontWeight: 700, color: "#ef4444", textTransform: "uppercase" }}>
                Legal Uncertainties & Vulnerabilities
              </div>
              <ul style={{ margin: "4px 0 0 16px", fontSize: "12px", color: "#fca5a5" }}>
                {activeIssue.uncertainties.map((u, i) => (
                  <li key={i}>{u}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
