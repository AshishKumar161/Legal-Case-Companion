"use client";

import React, { useState } from "react";
import { apiClient } from "@/api/client";

interface DecisionRecordModalProps {
  caseId: string;
  isOpen: boolean;
  onClose: () => void;
  onDecisionLogged: () => void;
  suggestedTitle?: string;
  linkedEvidence?: string;
  linkedAuthority?: string;
}

export function DecisionRecordModal({
  caseId,
  isOpen,
  onClose,
  onDecisionLogged,
  suggestedTitle = "",
  linkedEvidence = "",
  linkedAuthority = "",
}: DecisionRecordModalProps) {
  const [title, setTitle] = useState(suggestedTitle);
  const [context, setContext] = useState("");
  const [rationale, setRationale] = useState("");
  const [evidence, setEvidence] = useState(linkedEvidence);
  const [authority, setAuthority] = useState(linkedAuthority);
  const [shareWithMatter, setShareWithMatter] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !rationale.trim()) return;

    setSubmitting(true);
    setError("");

    try {
      // Human decision serialized cleanly into CaseNote with [DECISION] identifier
      const structuredContent = `[HUMAN LEGAL DECISION]
Title: ${title.trim()}
Legal Context: ${context.trim() || "Not specified"}
Strategic Rationale: ${rationale.trim()}
Linked Evidence: ${evidence.trim() || "None"}
Linked Authority: ${authority.trim() || "None"}`;

      await apiClient.post(`/api/v1/cases/${caseId}/notes`, {
        title: `[DECISION] ${title.trim().slice(0, 40)}`,
        content: structuredContent,
        visibility: "SHARED",
      });

      // If counsel selected shareWithMatter, post a formal status update to matter communication stream
      if (shareWithMatter) {
        try {
          await apiClient.post(`/api/v1/cases/${caseId}/collaboration/messages`, {
            content: `**Formal Legal Decision Logged**: ${title.trim()}\n\n*Strategic Rationale*: ${rationale.trim()}${context.trim() ? `\n*Legal Context*: ${context.trim()}` : ""}`,
            message_type: "STATUS_UPDATE",
            is_counsel_only: false,
          });
        } catch {
          // Non-blocking for note recording
        }
      }

      onDecisionLogged();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record human legal decision.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "20px",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "580px",
          backgroundColor: "var(--surface-card)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
          boxShadow: "var(--shadow-xl)",
          padding: "24px",
          display: "flex",
          flexDirection: "column",
          gap: "18px",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div
              style={{
                fontSize: "11px",
                fontWeight: 700,
                color: "#10b981",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: "2px",
              }}
            >
              Formal Case Governance
            </div>
            <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)" }}>
              Log Human Legal Decision Record
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
              Records conscious legal strategy decisions. Human legal decisions supersede AI suggestions.
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              fontSize: "18px",
              padding: "4px",
            }}
          >
            ✕
          </button>
        </div>

        {error && (
          <div
            style={{
              padding: "8px 12px",
              borderRadius: "4px",
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#f87171",
              fontSize: "12px",
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "6px" }}>
              Decision Title *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Waive counter-claim under Arbitration Act s.11 in favor of immediate settlement..."
              required
              className="input-field"
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "6px" }}>
              Legal Controversy / Context
            </label>
            <input
              type="text"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="e.g. Risk of statutory limitation lapsing under Commercial Courts Act s.12A..."
              className="input-field"
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "6px" }}>
              Counsel Rationale & Strategic Justification *
            </label>
            <textarea
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              rows={3}
              placeholder="Explain the legal reasoning, client approval, and why this course of action was chosen over alternatives..."
              required
              className="input-field"
              style={{ resize: "vertical" }}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "6px" }}>
                Linked Case Evidence
              </label>
              <input
                type="text"
                value={evidence}
                onChange={(e) => setEvidence(e.target.value)}
                placeholder="e.g. Lease Agreement p.14, Notice dated 12/03"
                className="input-field"
              />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "6px" }}>
                Governing Indian Authority
              </label>
              <input
                type="text"
                value={authority}
                onChange={(e) => setAuthority(e.target.value)}
                placeholder="e.g. Limitation Act s.5, NI Act s.138"
                className="input-field"
              />
            </div>
          </div>

          <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "#e2e8f0", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={shareWithMatter}
              onChange={(e) => setShareWithMatter(e.target.checked)}
            />
            <span>Broadcast formal status update to Matter Workspace Communication Stream</span>
          </label>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
            <button
              type="button"
              onClick={onClose}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !title.trim() || !rationale.trim()}
              className="btn btn-primary"
            >
              {submitting ? "Preserving Record..." : "Log Decision Record ↗"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
