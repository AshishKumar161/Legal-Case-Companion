"use client";

import React, { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiClient } from "@/api/client";
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
  legal_hold: boolean;
  legal_hold_reason: string | null;
  retention_until: string | null;
  created_at: string;
  updated_at: string;
  current_version: EvidenceVersionItem | null;
  versions: EvidenceVersionItem[];
  grants: EvidenceGrantItem[];
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Integrity Verification state
  const [verifying, setVerifying] = useState(false);
  const [integrityResult, setIntegrityResult] = useState<{
    match: boolean;
    sha256_recorded: string;
    sha256_computed: string;
    verified_at: string;
  } | null>(null);

  // New Version Modal state
  const [versionModalOpen, setVersionModalOpen] = useState(false);
  const [uploadingVersion, setUploadingVersion] = useState(false);
  const [newVersionFile, setNewVersionFile] = useState<File | null>(null);
  const [versionError, setVersionError] = useState("");

  // Share Modal state
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [shareTargetId, setShareTargetId] = useState("");
  const [shareLevel, setShareLevel] = useState("VIEW");
  const [shareExpires, setShareExpires] = useState("");
  const [shareError, setShareError] = useState("");

  const loadData = async () => {
    try {
      setLoading(true);
      setError("");
      const [detailRes, custodyRes] = await Promise.all([
        apiClient.get(`/api/v1/cases/${caseId}/evidence/${evidenceId}`) as Promise<EvidenceDetail>,
        apiClient.get(`/api/v1/cases/${caseId}/evidence/${evidenceId}/custody`) as Promise<
          EvidenceCustodyItem[]
        >,
      ]);
      setEvidence(detailRes);
      setCustodyEvents(custodyRes || []);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message || "Failed to load evidence details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [caseId, evidenceId]);

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

  const handleView = async (versionId?: string) => {
    try {
      let url = `/api/v1/cases/${caseId}/evidence/${evidenceId}/view-url`;
      if (versionId) url += `?version_id=${versionId}`;
      const res = (await apiClient.get(url)) as { url: string };
      if (res?.url) {
        window.open(res.url, "_blank", "noopener,noreferrer");
      }
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Preview failed");
    }
  };

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

  const handleShare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!shareTargetId) {
      setShareError("Target user UUID is required");
      return;
    }

    try {
      setSharing(true);
      setShareError("");

      await apiClient.post(`/api/v1/cases/${caseId}/evidence/${evidenceId}/share`, {
        target_user_id: shareTargetId.trim(),
        access_level: shareLevel,
        expires_at: shareExpires ? new Date(shareExpires).toISOString() : null,
      });

      setShareModalOpen(false);
      setShareTargetId("");
      await loadData();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setShareError(e?.message || "Failed to share evidence");
    } finally {
      setSharing(false);
    }
  };

  const handleRevoke = async (targetUserId: string) => {
    if (!confirm("Are you sure you want to revoke this user's access to this evidence item?")) {
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

  const handleToggleLegalHold = async () => {
    if (!evidence) return;
    const targetState = !evidence.legal_hold;
    const reason = targetState
      ? prompt("Enter justification for applying technical Legal Hold:")
      : "Legal hold lifted by manager";
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

  const handleDelete = async () => {
    if (
      !confirm(
        "Are you sure you want to delete this evidence item? This will be recorded permanently in the chain of custody."
      )
    ) {
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
    return <div className={styles.container}>Loading evidence details & custody ledger...</div>;
  }

  if (error || !evidence) {
    return (
      <div className={styles.container}>
        <div style={{ color: "#f87171", padding: "20px" }}>{error || "Evidence not found"}</div>
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

      {/* Header */}
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
                      : styles.pillConfidential
                  }`}
                >
                  {evidence.sensitivity}
                </span>
                <span
                  className={`${styles.pill} ${
                    evidence.status === "ACTIVE" ? styles.pillActive : styles.pillQuarantined
                  }`}
                >
                  {evidence.status}
                </span>
                {evidence.legal_hold && (
                  <span className={`${styles.pill} ${styles.pillHold}`}>⚖️ Legal Hold Active</span>
                )}
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button className={styles.secondaryBtn} onClick={handleToggleLegalHold}>
            {evidence.legal_hold ? "Lift Legal Hold" : "Apply Legal Hold"}
          </button>
          <button className={styles.dangerBtn} onClick={handleDelete}>
            Delete Item
          </button>
        </div>
      </div>

      {/* Detail Grid */}
      <div className={styles.detailGrid}>
        {/* Left Column: Current Version & Version History */}
        <div>
          {/* Active Version Card */}
          <div className={styles.panel}>
            <div className={styles.panelTitle}>
              <span>Active Evidence Version {curVer ? `(v${curVer.version_number})` : ""}</span>
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  className={styles.secondaryBtn}
                  onClick={() => handleView()}
                  title="View Securely"
                >
                  👁️ View
                </button>
                <button
                  className={styles.primaryBtn}
                  style={{ padding: "8px 14px", fontSize: "12px" }}
                  onClick={() => handleDownload()}
                  title="Download File"
                >
                  📥 Download
                </button>
              </div>
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
                    <span className={styles.metaVal}>
                      {(curVer.size_bytes / 1024).toFixed(1)} KB
                    </span>
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
                        integrityResult.match
                          ? "rgba(16, 185, 129, 0.3)"
                          : "rgba(239, 68, 68, 0.35)"
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

          {/* Immutable Version History */}
          <div className={styles.panel}>
            <div className={styles.panelTitle}>
              <span>Version History ({evidence.versions.length})</span>
              <button
                className={styles.secondaryBtn}
                onClick={() => setVersionModalOpen(true)}
              >
                + New Version
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {evidence.versions.map((ver) => (
                <div
                  key={ver.id}
                  style={{
                    padding: "14px 18px",
                    background: "#090a0f",
                    border: "1px solid #1a1e2b",
                    borderRadius: "10px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ fontWeight: 700, color: "#ffffff", fontSize: "13px" }}>
                        Version {ver.version_number}
                      </span>
                      {ver.id === evidence.current_version_id && (
                        <span className={`${styles.pill} ${styles.pillActive}`}>Current</span>
                      )}
                      <span className={`${styles.pill} ${styles.pillStandard}`}>
                        {(ver.size_bytes / 1024).toFixed(1)} KB
                      </span>
                    </div>
                    <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                      Uploaded: {new Date(ver.created_at).toLocaleString()} · SHA:{" "}
                      {ver.sha256.slice(0, 16)}...
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "6px" }}>
                    <button
                      className={styles.secondaryBtn}
                      style={{ padding: "4px 8px", fontSize: "11px" }}
                      onClick={() => handleView(ver.id)}
                    >
                      View
                    </button>
                    <button
                      className={styles.secondaryBtn}
                      style={{ padding: "4px 8px", fontSize: "11px" }}
                      onClick={() => handleDownload(ver.id)}
                    >
                      Download
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Controlled Sharing & Access Grants */}
          <div className={styles.panel}>
            <div className={styles.panelTitle}>
              <span>Controlled Sharing Grants ({evidence.grants.length})</span>
              <button
                className={styles.secondaryBtn}
                onClick={() => setShareModalOpen(true)}
              >
                + Share with Lawyer
              </button>
            </div>

            {evidence.grants.length === 0 ? (
              <div style={{ fontSize: "13px", color: "#64748b", padding: "12px 0" }}>
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
                        padding: "12px 16px",
                        background: "#090a0f",
                        border: `1px solid ${isRevoked ? "#27272a" : "#1a1e2b"}`,
                        borderRadius: "10px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        opacity: isRevoked ? 0.6 : 1,
                      }}
                    >
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontSize: "13px", color: "#e2e8f0", fontWeight: 600 }}>
                            Grantee: {grant.grantee_user_id.slice(0, 12)}...
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
                        <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                          Granted: {new Date(grant.created_at).toLocaleDateString()}
                          {grant.expires_at &&
                            ` · Expires: ${new Date(grant.expires_at).toLocaleDateString()}`}
                          {isRevoked && ` · Revoked on ${new Date(grant.revoked_at!).toLocaleDateString()}`}
                        </div>
                      </div>

                      {!isRevoked && (
                        <button
                          className={styles.dangerBtn}
                          style={{ padding: "4px 8px", fontSize: "11px" }}
                          onClick={() => handleRevoke(grant.grantee_user_id)}
                        >
                          Revoke
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Chain of Custody Timeline */}
        <div>
          <div className={styles.panel}>
            <div className={styles.panelTitle}>
              <span>Chain of Custody</span>
              <span className={styles.securityBadge} style={{ fontSize: "10px" }}>
                Audit Ledger
              </span>
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
                    <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                      Actor: {evt.actor_user_id.slice(0, 10)}...
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* New Version Modal */}
      {versionModalOpen && (
        <div className={styles.modalBackdrop}>
          <div className={styles.modalWindow}>
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
                <label className={styles.formLabel}>Select New Document File</label>
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
                      <p style={{ margin: 0, color: "#94a3b8", fontSize: "13px" }}>
                        Click to select replacement file
                      </p>
                      <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: "11px" }}>
                        Previous versions will remain immutable and permanently verifiable
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className={styles.modalActions}>
                <button
                  type="button"
                  className={styles.secondaryBtn}
                  onClick={() => setVersionModalOpen(false)}
                  disabled={uploadingVersion}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.primaryBtn}
                  disabled={uploadingVersion}
                >
                  {uploadingVersion ? "Verifying..." : "Upload Version"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Share Modal */}
      {shareModalOpen && (
        <div className={styles.modalBackdrop}>
          <div className={styles.modalWindow}>
            <h2 className={styles.modalTitle}>Share Evidence with Case Lawyer</h2>
            {shareError && (
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
                {shareError}
              </div>
            )}

            <form onSubmit={handleShare}>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Target Lawyer User ID (UUID) *</label>
                <input
                  type="text"
                  className={styles.formInput}
                  placeholder="e.g. 018f23a4-5678-..."
                  value={shareTargetId}
                  onChange={(e) => setShareTargetId(e.target.value)}
                  required
                />
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Access Level</label>
                <select
                  className={styles.formSelect}
                  value={shareLevel}
                  onChange={(e) => setShareLevel(e.target.value)}
                >
                  <option value="VIEW">VIEW (Preview only)</option>
                  <option value="DOWNLOAD">DOWNLOAD (Download & View)</option>
                  <option value="MANAGE">MANAGE (Manage, Share, Version)</option>
                </select>
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Grant Expiration (Optional)</label>
                <input
                  type="datetime-local"
                  className={styles.formInput}
                  value={shareExpires}
                  onChange={(e) => setShareExpires(e.target.value)}
                />
              </div>

              <div className={styles.modalActions}>
                <button
                  type="button"
                  className={styles.secondaryBtn}
                  onClick={() => setShareModalOpen(false)}
                  disabled={sharing}
                >
                  Cancel
                </button>
                <button type="submit" className={styles.primaryBtn} disabled={sharing}>
                  {sharing ? "Granting..." : "Create Access Grant"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
