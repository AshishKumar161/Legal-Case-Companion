"use client";

import React, { useState } from "react";
import { apiClient } from "@/api/client";

interface TaskComposerModalProps {
  caseId: string;
  isOpen: boolean;
  onClose: () => void;
  onTaskCreated: () => void;
  initialTitle?: string;
  initialDescription?: string;
  initialPriority?: "LOW" | "MEDIUM" | "HIGH" | "URGENT";
  sourceType?: string;
  sourceReference?: string;
}

export function TaskComposerModal({
  caseId,
  isOpen,
  onClose,
  onTaskCreated,
  initialTitle = "",
  initialDescription = "",
  initialPriority = "MEDIUM",
  sourceType = "MANUAL",
  sourceReference,
}: TaskComposerModalProps) {
  const [title, setTitle] = useState(initialTitle);
  const [description, setDescription] = useState(initialDescription);
  const [priority, setPriority] = useState<"LOW" | "MEDIUM" | "HIGH" | "URGENT">(initialPriority);
  const [dueDate, setDueDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setSubmitting(true);
    setError("");

    try {
      await apiClient.post(`/api/v1/cases/${caseId}/tasks`, {
        title: title.trim(),
        description: description.trim() || undefined,
        priority,
        due_date: dueDate ? new Date(dueDate).toISOString() : null,
        source_type: sourceType,
        source_reference: sourceReference || undefined,
        is_confirmed: true,
      });

      onTaskCreated();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record task obligation.";
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
          maxWidth: "540px",
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
        {/* Modal Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div
              style={{
                fontSize: "11px",
                fontWeight: 700,
                color: "var(--accent-secondary)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: "2px",
              }}
            >
              Workflow Command
            </div>
            <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)" }}>
              Create Case Task Obligation
            </h3>
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

        {sourceType !== "MANUAL" && (
          <div
            style={{
              padding: "8px 12px",
              borderRadius: "4px",
              background: "rgba(79, 91, 247, 0.1)",
              border: "1px solid rgba(79, 91, 247, 0.25)",
              fontSize: "12px",
              color: "#c4b5fd",
            }}
          >
            ✦ Source Provenance: <b>{sourceType}</b> {sourceReference ? `• Ref: ${sourceReference.slice(0, 16)}` : ""}
          </div>
        )}

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
              Task Title *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Procure original bank memorandum for statutory notice..."
              required
              className="input-field"
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "6px" }}>
              Operational Description / Justification
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Provide procedural instructions, relevant provisions, or client instructions..."
              className="input-field"
              style={{ resize: "vertical" }}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "6px" }}>
                Priority Level
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as any)}
                className="input-field"
              >
                <option value="LOW">Low (Routine)</option>
                <option value="MEDIUM">Medium (Standard)</option>
                <option value="HIGH">High (Urgent)</option>
                <option value="URGENT">Urgent (Procedural / Hearing Critical)</option>
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "6px" }}>
                Target Completion Due Date
              </label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="input-field"
              />
            </div>
          </div>

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
              disabled={submitting || !title.trim()}
              className="btn btn-primary"
            >
              {submitting ? "Assigning..." : "Assign Task Obligation ↗"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
