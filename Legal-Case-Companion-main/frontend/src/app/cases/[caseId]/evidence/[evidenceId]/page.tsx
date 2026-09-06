"use client";

import React, { use, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient } from "@/api/client";
import { EvidenceShareModal } from "@/components/Evidence/EvidenceShareModal";
import styles from "../evidence.module.css";

interface EvidenceVersionItem {
  id: string;
  version_number: number;
  uploaded_by_user_id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  scan_status: string;
  scan_details: string | null;
  integrity_status: string;
  last_verified_at: string | null;
  created_at: string;
}

interface EvidenceGrantItem {
  id: string;
  evidence_id: string;
  grantee_user_id: string;
  granted_by_user_id: string;
  access_level: string;
  created_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  revocation_reason: string | null;
}

interface EvidenceCustodyItem {
  id: string;
  evidence_id: string;
  version_id: string | null;
  actor_user_id: string | null;
  action: string;
  previous_event_id: string | null;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

interface CaseExhibitItem {
  id: string;
  case_id: string;
  evidence_id: string;
  version_id: string;
  hearing_id: string | null;
  exhibit_number: string;
  title: string;
  description: string | null;
  relevant_date: string | null;
  created_by_user_id: string;
  created_at: string;
  version_number?: number | null;
  hearing_purpose?: string | null;
  court_name?: string | null;
}

interface CaseHearingItem {
  id: string;
  purpose: string;
  court_name: string;
  hearing_at: string;
}

interface EvidenceDetail {
  id: string;
  case_id: string;
  created_by_user_id: string;
  current_version_id: string | null;
  title: string;
  description: string | null;
  category: string;
  status: string;
  sensitivity: string;
  original_filename: string;
  tags: string[];
  legal_hold: boolean;
  legal_hold_reason: string | null;
  retention_until: string | null;
  created_at: string;
  updated_at: string;
  exhibit_numbers: string[];
  current_version: EvidenceVersionItem | null;
  versions: EvidenceVersionItem[];
  grants: EvidenceGrantItem[];
  exhibits: CaseExhibitItem[];
}

export default function EvidenceDetailPage({
  params,
}: {
  params: Promise<{ caseId: string; evidenceId: string }>;
}) {
  const unwrappedParams = use(params);
  const { caseId, evidenceId } = unwrappedParams;
  const router = useRouter();

  const [evidence, setEvidence] = useState<EvidenceDetail | null>(null);
  const [custodyEvents, setCustodyEvents] = useState<EvidenceCustodyItem[]>([]);
  const [caseHearings, setCaseHearings] = useState<CaseHearingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Tabs: 'overview', 'versions', 'custody', 'grants', 'exhibits'
  const [activeTab, setActiveTab] = useState<"overview" | "versions" | "custody" | "grants" | "exhibits">("overview");

  // Inline Preview State
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewType, setPreviewType] = useState<string>("application/pdf");
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Integrity Verification State
  const [verifying, setVerifying] = useState(false);
  const [integrityResult, setIntegrityResult] = useState<{
    match: boolean;
    sha256_recorded: string;
    sha256_computed: string;
    verified_at: string;
  } | null>(null);

  // New Version Modal State
  const [versionModalOpen, setVersionModalOpen] = useState(false);
  const [uploadingVersion, setUploadingVersion] = useState(false);
  const [newVersionFile, setNewVersionFile] = useState<File | null>(null);
  const [versionError, setVersionError] = useState("");

  // Share Modal State
  const [shareModalOpen, setShareModalOpen] = useState(false);

  // Mark Exhibit Modal State
  const [exhibitModalOpen, setExhibitModalOpen] = useState(false);
  const [exhibitLoading, setExhibitLoading] = useState(false);
  const [exhibitError, setExhibitError] = useState("");
  const [exhibitTitle, setExhibitTitle] = useState("");
  const [exhibitNumber, setExhibitNumber] = useState("");
  const [exhibitDesc, setExhibitDesc] = useState("");
  const [exhibitVersionId, setExhibitVersionId] = useState("");
  const [exhibitHearingId, setExhibitHearingId] = useState("");
  const [exhibitDate, setExhibitDate] = useState("");

  // Tag Editor State
  const [newTagInput, setNewTagInput] = useState("");
  const [tagLoading, setTagLoading] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const [detailRes, custodyRes, hearingsRes] = await Promise.all([
        apiClient.get(`/api/v1/cases/${caseId}/evidence/${evidenceId}`) as Promise<EvidenceDetail>,
        apiClient.get(`/api/v1/cases/${caseId}/evidence/${evidenceId}/custody`) as Promise<EvidenceCustodyItem[]>,
        apiClient.get(`/api/v1/cases/${caseId}/hearings`).catch(() => []) as Promise<CaseHearingItem[]>,
      ]);
      setEvidence(detailRes);
      setCustodyEvents(custodyRes || []);
      setCaseHearings(hearingsRes || []);

