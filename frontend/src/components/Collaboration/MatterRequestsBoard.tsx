"use client";

import React, { useState } from "react";
import { MatterRequestItem, DocumentItem } from "@/types";
import { apiClient } from "@/api/client";

interface MatterRequestsBoardProps {
  caseId: string;
  requests: MatterRequestItem[];
  documents: DocumentItem[];
  userRole: string;
  onRefresh: () => void;
}

export function MatterRequestsBoard({
  caseId,
  requests,
  documents,
  userRole,
  onRefresh,
}: MatterRequestsBoardProps) {
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [submitModalRequest, setSubmitModalRequest] = useState<MatterRequestItem | null>(null);
  const [reviewModalRequest, setReviewModalRequest] = useState<MatterRequestItem | null>(null);

  // Creation form state
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newType, setNewType] = useState<"DOCUMENT_UPLOAD" | "INFORMATION_REQUEST" | "CONFIRMATION" | "REVIEW">("DOCUMENT_UPLOAD");
  const [newDueDate, setNewDueDate] = useState("");
  const [creating, setCreating] = useState(false);

  // Submission form state
  const [selectedDocId, setSelectedDocId] = useState("");
  const [submitNotes, setSubmitNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Review form state
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewing, setReviewing] = useState(false);

  const pendingRequests = requests.filter((r) => r.status === "PENDING");
  const submittedRequests = requests.filter((r) => r.status === "SUBMITTED");
  const reviewedRequests = requests.filter((r) => r.status === "REVIEWED");

  const handleCreateRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newDesc.trim()) return;
    setCreating(true);
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/collaboration/requests`, {
        title: newTitle.trim(),
        description: newDesc.trim(),
        request_type: newType,
        due_date: newDueDate ? new Date(newDueDate).toISOString() : null,
      });
      setNewTitle("");
      setNewDesc("");
      setNewDueDate("");
      setCreateModalOpen(false);
      onRefresh();
    } catch (err) {
      console.error("Create request failed:", err);
    } finally {
      setCreating(false);
    }
  };

  const handleSubmitResponse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!submitModalRequest) return;
    setSubmitting(true);
    try {
      await apiClient.post(
        `/api/v1/cases/${caseId}/collaboration/requests/${submitModalRequest.id}/submit`,
        {
          submitted_document_id: selectedDocId || null,
          response_notes: submitNotes.trim() || null,
        }
      );
      setSubmitModalRequest(null);
      setSelectedDocId("");
      setSubmitNotes("");
      onRefresh();
    } catch (err) {
      console.error("Submit request response failed:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReviewRequest = async (status: "REVIEWED" | "CANCELLED") => {
    if (!reviewModalRequest) return;
    setReviewing(true);
    try {
      await apiClient.post(
        `/api/v1/cases/${caseId}/collaboration/requests/${reviewModalRequest.id}/review`,
        {
          review_notes: reviewNotes.trim() || null,
          mark_status: status,
        }
      );
      setReviewModalRequest(null);
      setReviewNotes("");
      onRefresh();
    } catch (err) {
      console.error("Review request failed:", err);
    } finally {
      setReviewing(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Header Actions */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0 }}>
            Structured Matter Requests ({requests.length})
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
            Formal information, evidence submissions, and review obligations between counsel and clients.
          </p>
        </div>

        {userRole !== "VIEWER" && (
          <button
            onClick={() => setCreateModalOpen(true)}
            style={{
              padding: "8px 16px",
              background: "#3b82f6",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              fontSize: "12px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            + Request Document / Action
          </button>
        )}
      </div>

      {/* 3-Column Lifecycle Board */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "16px",
        }}
      >
        {/* PENDING COLUMN */}
        <div
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "16px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "12px", fontWeight: 700, color: "#f59e0b", letterSpacing: "0.04em" }}>
              ⏳ ATTENTION REQUIRED ({pendingRequests.length})
            </span>
          </div>

          {pendingRequests.length === 0 ? (
            <div
              style={{
                fontSize: "12px",
                color: "var(--text-muted)",
                padding: "16px 12px",
                textAlign: "center",
                background: "rgba(255, 255, 255, 0.02)",
                borderRadius: "6px",
                border: "1px dashed rgba(255, 255, 255, 0.08)",
                lineHeight: "1.5",
              }}
            >
              ✓ All required items have been submitted.
              <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "4px" }}>
                When counsel requests specific contracts, pleadings, or clarifications, they will appear here.
              </div>
            </div>
          ) : (
            pendingRequests.map((req) => (
              <div
                key={req.id}
                style={{
                  background: "#151923",
                  border: "1px solid #232838",
                  borderRadius: "6px",
                  padding: "14px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <span
                    style={{
                      fontSize: "10px",
                      fontWeight: 700,
                      padding: "2px 6px",
                      borderRadius: "4px",
                      background: "rgba(245, 158, 11, 0.15)",
                      color: "#f59e0b",
                    }}
                  >
                    {req.request_type}
                  </span>
                  {req.due_date && (
                    <span style={{ fontSize: "11px", color: "#ef4444", fontWeight: 600 }}>
                      Due: {new Date(req.due_date).toLocaleDateString("en-IN")}
                    </span>
                  )}
                </div>

                <div style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>{req.title}</div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary)", lineHeight: "1.4" }}>
                  {req.description}
                </div>

                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px" }}>
                  Requested by: <strong>{req.requesting_user_name}</strong>
                  {req.assigned_user_name && ` • For: ${req.assigned_user_name}`}
                </div>

                <button
                  onClick={() => setSubmitModalRequest(req)}
                  style={{
                    marginTop: "6px",
                    padding: "6px 12px",
                    background: "rgba(59, 130, 246, 0.15)",
                    border: "1px solid rgba(59, 130, 246, 0.3)",
                    borderRadius: "4px",
                    color: "#60a5fa",
                    fontSize: "11px",
                    fontWeight: 600,
                    cursor: "pointer",
                    alignSelf: "flex-start",
                  }}
                >
                  Submit Response / Upload →
                </button>
              </div>
            ))
          )}
        </div>

        {/* SUBMITTED COLUMN */}
        <div
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "16px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "12px", fontWeight: 700, color: "#3b82f6", letterSpacing: "0.04em" }}>
              📩 SUBMITTED / PENDING REVIEW ({submittedRequests.length})
            </span>
          </div>

          {submittedRequests.length === 0 ? (
            <div style={{ fontSize: "12px", color: "var(--text-muted)", padding: "12px 0", textAlign: "center" }}>
              No submissions awaiting review.
            </div>
          ) : (
            submittedRequests.map((req) => (
              <div
                key={req.id}
                style={{
                  background: "#151923",
                  border: "1px solid #232838",
                  borderRadius: "6px",
                  padding: "14px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                }}
              >
                <span
                  style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    padding: "2px 6px",
                    borderRadius: "4px",
                    background: "rgba(59, 130, 246, 0.15)",
                    color: "#60a5fa",
                    alignSelf: "flex-start",
                  }}
                >
                  SUBMITTED
                </span>

                <div style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>{req.title}</div>
                {req.submitted_document_title && (
                  <div
                    style={{
                      fontSize: "11px",
                      color: "#10b981",
                      padding: "4px 8px",
                      borderRadius: "4px",
                      background: "rgba(16, 185, 129, 0.1)",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    📄 {req.submitted_document_title} ({req.submitted_document_status || "SAFE"})
                  </div>
                )}
                {req.response_notes && (
                  <div style={{ fontSize: "12px", color: "var(--text-secondary)", fontStyle: "italic" }}>
                    &ldquo;{req.response_notes}&rdquo;
                  </div>
                )}

                <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  Submitted: {req.submitted_at ? new Date(req.submitted_at).toLocaleDateString("en-IN") : "Recently"}
                </div>

                {userRole !== "CLIENT" && (
                  <button
                    onClick={() => setReviewModalRequest(req)}
                    style={{
                      marginTop: "6px",
                      padding: "6px 12px",
                      background: "rgba(16, 185, 129, 0.15)",
                      border: "1px solid rgba(16, 185, 129, 0.3)",
                      borderRadius: "4px",
                      color: "#10b981",
                      fontSize: "11px",
                      fontWeight: 600,
                      cursor: "pointer",
                      alignSelf: "flex-start",
                    }}
                  >
                    Review & Complete →
                  </button>
                )}
              </div>
            ))
          )}
        </div>

        {/* REVIEWED COLUMN */}
        <div
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "16px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "12px", fontWeight: 700, color: "#10b981", letterSpacing: "0.04em" }}>
              ✓ ADMITTED & REVIEWED ({reviewedRequests.length})
            </span>
          </div>

          {reviewedRequests.length === 0 ? (
            <div style={{ fontSize: "12px", color: "var(--text-muted)", padding: "12px 0", textAlign: "center" }}>
              No completed requests yet.
            </div>
          ) : (
            reviewedRequests.slice(0, 5).map((req) => (
              <div
                key={req.id}
                style={{
                  background: "#131720",
                  border: "1px solid #1f2533",
                  borderRadius: "6px",
                  padding: "12px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                  opacity: 0.85,
                }}
              >
                <div style={{ fontSize: "13px", fontWeight: 600, color: "#e2e8f0" }}>{req.title}</div>
                {req.submitted_document_title && (
                  <div style={{ fontSize: "11px", color: "#64748b" }}>
                    Attached: {req.submitted_document_title}
                  </div>
                )}
                <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                  Approved by {req.reviewed_by_user_name || "Counsel"}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* CREATE REQUEST MODAL */}
      {createModalOpen && (
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
          onClick={() => setCreateModalOpen(false)}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "520px",
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0 }}>
              Create Formal Matter Request
            </h3>

            <form onSubmit={handleCreateRequest} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>
                  Request Title
                </label>
                <input
                  type="text"
                  placeholder="e.g. Upload Stamped Lease Agreement 2022"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "var(--surface-base)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "6px",
                    color: "#fff",
                    fontSize: "13px",
                  }}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>
                  Detailed Instructions / Reason
                </label>
                <textarea
                  rows={3}
                  placeholder="Specify legal purpose, specific annexures required, or questions to clarify..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "var(--surface-base)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "6px",
                    color: "#fff",
                    fontSize: "13px",
                  }}
                  required
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>
                    Request Type
                  </label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value as never)}
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "var(--surface-base)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "6px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                  >
                    <option value="DOCUMENT_UPLOAD">Document Upload</option>
                    <option value="INFORMATION_REQUEST">Information Request</option>
                    <option value="CONFIRMATION">Client Confirmation</option>
                    <option value="REVIEW">Draft Review</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>
                    Due Date (Optional)
                  </label>
                  <input
                    type="date"
                    value={newDueDate}
                    onChange={(e) => setNewDueDate(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "var(--surface-base)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "6px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "12px" }}>
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
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
                  disabled={creating}
                  style={{
                    padding: "8px 16px",
                    background: "#3b82f6",
                    border: "none",
                    borderRadius: "6px",
                    color: "#fff",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  {creating ? "Dispatching..." : "Send Request →"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* SUBMIT RESPONSE MODAL */}
      {submitModalRequest && (
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
          onClick={() => setSubmitModalRequest(null)}
        >
          <div
            style={{
              width: "100%",
              maxWidth: "500px",
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0 }}>
              Submit: {submitModalRequest.title}
            </h3>
            <p style={{ fontSize: "12px", color: "var(--text-secondary)", margin: 0 }}>
              {submitModalRequest.description}
            </p>

            <form onSubmit={handleSubmitResponse} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {submitModalRequest.request_type === "DOCUMENT_UPLOAD" && (
                <div>
                  <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>
                    Select Uploaded Evidence Document
                  </label>
                  <select
                    value={selectedDocId}
                    onChange={(e) => setSelectedDocId(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "var(--surface-base)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "6px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                  >
                    <option value="">-- Choose from Matter Documents Vault --</option>
                    {documents.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.filename} ({d.security_status})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>
                  Response Notes / Clarifications
                </label>
                <textarea
                  rows={3}
                  placeholder="Provide clarifying facts, reference page numbers, or explanations..."
                  value={submitNotes}
                  onChange={(e) => setSubmitNotes(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    background: "var(--surface-base)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "6px",
                    color: "#fff",
                    fontSize: "13px",
                  }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
                <button
                  type="button"
                  onClick={() => setSubmitModalRequest(null)}
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
                  disabled={submitting}
                  style={{
                    padding: "8px 16px",
                    background: "#10b981",
                    border: "none",
                    borderRadius: "6px",
                    color: "#fff",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  {submitting ? "Submitting..." : "Submit to Counsel →"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* REVIEW REQUEST MODAL */}
      {reviewModalRequest && (
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
          onClick={() => setReviewModalRequest(null)}
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
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0 }}>
              Review Matter Submission
            </h3>
            <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
              <strong>{reviewModalRequest.title}</strong>
              <div style={{ marginTop: "4px" }}>
                Submitted Document: {reviewModalRequest.submitted_document_title || "None"}
              </div>
              {reviewModalRequest.response_notes && (
                <div style={{ marginTop: "4px", fontStyle: "italic" }}>
                  &ldquo;{reviewModalRequest.response_notes}&rdquo;
                </div>
              )}
            </div>

            <div>
              <label style={{ fontSize: "12px", color: "var(--text-muted)", display: "block", marginBottom: "6px" }}>
                Counsel Review Notes (Optional)
              </label>
              <textarea
                rows={2}
                placeholder="Confirmation remarks or verification status..."
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  background: "var(--surface-base)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "6px",
                  color: "#fff",
                  fontSize: "13px",
                }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                onClick={() => setReviewModalRequest(null)}
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
                type="button"
                disabled={reviewing}
                onClick={() => handleReviewRequest("REVIEWED")}
                style={{
                  padding: "8px 16px",
                  background: "#10b981",
                  border: "none",
                  borderRadius: "6px",
                  color: "#fff",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {reviewing ? "Marking..." : "Approve & Complete ✓"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
