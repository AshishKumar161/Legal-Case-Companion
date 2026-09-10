"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import {
  VerificationQueueResponse,
  VerificationQueueItem,
  AdvocateVerificationDetail,
} from "@/types";
import styles from "./verification.module.css";

export default function AdminVerificationPage() {
  const { user } = useAuth();

  const [items, setItems] = useState<VerificationQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Detail Modal State
  const [selectedAppId, setSelectedAppId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdvocateVerificationDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionSubmitting, setActionSubmitting] = useState(false);

  // Approval Form State
  const [sourceReference, setSourceReference] = useState("Roll Entry Reg. No. Verified");
  const [verificationSource, setVerificationSource] = useState("State Bar Council Official Roll Portal");
  const [verificationMethod, setVerificationMethod] = useState("STATE_BAR_COUNCIL_PORTAL_CHECK");
  const [reviewNotes, setReviewNotes] = useState("");

  // Rejection Form State
  const [rejectCategory, setRejectCategory] = useState("UNVERIFIABLE_RECORD");
  const [rejectReason, setRejectReason] = useState("");

  // Request Information Form State
  const [requestInfoExplanation, setRequestInfoExplanation] = useState("");

  // Revocation Form State
  const [revokeReason, setRevokeReason] = useState("");

  const [activeTab, setActiveTab] = useState<"DOCS" | "DECISION" | "HISTORY">("DOCS");

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url =
        statusFilter === "ALL"
          ? "/api/v1/verification/admin/queue?limit=50"
          : `/api/v1/verification/admin/queue?status_filter=${statusFilter}&limit=50`;

      const res = await apiClient.get<VerificationQueueResponse>(url);
      setItems(res.items || []);
      setTotal(res.total || 0);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load verification queue.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void fetchQueue();
  }, [fetchQueue]);

  const openDetail = async (id: string) => {
    setSelectedAppId(id);
    setLoadingDetail(true);
    setActionError(null);
    setActionSuccess(null);
    setActiveTab("DOCS");

    try {
      const res = await apiClient.get<AdvocateVerificationDetail>(
        `/api/v1/verification/admin/${id}`
      );
      setDetail(res);
      setVerificationSource(
        res.state_bar_council ? `${res.state_bar_council} Roll Records` : "State Bar Council Official Roll Portal"
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load verification detail.";
      setActionError(msg);
    } finally {
      setLoadingDetail(false);
    }
  };

  const closeDetail = () => {
    setSelectedAppId(null);
    setDetail(null);
    setActionError(null);
    setActionSuccess(null);
  };

  const handleStartReview = async () => {
    if (!detail) return;
    setActionSubmitting(true);
    setActionError(null);
    try {
      await apiClient.post(`/api/v1/verification/${detail.id}/start-review`, {});
      setActionSuccess("Review session initiated successfully.");
      await openDetail(detail.id);
      await fetchQueue();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to start review.";
      setActionError(msg);
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleApprove = async () => {
    if (!detail) return;
    setActionSubmitting(true);
    setActionError(null);
    try {
      await apiClient.post(`/api/v1/verification/${detail.id}/approve`, {
        verification_source: verificationSource.trim(),
        source_reference: sourceReference.trim(),
        verification_method: verificationMethod.trim(),
        notes: reviewNotes.trim() || undefined,
      });
      setActionSuccess("Advocate enrollment verified and approved.");
      await openDetail(detail.id);
      await fetchQueue();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Approval failed.";
      setActionError(msg);
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!detail) return;
    if (!rejectReason.trim()) {
      setActionError("Please provide a factual rejection reason.");
      return;
    }
    setActionSubmitting(true);
    setActionError(null);
    try {
      await apiClient.post(`/api/v1/verification/${detail.id}/reject`, {
        rejection_reason_category: rejectCategory,
        rejection_reason: rejectReason.trim(),
        notes: reviewNotes.trim() || undefined,
      });
      setActionSuccess("Advocate verification rejected.");
      await openDetail(detail.id);
      await fetchQueue();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Rejection failed.";
      setActionError(msg);
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleRequestInfo = async () => {
    if (!detail) return;
    if (!requestInfoExplanation.trim()) {
      setActionError("Please describe the requested clarification or document.");
      return;
    }
    setActionSubmitting(true);
    setActionError(null);
    try {
      await apiClient.post(`/api/v1/verification/${detail.id}/request-information`, {
        requested_documents: ["BAR_COUNCIL_ENROLLMENT_CERTIFICATE"],
        explanation: requestInfoExplanation.trim(),
        notes: reviewNotes.trim() || undefined,
      });
      setActionSuccess("Information request dispatched to advocate.");
      await openDetail(detail.id);
      await fetchQueue();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Request information failed.";
      setActionError(msg);
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleRevoke = async () => {
    if (!detail) return;
    if (!revokeReason.trim()) {
      setActionError("Please provide a reason for revoking verified status.");
      return;
    }
    setActionSubmitting(true);
    setActionError(null);
    try {
      await apiClient.post(`/api/v1/verification/${detail.id}/revoke`, {
        revocation_reason: revokeReason.trim(),
        notes: reviewNotes.trim() || undefined,
      });
      setActionSuccess("Verification revoked and public badge removed.");
      await openDetail(detail.id);
      await fetchQueue();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Revocation failed.";
      setActionError(msg);
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleViewDocument = async (docId: string) => {
    try {
      const res = await apiClient.get<{ download_url: string; expires_in_seconds: number }>(
        `/api/v1/verification/documents/${docId}/download-url`
      );
      if (res.download_url) {
        window.open(res.download_url, "_blank");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate secure document preview URL.";
      alert(msg);
    }
  };

  const isSelfReview = Boolean(
    detail?.user_id && user?.id && detail.user_id === user.id
  );

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <div className={styles.tag}>Compliance & Practice Integrity</div>
          <h1 className={styles.title}>Advocate Verification Queue</h1>
          <p className={styles.subtitle}>
            Deterministic human-controlled verification queue under Advocates Act 1961 & BCI Rule 36.
          </p>
        </div>

        <div className={styles.filterGroup}>
          <label style={{ fontSize: "12px", color: "var(--text-secondary, #94a3b8)", marginRight: "8px" }}>
            Filter Status:
          </label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className={styles.select}
          >
            <option value="ALL">All Applicants ({total})</option>
            <option value="PENDING">Pending Review</option>
            <option value="UNDER_REVIEW">Under Review</option>
            <option value="APPROVED">Approved / Verified</option>
            <option value="NEEDS_INFO">Needs Information</option>
            <option value="REJECTED">Rejected</option>
            <option value="REVOKED">Revoked</option>
          </select>
        </div>
      </div>

      {error && (
        <div className={styles.alertError}>
          {error}
        </div>
      )}

      {loading ? (
        <div className={styles.emptyState}>Loading verification queue...</div>
      ) : items.length === 0 ? (
        <div className={styles.emptyState}>
          No advocate applications matching status: <strong>{statusFilter}</strong>
        </div>
      ) : (
        <div className={styles.tableContainer}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Applicant</th>
                <th>Enrollment No.</th>
                <th>State Bar Council</th>
                <th>Status</th>
                <th>Documents</th>
                <th>Submitted Date</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <div style={{ fontWeight: 600, color: "#ffffff" }}>{item.full_name}</div>
                    <div style={{ fontSize: "11px", color: "var(--text-secondary, #94a3b8)" }}>
                      {item.email || "No email listed"}
                    </div>
                  </td>
                  <td>
                    <code style={{ fontSize: "12px", color: "#93c5fd" }}>{item.enrollment_number}</code>
                  </td>
                  <td style={{ fontSize: "13px", color: "#cbd5e1" }}>{item.state_bar_council}</td>
                  <td>
                    <span className={`${styles.badge} ${styles[`badge_${item.status}`]}`}>
                      {item.status}
                    </span>
                  </td>
                  <td>
                    <div style={{ fontSize: "12px", color: "#ffffff" }}>
                      {item.submitted_documents_count} submitted
                    </div>
                    {item.missing_documents.length > 0 && (
                      <div style={{ fontSize: "10px", color: "#f87171" }}>
                        Missing: {item.missing_documents.join(", ")}
                      </div>
                    )}
                  </td>
                  <td style={{ fontSize: "12px", color: "var(--text-secondary, #94a3b8)" }}>
                    {item.submitted_at ? new Date(item.submitted_at).toLocaleDateString() : "Draft"}
                  </td>
                  <td>
                    <button
                      type="button"
                      onClick={() => openDetail(item.id)}
                      className={styles.reviewBtn}
                    >
                      Inspect Dossier →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* DETAIL DRAWER / MODAL */}
      {selectedAppId && (
        <div className={styles.modalOverlay} onClick={closeDetail}>
          <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div>
                <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#ffffff", margin: 0 }}>
                  Advocate Dossier: {detail?.full_name || "Loading..."}
                </h2>
                <div style={{ fontSize: "12px", color: "var(--text-secondary, #94a3b8)", marginTop: "4px" }}>
                  Enrollment: <strong>{detail?.enrollment_number}</strong> • {detail?.state_bar_council}
                </div>
              </div>
              <button type="button" onClick={closeDetail} className={styles.closeBtn}>
                ✕
              </button>
            </div>

            {/* Self-Approval Protection Alert */}
            {isSelfReview && (
              <div className={styles.alertWarning}>
                ⛔ <strong>Self-Approval Prohibited:</strong> You are logged in as the applicant. As an advocate, you cannot review, approve, or revoke your own verification application.
              </div>
            )}

            {actionError && <div className={styles.alertError}>{actionError}</div>}
            {actionSuccess && <div className={styles.alertSuccess}>{actionSuccess}</div>}

            {loadingDetail ? (
              <div style={{ padding: "40px 0", textAlign: "center", color: "#94a3b8" }}>
                Loading application dossier...
              </div>
            ) : detail ? (
              <div>
                {/* Tabs */}
                <div className={styles.tabBar}>
                  <button
                    type="button"
                    className={`${styles.tabBtn} ${activeTab === "DOCS" ? styles.tabBtnActive : ""}`}
                    onClick={() => setActiveTab("DOCS")}
                  >
                    Documents ({detail.documents.length})
                  </button>
                  <button
                    type="button"
                    className={`${styles.tabBtn} ${activeTab === "DECISION" ? styles.tabBtnActive : ""}`}
                    onClick={() => setActiveTab("DECISION")}
                  >
                    Compliance Decision
                  </button>
                  <button
                    type="button"
                    className={`${styles.tabBtn} ${activeTab === "HISTORY" ? styles.tabBtnActive : ""}`}
                    onClick={() => setActiveTab("HISTORY")}
                  >
                    Review History ({detail.review_events.length})
                  </button>
                </div>

                {/* TAB 1: DOCUMENTS */}
                {activeTab === "DOCS" && (
                  <div style={{ padding: "16px 0" }}>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: "#ffffff", marginBottom: "10px" }}>
                      Uploaded Professional Credentials
                    </div>

                    {detail.documents.length === 0 ? (
                      <div style={{ fontSize: "13px", color: "#94a3b8" }}>
                        No professional documents uploaded yet.
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                        {detail.documents.map((doc) => (
                          <div key={doc.id} className={styles.docItem}>
                            <div>
                              <div style={{ fontSize: "13px", fontWeight: 600, color: "#ffffff" }}>
                                {doc.document_type}
                              </div>
                              <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>
                                File: {doc.original_filename} • {(doc.file_size / 1024).toFixed(1)} KB • SHA-256:{" "}
                                <code>{doc.sha256_hash.slice(0, 16)}...</code>
                              </div>
                              <div style={{ fontSize: "11px", color: "#34d399", marginTop: "4px" }}>
                                Magic Byte Scan: {doc.scan_status} • Verification: {doc.verification_status}
                              </div>
                            </div>
                            <div>
                              <button
                                type="button"
                                onClick={() => handleViewDocument(doc.id)}
                                className={styles.downloadBtn}
                              >
                                View Document (Signed URL)
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {detail.missing_documents.length > 0 && (
                      <div style={{ marginTop: "16px", padding: "12px", background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", borderRadius: "8px", color: "#fca5a5", fontSize: "12px" }}>
                        <strong>Missing Mandatory Credentials:</strong> {detail.missing_documents.join(", ")}
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 2: COMPLIANCE DECISION */}
                {activeTab === "DECISION" && (
                  <div style={{ padding: "16px 0" }}>
                    <div style={{ marginBottom: "16px", fontSize: "13px", color: "#cbd5e1" }}>
                      Current Status: <strong style={{ color: "#ffffff" }}>{detail.status}</strong>
                    </div>

                    {/* Start Review Button if still PENDING */}
                    {detail.status === "PENDING" && (
                      <div style={{ marginBottom: "20px" }}>
                        <button
                          type="button"
                          disabled={actionSubmitting || isSelfReview}
                          onClick={handleStartReview}
                          className={styles.actionBtnPrimary}
                        >
                          {actionSubmitting ? "Locking..." : "Lock & Start Review Session"}
                        </button>
                      </div>
                    )}

                    {/* Review Forms */}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                      {/* Approve Section */}
                      <div style={{ background: "rgba(16, 185, 129, 0.05)", border: "1px solid rgba(16, 185, 129, 0.2)", borderRadius: "8px", padding: "16px" }}>
                        <h4 style={{ margin: "0 0 10px 0", fontSize: "14px", color: "#34d399", fontWeight: 700 }}>
                          ✓ Approve Advocate Enrollment
                        </h4>
                        <div style={{ marginBottom: "10px" }}>
                          <label style={{ fontSize: "11px", color: "#94a3b8", display: "block" }}>
                            Verification Method
                          </label>
                          <select
                            value={verificationMethod}
                            onChange={(e) => setVerificationMethod(e.target.value)}
                            className={styles.select}
                          >
                            <option value="STATE_BAR_COUNCIL_PORTAL_CHECK">State Bar Council Portal Check</option>
                            <option value="OFFICIAL_ROLL_INSPECTION">Official Roll Physical Inspection</option>
                            <option value="AUTHORIZED_BAR_DIRECTORY">Authorized State Bar Directory</option>
                          </select>
                        </div>
                        <div style={{ marginBottom: "10px" }}>
                          <label style={{ fontSize: "11px", color: "#94a3b8", display: "block" }}>
                            Verification Source
                          </label>
                          <input
                            type="text"
                            value={verificationSource}
                            onChange={(e) => setVerificationSource(e.target.value)}
                            className={styles.input}
                          />
                        </div>
                        <div style={{ marginBottom: "10px" }}>
                          <label style={{ fontSize: "11px", color: "#94a3b8", display: "block" }}>
                            Source Reference (Portal URL / Roll Page / Reg ID)
                          </label>
                          <input
                            type="text"
                            value={sourceReference}
                            onChange={(e) => setSourceReference(e.target.value)}
                            className={styles.input}
                          />
                        </div>
                        <div style={{ marginBottom: "10px" }}>
                          <label style={{ fontSize: "11px", color: "#94a3b8", display: "block" }}>
                            Reviewer Notes / Findings (Internal Audit)
                          </label>
                          <input
                            type="text"
                            placeholder="Optional verification notes..."
                            value={reviewNotes}
                            onChange={(e) => setReviewNotes(e.target.value)}
                            className={styles.input}
                          />
                        </div>
                        <button
                          type="button"
                          disabled={actionSubmitting || isSelfReview || detail.status === "APPROVED"}
                          onClick={handleApprove}
                          className={styles.actionBtnApprove}
                        >
                          Confirm & Approve Verification
                        </button>
                      </div>

                      {/* Reject / Request Info Section */}
                      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                        {/* Request Clarification */}
                        <div style={{ background: "rgba(59, 130, 246, 0.05)", border: "1px solid rgba(59, 130, 246, 0.2)", borderRadius: "8px", padding: "16px" }}>
                          <h4 style={{ margin: "0 0 10px 0", fontSize: "14px", color: "#60a5fa", fontWeight: 700 }}>
                            ❓ Request Clarification / Document
                          </h4>
                          <input
                            type="text"
                            placeholder="Reason or document needed..."
                            value={requestInfoExplanation}
                            onChange={(e) => setRequestInfoExplanation(e.target.value)}
                            className={styles.input}
                            style={{ marginBottom: "10px" }}
                          />
                          <button
                            type="button"
                            disabled={actionSubmitting || isSelfReview}
                            onClick={handleRequestInfo}
                            className={styles.actionBtnInfo}
                          >
                            Dispatch Request to Advocate
                          </button>
                        </div>

                        {/* Reject */}
                        <div style={{ background: "rgba(239, 68, 68, 0.05)", border: "1px solid rgba(239, 68, 68, 0.2)", borderRadius: "8px", padding: "16px" }}>
                          <h4 style={{ margin: "0 0 10px 0", fontSize: "14px", color: "#f87171", fontWeight: 700 }}>
                            ✕ Reject Application
                          </h4>
                          <select
                            value={rejectCategory}
                            onChange={(e) => setRejectCategory(e.target.value)}
                            className={styles.select}
                            style={{ marginBottom: "8px" }}
                          >
                            <option value="UNVERIFIABLE_RECORD">Unverifiable Roll Record</option>
                            <option value="NAME_MISMATCH">Name Mismatch with Bar Roll</option>
                            <option value="INVALID_ENROLLMENT_FORMAT">Invalid Enrollment Number Format</option>
                            <option value="SUSPENDED_ENROLLMENT">Suspended Enrollment</option>
                            <option value="FRAUDULENT_DOCUMENT">Fraudulent / Manipulated Document</option>
                          </select>
                          <input
                            type="text"
                            placeholder="Rejection explanation..."
                            value={rejectReason}
                            onChange={(e) => setRejectReason(e.target.value)}
                            className={styles.input}
                            style={{ marginBottom: "10px" }}
                          />
                          <button
                            type="button"
                            disabled={actionSubmitting || isSelfReview || detail.status === "REJECTED"}
                            onClick={handleReject}
                            className={styles.actionBtnReject}
                          >
                            Reject Application
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Revoke Section if currently APPROVED */}
                    {detail.status === "APPROVED" && (
                      <div style={{ marginTop: "20px", padding: "16px", background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "8px" }}>
                        <h4 style={{ margin: "0 0 8px 0", fontSize: "14px", color: "#f87171" }}>
                          ⚠️ Revoke Verified Status
                        </h4>
                        <p style={{ fontSize: "12px", color: "#cbd5e1", margin: "0 0 10px 0" }}>
                          Revoking status will immediately strip the verified badge from the advocate’s public card and set account status to pending re-verification.
                        </p>
                        <div style={{ display: "flex", gap: "10px" }}>
                          <input
                            type="text"
                            placeholder="Reason for revocation..."
                            value={revokeReason}
                            onChange={(e) => setRevokeReason(e.target.value)}
                            className={styles.input}
                          />
                          <button
                            type="button"
                            disabled={actionSubmitting || isSelfReview}
                            onClick={handleRevoke}
                            className={styles.actionBtnReject}
                            style={{ whiteSpace: "nowrap" }}
                          >
                            Revoke Status
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* TAB 3: REVIEW HISTORY */}
                {activeTab === "HISTORY" && (
                  <div style={{ padding: "16px 0" }}>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: "#ffffff", marginBottom: "12px" }}>
                      Immutable Review Trail
                    </div>
                    {detail.review_events.length === 0 ? (
                      <div style={{ fontSize: "13px", color: "#94a3b8" }}>No review events recorded.</div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                        {detail.review_events.map((ev) => (
                          <div key={ev.id} className={styles.eventCard}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ fontSize: "12px", fontWeight: 700, color: "#93c5fd" }}>
                                {ev.decision} ({ev.from_status || "INITIAL"} → {ev.to_status})
                              </span>
                              <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                                {new Date(ev.created_at).toLocaleString()}
                              </span>
                            </div>
                            <div style={{ fontSize: "12px", color: "#cbd5e1", marginTop: "4px" }}>
                              {ev.notes || "No notes recorded"}
                            </div>
                            {ev.verification_source && (
                              <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>
                                Source: {ev.verification_source} • Ref: {ev.source_reference || "N/A"}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
