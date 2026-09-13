"use client";

import React, { useState } from "react";
import { apiClient } from "@/api/client";

interface PilotFeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function PilotFeedbackModal({ isOpen, onClose }: PilotFeedbackModalProps) {
  const [category, setCategory] = useState<"BUG" | "CONFUSING_UX" | "MISSING_CAPABILITY" | "AI_ISSUE" | "DOCUMENT_ISSUE" | "OTHER">("CONFUSING_UX");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) return;

    setSubmitting(true);
    setError("");

    try {
      await apiClient.post("/api/v1/feedback", {
        category,
        description: description.trim(),
        page_url: typeof window !== "undefined" ? window.location.pathname : "/",
      });
      setSubmitted(true);
      setTimeout(() => {
        setSubmitted(false);
        setDescription("");
        onClose();
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record feedback.";
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
        zIndex: 10000,
        padding: "20px",
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "480px",
          background: "var(--surface-card)",
          border: "1px solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
          padding: "24px",
          display: "flex",
          flexDirection: "column",
          gap: "16px",
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0 }}>
              Share Pilot Feedback & Friction
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px" }}>
              Help us refine the legal workflow. Your feedback directly shapes the next release.
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
              cursor: "pointer",
              fontSize: "16px",
            }}
          >
            ✕
          </button>
        </div>

        {submitted ? (
          <div
            style={{
              padding: "20px",
              textAlign: "center",
              color: "#10b981",
              background: "rgba(16, 185, 129, 0.1)",
              borderRadius: "6px",
              fontSize: "14px",
              fontWeight: 600,
            }}
          >
            ✓ Thank you! Feedback recorded for product team review.
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            {error && (
              <div
                style={{
                  padding: "8px 12px",
                  borderRadius: "6px",
                  background: "rgba(239, 68, 68, 0.15)",
                  color: "#f87171",
                  fontSize: "12px",
                }}
              >
                {error}
              </div>
            )}

            <div>
              <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>
                Feedback Category
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as never)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--surface-base)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "6px",
                  color: "#fff",
                  fontSize: "13px",
                }}
              >
                <option value="CONFUSING_UX">Confusing or Unclear Workflow</option>
                <option value="BUG">Software Defect or UI Glitch</option>
                <option value="AI_ISSUE">AI Grounding or Legal Accuracy Concern</option>
                <option value="DOCUMENT_ISSUE">Document / Evidence Processing Issue</option>
                <option value="MISSING_CAPABILITY">Missing Legal Feature / Capability</option>
                <option value="OTHER">General Feedback</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>
                Description & Observations
              </label>
              <textarea
                rows={4}
                placeholder="What occurred, what felt confusing, or what was expected? (Do not include sensitive case evidence or secret client details)"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  background: "var(--surface-base)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "6px",
                  color: "#fff",
                  fontSize: "13px",
                  resize: "vertical",
                }}
                required
              />
            </div>

            <div
              style={{
                fontSize: "11px",
                color: "var(--text-muted)",
                background: "rgba(255, 255, 255, 0.03)",
                padding: "8px 12px",
                borderRadius: "4px",
                border: "1px solid rgba(255, 255, 255, 0.06)",
              }}
            >
              🔒 <strong>Privacy Assurance</strong>: Submissions do not capture case evidence text, privileged documents, or confidential client records.
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "4px" }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  padding: "8px 14px",
                  background: "transparent",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "6px",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !description.trim()}
                style={{
                  padding: "8px 16px",
                  background: "#3b82f6",
                  color: "#fff",
                  border: "none",
                  borderRadius: "6px",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {submitting ? "Sending..." : "Submit Feedback →"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