      if (detailRes?.current_version_id) {
        setExhibitVersionId(detailRes.current_version_id);
      }
      if (detailRes?.title) {
        setExhibitTitle((prev) => prev || detailRes.title);
      }
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message || "Failed to load evidence details");
    } finally {
      setLoading(false);
    }
  }, [caseId, evidenceId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Load preview URL for overview tab
  const loadInlinePreview = useCallback(async (versionId?: string) => {
    try {
      setLoadingPreview(true);
      let url = `/api/v1/cases/${caseId}/evidence/${evidenceId}/view-url`;
      if (versionId) url += `?version_id=${versionId}`;
      const res = (await apiClient.get(url)) as { url: string; content_type: string };
      setPreviewUrl(res.url);
      setPreviewType(res.content_type || "application/pdf");
    } catch {
      setPreviewUrl(null);
    } finally {
      setLoadingPreview(false);
    }
  }, [caseId, evidenceId]);

  useEffect(() => {
    if (evidence?.current_version) {
      loadInlinePreview(evidence.current_version.id);
    }
  }, [evidence?.current_version, loadInlinePreview]);

  // Integrity Verification
  const handleVerifyIntegrity = async () => {
    try {
      setVerifying(true);
      const res = (await apiClient.post(
        `/api/v1/cases/${caseId}/evidence/${evidenceId}/verify-integrity`,
        {}
      )) as {
        match: boolean;
        sha256_recorded: string;
        sha256_computed: string;
        verified_at: string;
      };
      setIntegrityResult(res);
      await loadData();
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Integrity verification failed");
    } finally {
      setVerifying(false);
    }
  };

  // Download
  const handleDownload = async (versionId?: string) => {
    try {
      let url = `/api/v1/cases/${caseId}/evidence/${evidenceId}/download`;
      if (versionId) url += `?version_id=${versionId}`;
      const res = (await apiClient.get(url)) as { url: string };
      if (res?.url) {
        window.open(res.url, "_blank", "noopener,noreferrer");
      }
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Download failed");
    }
  };

  // Upload New Version
  const handleVersionUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newVersionFile) {
      setVersionError("Please select a file to upload as the new version");
      return;
    }

    try {
      setUploadingVersion(true);
      setVersionError("");

      const initRes = (await apiClient.post(
        `/api/v1/cases/${caseId}/evidence/${evidenceId}/versions/upload-init`,
        {
          original_filename: newVersionFile.name,
          content_type: newVersionFile.type || "application/pdf",
          size_bytes: newVersionFile.size,
        }
      )) as { version_id: string; upload_url: string };

      try {
        await fetch(initRes.upload_url, {
          method: "PUT",
          body: newVersionFile,
          headers: { "Content-Type": newVersionFile.type || "application/pdf" },
        });
      } catch (uploadErr) {
        console.warn("Storage PUT completed or simulated:", uploadErr);
      }

      await apiClient.post(
        `/api/v1/cases/${caseId}/evidence/${evidenceId}/versions/${initRes.version_id}/complete`,
        {}
      );

      setVersionModalOpen(false);
      setNewVersionFile(null);
      await loadData();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setVersionError(e?.message || "Failed to upload new version");
    } finally {
      setUploadingVersion(false);
    }
  };


  // Revoke Share
  const handleRevoke = async (targetUserId: string) => {
    if (!confirm("Are you sure you want to revoke this user's access? Access will terminate immediately.")) {
      return;
    }
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/evidence/${evidenceId}/revoke`, {
        target_user_id: targetUserId,
        reason: "Revoked by case manager via Evidence Locker UI",
      });
      await loadData();
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Revocation failed");
    }
  };

  // Create Case Exhibit
  const handleCreateExhibit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!exhibitTitle.trim()) {
      setExhibitError("Exhibit title is required");
      return;
    }

    try {
      setExhibitLoading(true);
      setExhibitError("");

      await apiClient.post(`/api/v1/cases/${caseId}/evidence/${evidenceId}/exhibits`, {
        title: exhibitTitle.trim(),
        exhibit_number: exhibitNumber.trim() || null,
        description: exhibitDesc.trim() || null,
        version_id: exhibitVersionId || null,
        hearing_id: exhibitHearingId || null,
        relevant_date: exhibitDate ? new Date(exhibitDate).toISOString() : null,
      });

      setExhibitModalOpen(false);
      setExhibitNumber("");
      setExhibitDesc("");
      await loadData();
      setActiveTab("exhibits");
    } catch (err: unknown) {
      const e = err as { message?: string };
      setExhibitError(e?.message || "Failed to mark exhibit");
    } finally {
      setExhibitLoading(false);
    }
  };

  // Tag Management
  const handleAddTag = async () => {
    if (!newTagInput.trim() || !evidence) return;
    const cleanTag = newTagInput.trim().toLowerCase();
    const currentTags = evidence.tags || [];
    if (currentTags.includes(cleanTag)) {
      setNewTagInput("");
      return;
    }
    if (currentTags.length >= 20) {
      alert("Maximum 20 tags permitted per evidence item");
      return;
    }

    try {
      setTagLoading(true);
      await apiClient.patch(`/api/v1/cases/${caseId}/evidence/${evidenceId}`, {
        tags: [...currentTags, cleanTag],
      });
      setNewTagInput("");
      await loadData();
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Failed to update tags");
    } finally {
      setTagLoading(false);
    }
  };

  const handleRemoveTag = async (tagToRemove: string) => {
    if (!evidence) return;
    try {
      setTagLoading(true);
      const updated = (evidence.tags || []).filter((t) => t !== tagToRemove);
      await apiClient.patch(`/api/v1/cases/${caseId}/evidence/${evidenceId}`, {
        tags: updated,
      });
      await loadData();
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Failed to remove tag");
    } finally {
      setTagLoading(false);
    }
  };

  // Legal Hold Toggle
  const handleToggleLegalHold = async () => {
    if (!evidence) return;
    const targetState = !evidence.legal_hold;
    const reason = targetState
      ? prompt("Enter legal justification for applying technical Legal Hold:")
      : "Legal hold lifted by authorized manager";
    if (targetState && !reason) return;

    try {
      await apiClient.post(`/api/v1/cases/${caseId}/evidence/${evidenceId}/legal-hold`, {
        legal_hold: targetState,
        reason: reason || null,
      });
      await loadData();
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Legal hold update failed");
    }
  };

  // Archive / Restore
  const handleToggleArchive = async () => {
    if (!evidence) return;
    const isArchived = evidence.status === "ARCHIVED";
    const endpoint = isArchived ? "restore" : "archive";
    if (!isArchived && !confirm("Archive this evidence item? It will be safely retained in the vault.")) {
      return;
    }
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/evidence/${evidenceId}/${endpoint}`, {});
      await loadData();
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || `Failed to ${endpoint} evidence`);
    }
  };

  // Soft Delete
  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this evidence item? This will be recorded permanently in the chain of custody.")) {
      return;
    }
    try {
      await apiClient.delete(`/api/v1/cases/${caseId}/evidence/${evidenceId}`);
      router.push(`/cases/${caseId}/evidence`);
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Deletion failed");
    }
  };

  if (loading) {
    return <div className={styles.container}>Loading evidence vault ledger...</div>;
  }

  if (error || !evidence) {
    return (
      <div className={styles.container}>
        <div style={{ color: "#f87171", padding: "20px" }}>{error || "Evidence item not found"}</div>
      </div>
    );
  }

  const curVer = evidence.current_version;

  return (
    <div className={styles.container}>
      {/* Breadcrumbs */}
      <nav className={styles.breadcrumbNav}>
        <Link href="/cases" className={styles.breadcrumbLink}>
          Cases
        </Link>
        <span className={styles.breadcrumbSep}>/</span>
        <Link href={`/cases/${caseId}`} className={styles.breadcrumbLink}>
          Case Workspace
        </Link>
        <span className={styles.breadcrumbSep}>/</span>
        <Link href={`/cases/${caseId}/evidence`} className={styles.breadcrumbLink}>
          Evidence Locker
        </Link>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{evidence.title}</span>
      </nav>

      {/* Hero Header */}
      <div className={styles.heroHeader}>
        <div className={styles.heroGlow} />
        <div>
          <div className={styles.titleArea}>
            <div className={styles.lockIconWrapper}>🔒</div>
            <div>
              <h1>{evidence.title}</h1>
              <div style={{ display: "flex", gap: "8px", marginTop: "8px", flexWrap: "wrap" }}>
                <span className={`${styles.pill} ${styles.pillCategory}`}>{evidence.category}</span>
                <span
                  className={`${styles.pill} ${
                    evidence.sensitivity === "PRIVILEGED"
                      ? styles.pillPrivileged
                      : evidence.sensitivity === "CONFIDENTIAL"
                      ? styles.pillConfidential
                      : styles.pillStandard
                  }`}
                >
                  {evidence.sensitivity}
                </span>
                <span
                  className={`${styles.pill} ${
                    evidence.status === "ACTIVE"
                      ? styles.pillActive
                      : evidence.status === "ARCHIVED"
                      ? styles.pillArchived
                      : styles.pillQuarantined
                  }`}
                >
                  {evidence.status}
                </span>
                {evidence.legal_hold && (
                  <span className={`${styles.pill} ${styles.pillHold}`}>⚖️ Legal Hold Active</span>
                )}
                {(evidence.exhibits || []).map((ex) => (
                  <span key={ex.id} className={styles.exhibitBadge}>
                    🏷️ {ex.exhibit_number}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button className={styles.primaryBtn} onClick={() => setExhibitModalOpen(true)}>
            🏷️ Mark as Exhibit
          </button>
          <button className={styles.secondaryBtn} onClick={() => setShareModalOpen(true)}>
            🔗 Share Document
          </button>
          <button className={styles.secondaryBtn} onClick={handleToggleLegalHold}>
            {evidence.legal_hold ? "Lift Legal Hold" : "Apply Legal Hold"}
          </button>
          <button className={styles.secondaryBtn} onClick={handleToggleArchive}>
            {evidence.status === "ARCHIVED" ? "♻️ Restore Item" : "📦 Archive Item"}
          </button>
          <button className={styles.dangerBtn} onClick={handleDelete}>
            Delete Item
          </button>
        </div>
      </div>

      {/* Structured Navigation Tabs */}
      <div className={styles.tabNav} role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === "overview"}
          className={`${styles.tabBtn} ${activeTab === "overview" ? styles.tabBtnActive : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          👁️ Overview & Preview
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "versions"}
          className={`${styles.tabBtn} ${activeTab === "versions" ? styles.tabBtnActive : ""}`}
          onClick={() => setActiveTab("versions")}
        >
          📄 Immutable Versions
          <span className={styles.tabBadgeCount}>{evidence.versions.length}</span>
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "exhibits"}
          className={`${styles.tabBtn} ${activeTab === "exhibits" ? styles.tabBtnActive : ""}`}
          onClick={() => setActiveTab("exhibits")}
        >
          🏷️ Court Exhibits
          <span className={styles.tabBadgeCount}>{(evidence.exhibits || []).length}</span>
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "grants"}
          className={`${styles.tabBtn} ${activeTab === "grants" ? styles.tabBtnActive : ""}`}
          onClick={() => setActiveTab("grants")}
        >
          👥 Sharing & Access
          <span className={styles.tabBadgeCount}>{evidence.grants.length}</span>
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "custody"}
          className={`${styles.tabBtn} ${activeTab === "custody" ? styles.tabBtnActive : ""}`}
          onClick={() => setActiveTab("custody")}
        >
          📜 Chain of Custody
          <span className={styles.tabBadgeCount}>{custodyEvents.length}</span>
        </button>
      </div>

      {/* Tab 1: Overview & Preview */}
      {activeTab === "overview" && (
        <div className={styles.detailGrid}>
          {/* Left: Metadata & Tags */}
          <div>
            <div className={styles.panel}>
              <div className={styles.panelTitle}>
                <span>Active Evidence File Details</span>
                {curVer && (
                  <button className={styles.primaryBtn} onClick={() => handleDownload(curVer.id)}>
                    📥 Download Verified File
                  </button>
                )}
              </div>

              {curVer ? (
                <div>
                  <div className={styles.metaGrid} style={{ marginBottom: "16px" }}>
                    <div className={styles.metaItem}>
                      <span className={styles.metaKey}>Filename</span>
                      <span className={styles.metaVal}>{curVer.original_filename}</span>
                    </div>
                    <div className={styles.metaItem}>
                      <span className={styles.metaKey}>File Size</span>
                      <span className={styles.metaVal}>{(curVer.size_bytes / 1024).toFixed(1)} KB</span>
                    </div>
                    <div className={styles.metaItem}>
                      <span className={styles.metaKey}>Content Type</span>
                      <span className={styles.metaVal}>{curVer.content_type}</span>
                    </div>
                    <div className={styles.metaItem}>
                      <span className={styles.metaKey}>Scan Status</span>
                      <span
                        className={styles.metaVal}
                        style={{
                          color: curVer.scan_status === "PASSED" ? "#34d399" : "#f87171",
                          fontWeight: 600,
                        }}
                      >
                        ✓ {curVer.scan_status}
                      </span>
                    </div>
                  </div>

                  <div style={{ marginBottom: "16px" }}>
                    <span className={styles.statLabel}>Cryptographic SHA-256 Digest:</span>
                    <div className={styles.hashBox} style={{ marginTop: "6px" }}>
                      <span>{curVer.sha256}</span>
                      <button
                        className={styles.secondaryBtn}
                        style={{ padding: "3px 8px", fontSize: "11px" }}
                        onClick={() => {
                          navigator.clipboard.writeText(curVer.sha256);
                          alert("SHA-256 hash copied to clipboard!");
                        }}
                      >
                        Copy
                      </button>
                    </div>
                  </div>

                  {/* Integrity Card */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "14px 18px",
                      background: "#08090d",
                      border: "1px solid #1f2434",
                      borderRadius: "10px",
                    }}
                  >
                    <div>
                      <div style={{ fontSize: "13px", fontWeight: 600, color: "#ffffff" }}>
                        Integrity Status:{" "}
                        <span
                          style={{
                            color:
                              curVer.integrity_status === "VERIFIED_MATCH"
                                ? "#34d399"
                                : curVer.integrity_status === "TAMPER_DETECTED"
                                ? "#f87171"
                                : "#94a3b8",
                          }}
                        >
                          {curVer.integrity_status}
                        </span>
                      </div>
                      <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                        Last checked:{" "}
                        {curVer.last_verified_at
                          ? new Date(curVer.last_verified_at).toLocaleString()
                          : "Never"}
                      </div>
                    </div>
                    <button
                      className={styles.secondaryBtn}
                      onClick={handleVerifyIntegrity}
                      disabled={verifying}
                    >
                      {verifying ? "Verifying..." : "⚡ Verify Integrity"}
                    </button>
                  </div>

                  {integrityResult && (
                    <div
                      style={{
                        marginTop: "12px",
                        padding: "12px 16px",
                        borderRadius: "8px",
                        background: integrityResult.match
                          ? "rgba(16, 185, 129, 0.12)"
                          : "rgba(239, 68, 68, 0.15)",
                        border: `1px solid ${
                          integrityResult.match ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.35)"
                        }`,
                        color: integrityResult.match ? "#34d399" : "#f87171",
                        fontSize: "13px",
                      }}
                    >
                      <strong>
                        {integrityResult.match
                          ? "✓ Cryptographic Integrity Verified"
                          : "⚠️ TAMPER DETECTED: Storage bytes do not match recorded hash!"}
                      </strong>
                      <div style={{ fontSize: "11px", marginTop: "4px", color: "#94a3b8" }}>
                        Recorded: {integrityResult.sha256_recorded}
                      </div>
                      <div style={{ fontSize: "11px", color: "#94a3b8" }}>
                        Computed: {integrityResult.sha256_computed}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className={styles.emptyState}>No version currently active.</div>
              )}
            </div>

            {/* Tag Management */}
            <div className={styles.panel}>
              <div className={styles.panelTitle}>
                <span>Metadata Tags ({(evidence.tags || []).length}/20)</span>
              </div>

              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginBottom: "16px" }}>
                {(evidence.tags || []).map((tag) => (
                  <span
                    key={tag}
                    className={styles.tagPill}
                    style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
                  >
                    #{tag}
                    <button
                      onClick={() => handleRemoveTag(tag)}
                      disabled={tagLoading}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#94a3b8",
                        cursor: "pointer",
                        padding: 0,
                        fontSize: "12px",
                      }}
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>

              <div style={{ display: "flex", gap: "8px" }}>
                <input
                  type="text"
                  className={styles.formInput}
                  placeholder="Add new tag (e.g. lease, audit)..."
                  value={newTagInput}
                  onChange={(e) => setNewTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddTag();
                    }
                  }}
                  style={{ flex: 1 }}
                />
                <button
                  className={styles.secondaryBtn}
                  onClick={handleAddTag}
                  disabled={tagLoading || !newTagInput.trim()}
                >
                  + Add Tag
                </button>
              </div>
            </div>
          </div>

          {/* Right: Embedded Safe Preview */}
          <div>
            <div className={styles.panel} style={{ minHeight: "440px", display: "flex", flexDirection: "column" }}>
              <div className={styles.panelTitle}>
                <span>Embedded File Preview</span>
                {curVer && (
                  <button
                    className={styles.secondaryBtn}
                    onClick={() => handleDownload(curVer.id)}
                  >
                    📥 Download
                  </button>
                )}
              </div>

              <div
                style={{
                  flex: 1,
                  background: "#08090d",
                  borderRadius: "10px",
                  border: "1px solid #1f2434",
                  overflow: "hidden",
                  minHeight: "380px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {loadingPreview ? (
                  <div className={styles.emptyState}>Loading preview bytes...</div>
                ) : !previewUrl ? (
                  <div className={styles.emptyState}>No preview available</div>
                ) : previewType === "application/pdf" ? (
                  <iframe
                    src={previewUrl}
                    title="Inline PDF Preview"
                    style={{ width: "100%", height: "420px", border: "none" }}
                    sandbox="allow-scripts allow-same-origin"
                  />
                ) : previewType.startsWith("image/") ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={previewUrl}
                    alt="Inline Preview"
                    style={{ maxWidth: "100%", maxHeight: "420px", objectFit: "contain" }}
                  />
                ) : (
                  <div className={styles.previewFallback}>
                    <p style={{ fontSize: "14px", color: "#ffffff", fontWeight: 600 }}>
                      Inline preview unavailable for {previewType}
                    </p>
                    <button
                      className={styles.primaryBtn}
                      style={{ marginTop: "12px" }}
                      onClick={() => handleDownload()}
                    >
                      📥 Download File
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Immutable Versions */}
      {activeTab === "versions" && (
        <div className={styles.panel}>
          <div className={styles.panelTitle}>
            <span>Immutable Version History ({evidence.versions.length})</span>
            <button className={styles.primaryBtn} onClick={() => setVersionModalOpen(true)}>
              + Deposit New Version
            </button>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {evidence.versions.map((ver) => (
              <div
                key={ver.id}
                style={{
                  padding: "16px 20px",
                  background: "#090a0f",
                  border: "1px solid #1a1e2b",
                  borderRadius: "12px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "12px",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontWeight: 700, color: "#ffffff", fontSize: "14px" }}>
                      Version {ver.version_number}
                    </span>
                    {ver.id === evidence.current_version_id && (
                      <span className={`${styles.pill} ${styles.pillActive}`}>Current Active</span>
                    )}
                    <span className={`${styles.pill} ${styles.pillStandard}`}>
                      {(ver.size_bytes / 1024).toFixed(1)} KB
                    </span>
                    <span
                      style={{
                        fontSize: "12px",
                        fontWeight: 600,
                        color: ver.scan_status === "PASSED" ? "#34d399" : "#f87171",
                      }}
                    >
                      ✓ {ver.scan_status}
                    </span>
                  </div>
                  <div style={{ fontSize: "12px", color: "#8c97ad", marginTop: "6px" }}>
                    Uploaded: {new Date(ver.created_at).toLocaleString()} · SHA-256:{" "}
                    <code style={{ color: "#38bdf8" }}>{ver.sha256}</code>
                  </div>
                </div>

                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    className={styles.secondaryBtn}
                    onClick={() => {
                      loadInlinePreview(ver.id);
                      setActiveTab("overview");
                    }}
                  >
                    👁️ View
                  </button>
                  <button className={styles.secondaryBtn} onClick={() => handleDownload(ver.id)}>
                    📥 Download
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Court Exhibits */}
      {activeTab === "exhibits" && (
        <div className={styles.panel}>
          <div className={styles.panelTitle}>
            <span>Formal Court Exhibits ({(evidence.exhibits || []).length})</span>
            <button className={styles.primaryBtn} onClick={() => setExhibitModalOpen(true)}>
              + Mark as Exhibit
            </button>
          </div>

          {(evidence.exhibits || []).length === 0 ? (
            <div className={styles.emptyState}>
              <p style={{ fontSize: "16px", color: "#cbd5e1", fontWeight: 600 }}>
                No Court Exhibits Marked
              </p>
              <p style={{ fontSize: "13px", marginTop: "6px" }}>
                Formal exhibits reference specific immutable versions and can be linked directly to court hearings.
              </p>
              <button
                className={styles.primaryBtn}
                style={{ marginTop: "14px" }}
                onClick={() => setExhibitModalOpen(true)}
              >
                + Mark First Exhibit
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {evidence.exhibits.map((ex) => (
                <div key={ex.id} className={styles.exhibitCard}>
                  <div className={styles.exhibitHeader}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                        <span className={styles.exhibitBadge} style={{ fontSize: "13px", padding: "4px 10px" }}>
                          🏷️ {ex.exhibit_number}
                        </span>
                        <span className={styles.exhibitTitle}>{ex.title}</span>
                      </div>
                      <p style={{ fontSize: "13px", color: "#94a3b8", margin: "6px 0 0" }}>
                        {ex.description || "No specific exhibit description."}
                      </p>
                    </div>
                  </div>

                  <div className={styles.exhibitMetaRow}>
                    <span>
                      📌 <strong>Points to:</strong> Version {ex.version_number ?? 1}
                    </span>
                    {ex.hearing_purpose && (
                      <span>
                        ⚖️ <strong>Linked Hearing:</strong> {ex.hearing_purpose}{" "}
                        {ex.court_name && `(${ex.court_name})`}
                      </span>
                    )}
                    {ex.relevant_date && (
                      <span>
                        📅 <strong>Relevant Date:</strong>{" "}
                        {new Date(ex.relevant_date).toLocaleDateString()}
                      </span>
                    )}
                    <span>
                      🕒 <strong>Marked on:</strong> {new Date(ex.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Sharing & Access Grants */}
      {activeTab === "grants" && (
        <div className={styles.panel}>
          <div className={styles.panelTitle}>
            <span>Controlled Sharing Grants ({evidence.grants.length})</span>
            <button className={styles.primaryBtn} onClick={() => setShareModalOpen(true)}>
              + Share with Lawyer
            </button>
          </div>

          {evidence.grants.length === 0 ? (
            <div className={styles.emptyState}>
              This evidence item has not been shared with any additional parties.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {evidence.grants.map((grant) => {
                const isRevoked = !!grant.revoked_at;
                return (
                  <div
                    key={grant.id}
                    style={{
                      padding: "14px 18px",
                      background: "#090a0f",
                      border: `1px solid ${isRevoked ? "#27272a" : "#1a1e2b"}`,
                      borderRadius: "12px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      opacity: isRevoked ? 0.6 : 1,
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{ fontSize: "14px", color: "#ffffff", fontWeight: 600 }}>
                          Grantee ID: {grant.grantee_user_id}
                        </span>
                        <span className={`${styles.pill} ${styles.pillCategory}`}>
                          {grant.access_level}
                        </span>
                        {isRevoked && (
                          <span className={`${styles.pill} ${styles.pillPrivileged}`}>
                            Revoked
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: "12px", color: "#8c97ad", marginTop: "4px" }}>
                        Granted on: {new Date(grant.created_at).toLocaleDateString()}
                        {grant.expires_at && ` · Expires: ${new Date(grant.expires_at).toLocaleDateString()}`}
                        {isRevoked && ` · Revoked on ${new Date(grant.revoked_at!).toLocaleDateString()}`}
                      </div>
                    </div>

                    {!isRevoked && (
                      <button
                        className={styles.dangerBtn}
                        onClick={() => handleRevoke(grant.grantee_user_id)}
                      >
                        Revoke Access
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Chain of Custody */}
      {activeTab === "custody" && (
        <div className={styles.panel}>
          <div className={styles.panelTitle}>
            <span>Chain of Custody Provenance Ledger</span>
            <span className={styles.securityBadge}>Cryptographically Chained</span>
          </div>

          <div className={styles.timeline}>
            {custodyEvents.map((evt) => (
              <div key={evt.id} className={styles.timelineNode}>
                <div className={styles.timelineDot} />
                <span className={styles.timelineAction}>{evt.action}</span>
                <span className={styles.timelineTime}>
                  {new Date(evt.timestamp).toLocaleString()}
                </span>
                {evt.actor_user_id && (
                  <span style={{ fontSize: "12px", color: "#8c97ad" }}>
                    Actor UUID: {evt.actor_user_id}
                  </span>
                )}
                {evt.metadata && Object.keys(evt.metadata).length > 0 && (
                  <pre
                    style={{
                      background: "#08090d",
                      border: "1px solid #1a1e2b",
                      padding: "8px 12px",
                      borderRadius: "6px",
                      fontSize: "11px",
                      color: "#94a3b8",
                      marginTop: "4px",
                      overflowX: "auto",
                    }}
                  >
                    {JSON.stringify(evt.metadata, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Mark Exhibit Modal */}
      {exhibitModalOpen && (
        <div className={styles.modalBackdrop} onClick={() => setExhibitModalOpen(false)}>
          <div className={styles.modalWindow} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>Mark Formal Court Exhibit</h2>
            {exhibitError && (
              <div
                style={{
                  background: "rgba(239, 68, 68, 0.15)",
                  color: "#f87171",
                  padding: "10px",
                  borderRadius: "8px",
                  marginBottom: "12px",
                  fontSize: "13px",
                }}
              >
                {exhibitError}
              </div>
            )}

            <form onSubmit={handleCreateExhibit}>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Exhibit Number (Optional — auto-allocated if blank)</label>
                <input
                  type="text"
                  className={styles.formInput}
                  placeholder="Leave blank for next letter (e.g. Exhibit A, Exhibit B), or enter custom (e.g. Exhibit P-1)"
                  value={exhibitNumber}
                  onChange={(e) => setExhibitNumber(e.target.value)}
                />
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Exhibit Title *</label>
                <input
                  type="text"
                  className={styles.formInput}
                  placeholder="e.g., Primary Sale Deed with Land Annexure"
                  value={exhibitTitle}
                  onChange={(e) => setExhibitTitle(e.target.value)}
                  required
                />
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Target Evidence Version</label>
                <select
                  className={styles.formSelect}
                  value={exhibitVersionId}
                  onChange={(e) => setExhibitVersionId(e.target.value)}
                >
                  {evidence.versions.map((ver) => (
                    <option key={ver.id} value={ver.id}>
                      Version {ver.version_number} ({ver.original_filename} · {new Date(ver.created_at).toLocaleDateString()})
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Link to Court Hearing (Optional)</label>
                <select
                  className={styles.formSelect}
                  value={exhibitHearingId}
                  onChange={(e) => setExhibitHearingId(e.target.value)}
                >
                  <option value="">-- None (Case Level Exhibit) --</option>
                  {caseHearings.map((h) => (
                    <option key={h.id} value={h.id}>
                      {h.purpose} ({h.court_name} · {new Date(h.hearing_at).toLocaleDateString()})
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Relevant Date (Optional)</label>
                <input
                  type="date"
                  className={styles.formInput}
                  value={exhibitDate}
                  onChange={(e) => setExhibitDate(e.target.value)}
                />
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Legal Context / Description</label>
                <textarea
                  className={styles.formTextarea}
                  placeholder="Notes for litigation, relevant clauses, or cross-examination points..."
                  rows={2}
                  value={exhibitDesc}
                  onChange={(e) => setExhibitDesc(e.target.value)}
                />
              </div>

              <div className={styles.modalActions}>
                <button
                  type="button"
                  className={styles.secondaryBtn}
                  onClick={() => setExhibitModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className={styles.primaryBtn} disabled={exhibitLoading}>
                  {exhibitLoading ? "Allocating & Marking..." : "Confirm Exhibit"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Deposit Version Modal */}
      {versionModalOpen && (
        <div className={styles.modalBackdrop} onClick={() => setVersionModalOpen(false)}>
          <div className={styles.modalWindow} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>Deposit Immutable Version</h2>
            {versionError && (
              <div
                style={{
                  background: "rgba(239, 68, 68, 0.15)",
                  color: "#f87171",
                  padding: "10px",
                  borderRadius: "8px",
                  marginBottom: "12px",
                  fontSize: "13px",
                }}
              >
                {versionError}
              </div>
            )}

            <form onSubmit={handleVersionUpload}>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Select New Version File *</label>
                <div
                  className={styles.fileDropZone}
                  onClick={() => document.getElementById("new-ver-input")?.click()}
                >
                  <input
                    id="new-ver-input"
                    type="file"
                    style={{ display: "none" }}
                    onChange={(e) => {
                      if (e.target.files?.[0]) setNewVersionFile(e.target.files[0]);
                    }}
                  />
                  {newVersionFile ? (
                    <div>
                      <span style={{ color: "#38bdf8", fontWeight: 600 }}>
                        📄 {newVersionFile.name}
                      </span>
                      <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                        {(newVersionFile.size / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  ) : (
                    <div>
                      <span style={{ color: "#818cf8", fontSize: "13px" }}>
                        Click to select new version file
                      </span>
                      <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                        PDF, PNG, JPEG (SHA-256 Verifiable)
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className={styles.modalActions}>
                <button
                  type="button"
                  className={styles.secondaryBtn}
                  onClick={() => setVersionModalOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.primaryBtn}
                  disabled={uploadingVersion || !newVersionFile}
                >
                  {uploadingVersion ? "Uploading & Scanning..." : "Deposit Version"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Evidence Share Modal */}
      {shareModalOpen && (
        <EvidenceShareModal
          isOpen={shareModalOpen}
          onClose={() => {
            setShareModalOpen(false);
            loadData();
          }}
          caseId={caseId}
          evidenceId={evidenceId}
          evidenceTitle={evidence.title}
        />
      )}
    </div>
  );
}
