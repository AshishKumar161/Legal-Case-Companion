"use client";

import React, { use, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiClient } from "@/api/client";
import styles from "./bundles.module.css";
import {
  EvidenceBundleItemDetail,
  BundleStatus,
  BSACertificateDraftItem,
} from "@/types";

interface CaseExhibitItem {
  id: string;
  evidence_id: string;
  evidence_version_id: string;
  hearing_id: string | null;
  exhibit_number: string;
  exhibit_label: string | null;
  evidence_title?: string;
  original_filename?: string;
  sha256_hash?: string;
}

interface CaseHearingBrief {
  id: string;
  court_name: string;
  court_number?: string | null;
  hearing_at: string;
  status: string;
  purpose?: string | null;
}

export default function EvidentiaryBundlesPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const unwrappedParams = use(params);
  const { caseId } = unwrappedParams;
  const searchParams = useSearchParams();
  const preselectedHearingId = searchParams.get("hearingId");

  const [bundles, setBundles] = useState<EvidenceBundleItemDetail[]>([]);
  const [hearings, setHearings] = useState<CaseHearingBrief[]>([]);
  const [availableExhibits, setAvailableExhibits] = useState<CaseExhibitItem[]>([]);
  const [caseTitle, setCaseTitle] = useState<string>("Case Matter");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Filtering
  const [statusFilter, setStatusFilter] = useState<"ALL" | BundleStatus>("ALL");

  // Create Bundle Modal State
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newHearingId, setNewHearingId] = useState<string>(preselectedHearingId || "");
  const [newBatesPrefix, setNewBatesPrefix] = useState("LCC");
  const [newBatesStart, setNewBatesStart] = useState(1);
  const [selectedExhibitIds, setSelectedExhibitIds] = useState<Set<string>>(new Set());

  // Manifest View Modal State
  const [manifestModalOpen, setManifestModalOpen] = useState(false);
  const [activeBundleDetail, setActiveBundleDetail] = useState<EvidenceBundleItemDetail | null>(null);

  // Finalize Confirmation Modal State
  const [finalizeModalOpen, setFinalizeModalOpen] = useState(false);
  const [bundleToFinalize, setBundleToFinalize] = useState<EvidenceBundleItemDetail | null>(null);
  const [finalizing, setFinalizing] = useState(false);

  // BSA Section 63 Certificate Modal State
  const [certificateModalOpen, setCertificateModalOpen] = useState(false);
  const [certBundle, setCertBundle] = useState<EvidenceBundleItemDetail | null>(null);
  const [certDeclarantName, setCertDeclarantName] = useState("");
  const [certDeclarantDesignation, setCertDeclarantDesignation] = useState("Advocate on Record / Counsel");
  const [certDeclarantOrg, setCertDeclarantOrg] = useState("");
  const [certDeviceDesc, setCertDeviceDesc] = useState("Workstation & Primary Scanner");
  const [certDeviceSerial, setCertDeviceSerial] = useState("");
  const [certLawfulControlConfirmed, setCertLawfulControlConfirmed] = useState(true);
  const [certOperationalConditionConfirmed, setCertOperationalConditionConfirmed] = useState(true);
  const [certStatutoryAffirmation, setCertStatutoryAffirmation] = useState(false);
  const [submittingCert, setSubmittingCert] = useState(false);
  const [createdCertificate, setCreatedCertificate] = useState<BSACertificateDraftItem | null>(null);

  // Fetch bundles and case context
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [caseRes, bundlesRes, workflowRes] = await Promise.all([
        apiClient.get(`/api/v1/cases/${caseId}`).catch(() => null),
        apiClient.get(`/api/v1/cases/${caseId}/bundles`).catch(() => ({ items: [] })),
        apiClient.get(`/api/v1/cases/${caseId}/workflow`).catch(() => null),
      ]);

      if (caseRes?.title) {
        setCaseTitle(caseRes.title);
      }

      setBundles(bundlesRes?.items || []);

      if (workflowRes?.hearings) {
        setHearings(workflowRes.hearings);
      }

      // Fetch exhibits for exhibit selection
      try {
        const exhibitsRes = await apiClient.get(`/api/v1/cases/${caseId}/evidence/exhibits`);
        setAvailableExhibits(exhibitsRes?.items || exhibitsRes || []);
      } catch {
        // Fallback: if exhibits endpoint not directly exposed, empty list
        setAvailableExhibits([]);
      }
    } catch (err: unknown) {
      const e = err as Error;
      setError(e.message || "Failed to load evidentiary bundles.");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  // If launched with hearingId query param, open Create Modal automatically
  useEffect(() => {
    if (preselectedHearingId && hearings.length > 0) {
      setNewHearingId(preselectedHearingId);
      const hearing = hearings.find((h) => h.id === preselectedHearingId);
      if (hearing && !newTitle) {
        setNewTitle(`Court Bundle - ${hearing.court_name} (${new Date(hearing.hearing_at).toLocaleDateString()})`);
      }
    }
  }, [preselectedHearingId, hearings, newTitle]);

  const handleCreateBundle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) {
      setError("Please provide a bundle title.");
      return;
    }

    try {
      setCreating(true);
      setError("");

      const payload = {
        title: newTitle.trim(),
        description: newDesc.trim() || undefined,
        hearing_id: newHearingId || undefined,
        bates_prefix: newBatesPrefix.trim() || "LCC",
        bates_start_number: newBatesStart || 1,
        selected_evidence_version_ids: Array.from(selectedExhibitIds).length > 0
          ? Array.from(selectedExhibitIds)
          : undefined,
      };

      await apiClient.post(`/api/v1/cases/${caseId}/bundles`, payload);
      setSuccessMsg("Evidentiary bundle draft created successfully.");
      setCreateModalOpen(false);
      setNewTitle("");
      setNewDesc("");
      setSelectedExhibitIds(new Set());
      await fetchData();
    } catch (err: unknown) {
      const e = err as Error;
      setError(e.message || "Failed to create evidentiary bundle.");
    } finally {
      setCreating(false);
    }
  };

  const handleOpenFinalize = (b: EvidenceBundleItemDetail) => {
    setBundleToFinalize(b);
    setFinalizeModalOpen(true);
  };

  const handleConfirmFinalize = async () => {
    if (!bundleToFinalize) return;
    try {
      setFinalizing(true);
      setError("");

      await apiClient.post(`/api/v1/cases/${caseId}/bundles/${bundleToFinalize.id}/finalize`, {});
      setSuccessMsg(`Bundle "${bundleToFinalize.title}" successfully finalized with Bates stamping & SHA-256 manifest!`);
      setFinalizeModalOpen(false);
      setBundleToFinalize(null);
      await fetchData();
    } catch (err: unknown) {
      const e = err as Error;
      setError(e.message || "Finalization failed.");
    } finally {
      setFinalizing(false);
    }
  };

  const handleDownloadBundle = async (bundle: EvidenceBundleItemDetail) => {
    try {
      setError("");
      const res = (await apiClient.get(
        `/api/v1/cases/${caseId}/bundles/${bundle.id}/download`
      )) as { download_url: string; filename: string };
      if (res?.download_url) {
        window.open(res.download_url, "_blank");
      }
    } catch (err: unknown) {
      const e = err as Error;
      setError(e.message || "Failed to initiate secure download.");
    }
  };

  const handleOpenManifest = async (bundle: EvidenceBundleItemDetail) => {
    try {
      setError("");
      const detail = (await apiClient.get(
        `/api/v1/cases/${caseId}/bundles/${bundle.id}`
      )) as EvidenceBundleItemDetail;
      setActiveBundleDetail(detail);
      setManifestModalOpen(true);
    } catch (err: unknown) {
      const e = err as Error;
      setError(e.message || "Failed to load bundle manifest details.");
    }
  };

  const handleOpenCertificateModal = (bundle: EvidenceBundleItemDetail) => {
    setCertBundle(bundle);
    setCreatedCertificate(null);
    setCertStatutoryAffirmation(false);
    setCertificateModalOpen(true);
  };

  const handlePrepareCertificate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!certBundle) return;
    if (!certDeclarantName.trim()) {
      setError("Declarant name is required for statutory preparation.");
      return;
    }
    if (!certStatutoryAffirmation) {
      setError("Please affirm the truthfulness declaration before generating the draft.");
      return;
    }

    try {
      setSubmittingCert(true);
      setError("");

      const payload = {
        declarant_name: certDeclarantName.trim(),
        declarant_designation: certDeclarantDesignation.trim(),
        declarant_organization: certDeclarantOrg.trim() || undefined,
        device_description: certDeviceDesc.trim(),
        device_serial_number: certDeviceSerial.trim() || undefined,
        lawful_control_declaration:
          "The computer device and evidence storage systems were operating under lawful control of the declarant throughout the relevant period.",
        operational_condition_declaration:
          "During the material period, the computer system was operating properly and neither the storage nor transmission of electronic records was compromised by malfunction.",
        is_confirmed: true,
      };

      const certRes = (await apiClient.post(
        `/api/v1/cases/${caseId}/bundles/${certBundle.id}/certificates/bsa63`,
        payload
      )) as BSACertificateDraftItem;

      setCreatedCertificate(certRes);
      setSuccessMsg("Section 63(4) Certificate Draft prepared successfully.");
      await fetchData();
    } catch (err: unknown) {
      const e = err as Error;
      setError(e.message || "Failed to prepare Section 63 certificate.");
    } finally {
      setSubmittingCert(false);
    }
  };

  const handleDownloadCertificate = async (cert: BSACertificateDraftItem) => {
    try {
      setError("");
      const res = (await apiClient.get(
        `/api/v1/cases/${caseId}/bundles/${cert.bundle_id}/certificates/${cert.id}/download`
      )) as { download_url: string; filename: string };
      if (res?.download_url) {
        window.open(res.download_url, "_blank");
      }
    } catch (err: unknown) {
      const e = err as Error;
      setError(e.message || "Failed to download certificate PDF.");
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setSuccessMsg("Hash copied to clipboard!");
    setTimeout(() => setSuccessMsg(""), 3000);
  };

  const filteredBundles = bundles.filter((b) => {
    if (statusFilter === "ALL") return true;
    return b.status === statusFilter;
  });

  const finalizedCount = bundles.filter((b) => b.status === "FINALIZED").length;
  const draftCount = bundles.filter((b) => b.status === "DRAFT").length;

  return (
    <div className={styles.container}>
      {/* Breadcrumb Navigation */}
      <nav className={styles.breadcrumbNav} aria-label="Breadcrumb">
        <Link href="/dashboard" className={styles.breadcrumbLink}>
          Dashboard
        </Link>
        <span className={styles.breadcrumbSep}>/</span>
        <Link href={`/cases/${caseId}`} className={styles.breadcrumbLink}>
          {caseTitle}
        </Link>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>Evidentiary Bundles</span>
      </nav>

      {/* Hero Header */}
      <div className={styles.heroHeader}>
        <div className={styles.heroGlow} />
        <div className={styles.titleArea}>
          <div className={styles.bundleIconWrapper}>📦</div>
          <div>
            <h1>Evidentiary Bundles & Court Preparation</h1>
            <div className={styles.complianceBadge}>
              <span>⚖️</span> Deterministic Manifest · Bates Numbered · BSA §63 Compliant
            </div>
          </div>
        </div>

        <div className={styles.headerActions}>
          <Link href={`/cases/${caseId}/evidence`} className={styles.secondaryBtn}>
            <span>🗄️</span> Evidence Locker
          </Link>
          <button
            onClick={() => setCreateModalOpen(true)}
            className={styles.primaryBtn}
            id="create-bundle-btn"
          >
            <span>+</span> New Evidentiary Bundle
          </button>
        </div>
      </div>

      {/* Feedback Alerts */}
      {error && (
        <div
          style={{
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            borderRadius: "10px",
            padding: "12px 16px",
            color: "#f87171",
            fontSize: "13px",
            marginBottom: "20px",
          }}
        >
          <strong>Error:</strong> {error}
        </div>
      )}

      {successMsg && (
        <div
          style={{
            background: "rgba(16, 185, 129, 0.1)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            borderRadius: "10px",
            padding: "12px 16px",
            color: "#34d399",
            fontSize: "13px",
            marginBottom: "20px",
          }}
        >
          ✓ {successMsg}
        </div>
      )}

      {/* Stats Ribbon */}
      <div className={styles.statsRibbon}>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>Total Bundles</div>
          <div className={styles.statValue}>{bundles.length}</div>
          <div className={styles.statSub}>Configured for this matter</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>Finalized & Sealed</div>
          <div className={styles.statValue} style={{ color: "#34d399" }}>
            {finalizedCount}
          </div>
          <div className={styles.statSub}>Immutable court derivatives</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>Draft Bundles</div>
          <div className={styles.statValue} style={{ color: "#fbbf24" }}>
            {draftCount}
          </div>
          <div className={styles.statSub}>In preparation / editing</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statLabel}>Associated Hearings</div>
          <div className={styles.statValue}>{hearings.length}</div>
          <div className={styles.statSub}>Upcoming & recorded listings</div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className={styles.filterBar}>
        <div className={styles.filterTabs}>
          <button
            className={`${styles.filterTabBtn} ${statusFilter === "ALL" ? styles.filterTabActive : ""}`}
            onClick={() => setStatusFilter("ALL")}
          >
            All Bundles ({bundles.length})
          </button>
          <button
            className={`${styles.filterTabBtn} ${statusFilter === "FINALIZED" ? styles.filterTabActive : ""}`}
            onClick={() => setStatusFilter("FINALIZED")}
          >
            Finalized ({finalizedCount})
          </button>
          <button
            className={`${styles.filterTabBtn} ${statusFilter === "DRAFT" ? styles.filterTabActive : ""}`}
            onClick={() => setStatusFilter("DRAFT")}
          >
            Drafts ({draftCount})
          </button>
        </div>
      </div>

      {/* Bundles Listing */}
      {loading ? (
        <div style={{ textAlign: "center", padding: "60px 20px", color: "#727c8e" }}>
          Loading evidentiary bundles and cryptographic manifests...
        </div>
      ) : filteredBundles.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>📦</div>
          <h3 className={styles.emptyTitle}>No Evidentiary Bundles Found</h3>
          <p className={styles.emptyDesc}>
            Prepare a clean, indexed, Bates-numbered court bundle for your upcoming hearing. Original
            evidence items remain preserved and uncompromised.
          </p>
          <button
            onClick={() => setCreateModalOpen(true)}
            className={styles.primaryBtn}
            style={{ marginTop: "12px" }}
          >
            <span>+</span> Create First Bundle
          </button>
        </div>
      ) : (
        <div className={styles.bundleGrid}>
          {filteredBundles.map((bundle) => {
            const isFinalized = bundle.status === "FINALIZED";
            const isDraft = bundle.status === "DRAFT";
            const isGenerating = bundle.status === "GENERATING";

            return (
              <div key={bundle.id} className={styles.bundleCard}>
                <div className={styles.cardTop}>
                  <div className={styles.cardTitleArea}>
                    <div className={styles.cardHeadingRow}>
                      <h3 className={styles.bundleTitle}>{bundle.title}</h3>
                      {isFinalized && <span className={styles.badgeFinalized}>FINALIZED 🔒</span>}
                      {isDraft && <span className={styles.badgeDraft}>DRAFT 📝</span>}
                      {isGenerating && <span className={styles.badgeGenerating}>COMPILING ⏳</span>}
                      {bundle.status === "FAILED" && <span className={styles.badgeFailed}>FAILED ⚠️</span>}
                    </div>
                    {bundle.description && <p className={styles.bundleDesc}>{bundle.description}</p>}
                  </div>
                </div>

                <div className={styles.cardMetaGrid}>
                  <div className={styles.metaItem}>
                    <span className={styles.metaLabel}>Bates Stamping</span>
                    <span className={styles.batesBadge}>
                      {bundle.bates_prefix}
                      {String(bundle.bates_start_number).padStart(6, "0")}
                      {isFinalized && bundle.total_pages > 0
                        ? ` → ${bundle.bates_prefix}${String(bundle.bates_start_number + bundle.total_pages - 1).padStart(6, "0")}`
                        : " (Configured)"}
                    </span>
                  </div>

                  <div className={styles.metaItem}>
                    <span className={styles.metaLabel}>Documents / Exhibits</span>
                    <span className={styles.metaVal}>{bundle.item_count} selected items</span>
                  </div>

                  <div className={styles.metaItem}>
                    <span className={styles.metaLabel}>Compiled Pages</span>
                    <span className={styles.metaVal}>
                      {isFinalized ? `${bundle.total_pages} pages` : "Pending finalization"}
                    </span>
                  </div>

                  {bundle.bundle_sha256 && (
                    <div className={styles.metaItem} style={{ gridColumn: "span 2" }}>
                      <span className={styles.metaLabel}>SHA-256 Bundle Digest</span>
                      <div className={styles.hashBadge}>
                        <span>{bundle.bundle_sha256}</span>
                        <button
                          className={styles.copyHashBtn}
                          onClick={() => copyToClipboard(bundle.bundle_sha256!)}
                          title="Copy digest"
                        >
                          📋
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                <div className={styles.cardFooter}>
                  <div className={styles.footerLeft}>
                    <span>Created: {new Date(bundle.created_at).toLocaleDateString()}</span>
                    {bundle.finalized_at && (
                      <span>• Sealed: {new Date(bundle.finalized_at).toLocaleString()}</span>
                    )}
                  </div>

                  <div className={styles.footerActions}>
                    <button
                      onClick={() => handleOpenManifest(bundle)}
                      className={styles.btnManifest}
                      title="Inspect frozen manifest"
                    >
                      📋 Manifest
                    </button>

                    {isDraft && (
                      <button
                        onClick={() => handleOpenFinalize(bundle)}
                        className={styles.btnFinalize}
                        title="Compile PDF and seal bundle permanently"
                      >
                        🔒 Finalize & Bates Stamp
                      </button>
                    )}

                    {isFinalized && (
                      <>
                        <button
                          onClick={() => handleOpenCertificateModal(bundle)}
                          className={styles.btnCertificate}
                          title="Prepare Section 63 statutory certificate draft"
                        >
                          📜 BSA §63 Draft
                        </button>

                        <button
                          onClick={() => handleDownloadBundle(bundle)}
                          className={styles.btnDownload}
                          title="Download court PDF bundle"
                        >
                          📥 Download PDF
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* CREATE BUNDLE MODAL */}
      {createModalOpen && (
        <div className={styles.modalBackdrop}>
          <div className={styles.modalBox}>
            <div className={styles.modalHeader}>
              <h2>Create New Evidentiary Bundle</h2>
              <button onClick={() => setCreateModalOpen(false)} className={styles.closeBtn}>
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateBundle}>
              <div className={styles.modalBody}>
                <div className={styles.securityNoticeAlert}>
                  <span>ℹ️</span>
                  <div>
                    <strong>Derivative Artifact Policy:</strong> Creating a bundle links designated
                    evidence versions and generates a court-ready package. Original files in the Evidence
                    Locker are preserved unmodified.
                  </div>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Bundle Title *</label>
                  <input
                    type="text"
                    required
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="e.g., Court Evidentiary Bundle - Company Petition 2026"
                    className={styles.formInput}
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Purpose / Description</label>
                  <textarea
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                    placeholder="e.g., Evidentiary exhibits for preliminary hearing before High Court Bench 3"
                    className={styles.formTextarea}
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Associated Court Hearing</label>
                  <select
                    value={newHearingId}
                    onChange={(e) => setNewHearingId(e.target.value)}
                    className={styles.formSelect}
                  >
                    <option value="">-- Standalone Bundle (No specific hearing) --</option>
                    {hearings.map((h) => (
                      <option key={h.id} value={h.id}>
                        {h.court_name} · {new Date(h.hearing_at).toLocaleDateString()} (
                        {h.status})
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Bates Prefix</label>
                    <input
                      type="text"
                      value={newBatesPrefix}
                      onChange={(e) => setNewBatesPrefix(e.target.value.toUpperCase())}
                      placeholder="LCC"
                      className={styles.formInput}
                    />
                    <span className={styles.formHelp}>Default prefix burned on each page footer</span>
                  </div>

                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Bates Starting Number</label>
                    <input
                      type="number"
                      min={1}
                      value={newBatesStart}
                      onChange={(e) => setNewBatesStart(parseInt(e.target.value, 10) || 1)}
                      className={styles.formInput}
                    />
                    <span className={styles.formHelp}>e.g. 1 generates {newBatesPrefix}000001</span>
                  </div>
                </div>

                {availableExhibits.length > 0 && (
                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Select Marked Exhibits to Include</label>
                    <div className={styles.exhibitSelectTable}>
                      {availableExhibits.map((ex) => {
                        const isChecked = selectedExhibitIds.has(ex.evidence_version_id);
                        return (
                          <div key={ex.id} className={styles.exhibitRow}>
                            <input
                              type="checkbox"
                              className={styles.checkboxInput}
                              checked={isChecked}
                              onChange={(e) => {
                                const next = new Set(selectedExhibitIds);
                                if (e.target.checked) {
                                  next.add(ex.evidence_version_id);
                                } else {
                                  next.delete(ex.evidence_version_id);
                                }
                                setSelectedExhibitIds(next);
                              }}
                            />
                            <div style={{ flex: 1 }}>
                              <strong>{ex.exhibit_number}</strong>: {ex.evidence_title || ex.original_filename || "Evidence"}
                              <div style={{ fontSize: "11px", color: "#727c8e", fontFamily: "monospace" }}>
                                SHA: {ex.sha256_hash?.slice(0, 16)}...
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <span className={styles.formHelp}>
                      Selected versions will be compiled in natural order (Exhibit A, B, ... AA).
                    </span>
                  </div>
                )}
              </div>

              <div className={styles.modalFooter}>
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
                  className={styles.secondaryBtn}
                >
                  Cancel
                </button>
                <button type="submit" disabled={creating} className={styles.primaryBtn}>
                  {creating ? "Creating Draft..." : "Create Bundle Draft"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* FINALIZE CONFIRMATION MODAL */}
      {finalizeModalOpen && bundleToFinalize && (
        <div className={styles.modalBackdrop}>
          <div className={styles.modalBox}>
            <div className={styles.modalHeader}>
              <h2>Confirm Immutable Finalization</h2>
              <button onClick={() => setFinalizeModalOpen(false)} className={styles.closeBtn}>
                ✕
              </button>
            </div>

            <div className={styles.modalBody}>
              <div className={styles.noticeAlert}>
                <span>⚠️</span>
                <div>
                  <strong>Permanent Immutability Warning:</strong> Once finalized, this bundle will be
                  compiled into a single sealed PDF with cover page, table of exhibits, stamped Bates
                  numbers, and frozen SHA-256 digests.
                  <p style={{ margin: "6px 0 0" }}>
                    The bundle cannot be edited or modified after finalization. Any subsequent additions
                    require creating a new derivative bundle.
                  </p>
                </div>
              </div>

              <div>
                <p>
                  <strong>Bundle:</strong> {bundleToFinalize.title}
                </p>
                <p>
                  <strong>Configured Bates:</strong> {bundleToFinalize.bates_prefix}
                  {String(bundleToFinalize.bates_start_number).padStart(6, "0")}
                </p>
              </div>
            </div>

            <div className={styles.modalFooter}>
              <button
                type="button"
                onClick={() => setFinalizeModalOpen(false)}
                className={styles.secondaryBtn}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmFinalize}
                disabled={finalizing}
                className={styles.btnFinalize}
              >
                {finalizing ? "Compiling PDF & Sealing..." : "Confirm & Finalize Bundle"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MANIFEST INSPECTOR MODAL */}
      {manifestModalOpen && activeBundleDetail && (
        <div className={styles.modalBackdrop}>
          <div className={styles.modalBox} style={{ maxWidth: "800px" }}>
            <div className={styles.modalHeader}>
              <h2>Bundle Manifest & Provenance Digest</h2>
              <button onClick={() => setManifestModalOpen(false)} className={styles.closeBtn}>
                ✕
              </button>
            </div>

            <div className={styles.modalBody}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <strong>Bundle:</strong> {activeBundleDetail.title}
                </div>
                <div>
                  <strong>Status:</strong> {activeBundleDetail.status}
                </div>
                <div>
                  <strong>Bates Prefix:</strong> {activeBundleDetail.bates_prefix}
                </div>
                <div>
                  <strong>Total Pages:</strong> {activeBundleDetail.total_pages}
                </div>
              </div>

              {activeBundleDetail.bundle_sha256 && (
                <div style={{ marginTop: "12px" }}>
                  <span className={styles.formLabel}>Final Sealed PDF Hash (SHA-256)</span>
                  <div className={styles.hashBadge} style={{ marginTop: "4px" }}>
                    <span>{activeBundleDetail.bundle_sha256}</span>
                    <button
                      className={styles.copyHashBtn}
                      onClick={() => copyToClipboard(activeBundleDetail.bundle_sha256!)}
                    >
                      📋
                    </button>
                  </div>
                </div>
              )}

              <div style={{ marginTop: "16px" }}>
                <span className={styles.formLabel}>Ordered Exhibit Items</span>
                <table className={styles.manifestTable} style={{ marginTop: "8px" }}>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Exhibit</th>
                      <th>Evidence Title</th>
                      <th>Bates Range</th>
                      <th>SHA-256 Hash</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeBundleDetail.items && activeBundleDetail.items.length > 0 ? (
                      activeBundleDetail.items.map((item, idx) => (
                        <tr key={item.id}>
                          <td>{idx + 1}</td>
                          <td>
                            <strong>{item.exhibit_label || `Item ${idx + 1}`}</strong>
                          </td>
                          <td>{item.evidence_title || item.original_filename || "Document"}</td>
                          <td>
                            <span className={styles.batesBadge}>
                              {item.bates_start || "N/A"} → {item.bates_end || "N/A"}
                            </span>
                          </td>
                          <td style={{ fontFamily: "monospace", fontSize: "11px" }}>
                            {item.sha256_hash ? `${item.sha256_hash.slice(0, 16)}...` : "Pending"}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={5} style={{ textAlign: "center", color: "#727c8e" }}>
                          No exhibits added to this bundle draft yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className={styles.modalFooter}>
              <button
                type="button"
                onClick={() => setManifestModalOpen(false)}
                className={styles.secondaryBtn}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* BSA SECTION 63 CERTIFICATE MODAL */}
      {certificateModalOpen && certBundle && (
        <div className={styles.modalBackdrop}>
          <div className={styles.modalBox} style={{ maxWidth: "720px" }}>
            <div className={styles.modalHeader}>
              <h2>Bharatiya Sakshya Adhiniyam, 2023 — Section 63(4) Certificate Draft</h2>
              <button onClick={() => setCertificateModalOpen(false)} className={styles.closeBtn}>
                ✕
              </button>
            </div>

            {createdCertificate ? (
              <div className={styles.modalBody}>
                <div
                  style={{
                    background: "rgba(16, 185, 129, 0.12)",
                    border: "1px solid rgba(16, 185, 129, 0.3)",
                    borderRadius: "10px",
                    padding: "16px",
                    color: "#34d399",
                  }}
                >
                  <h3 style={{ margin: "0 0 6px", fontSize: "16px", color: "#fff" }}>
                    ✓ Certificate Draft Prepared
                  </h3>
                  <p style={{ margin: 0, fontSize: "13px", color: "#e2e8f0" }}>
                    The statutory certificate draft conforming to the Schedule of Bharatiya Sakshya
                    Adhiniyam, 2023 has been generated. The declarant must review, sign, and verify the
                    document before submitting it to the court.
                  </p>
                </div>

                <div style={{ display: "flex", gap: "12px", marginTop: "12px" }}>
                  <button
                    onClick={() => handleDownloadCertificate(createdCertificate)}
                    className={styles.btnDownload}
                  >
                    📥 Download Certificate PDF
                  </button>
                  <button
                    onClick={() => setCertificateModalOpen(false)}
                    className={styles.secondaryBtn}
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handlePrepareCertificate}>
                <div className={styles.modalBody}>
                  {/* Statutory disclaimer */}
                  <div className={styles.noticeAlert}>
                    <span>⚖️</span>
                    <div>
                      <strong>Legal Notice & Safe Harbor:</strong> This workflow prepares a structured
                      draft certificate under Section 63(4) and the Schedule of the Bharatiya Sakshya
                      Adhiniyam, 2023. LCC auto-populates cryptographic hashes and electronic records.
                      LCC does not claim or guarantee court admissibility. The declarant must verify and
                      truthfully attest to device facts and lawful control.
                    </div>
                  </div>

                  <div className={styles.formGroup}>
                    <label className={styles.formLabel}>Declarant Full Name *</label>
                    <input
                      type="text"
                      required
                      value={certDeclarantName}
                      onChange={(e) => setCertDeclarantName(e.target.value)}
                      placeholder="e.g., Rajesh Kumar Sharma"
                      className={styles.formInput}
                    />
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
                    <div className={styles.formGroup}>
                      <label className={styles.formLabel}>Declarant Designation *</label>
                      <input
                        type="text"
                        required
                        value={certDeclarantDesignation}
                        onChange={(e) => setCertDeclarantDesignation(e.target.value)}
                        placeholder="e.g., Advocate on Record / System Administrator"
                        className={styles.formInput}
                      />
                    </div>

                    <div className={styles.formGroup}>
                      <label className={styles.formLabel}>Organization / Chamber</label>
                      <input
                        type="text"
                        value={certDeclarantOrg}
                        onChange={(e) => setCertDeclarantOrg(e.target.value)}
                        placeholder="e.g., High Court of Delhi Chamber 14"
                        className={styles.formInput}
                      />
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
                    <div className={styles.formGroup}>
                      <label className={styles.formLabel}>Device Description *</label>
                      <input
                        type="text"
                        required
                        value={certDeviceDesc}
                        onChange={(e) => setCertDeviceDesc(e.target.value)}
                        placeholder="e.g., MacBook Pro M2 & Canon DR-C225 Document Scanner"
                        className={styles.formInput}
                      />
                      <span className={styles.formHelp}>Verified physical device used for digital records</span>
                    </div>

                    <div className={styles.formGroup}>
                      <label className={styles.formLabel}>Device Serial / MAC (Optional)</label>
                      <input
                        type="text"
                        value={certDeviceSerial}
                        onChange={(e) => setCertDeviceSerial(e.target.value)}
                        placeholder="e.g., C02G78K0MD6R"
                        className={styles.formInput}
                      />
                      <span className={styles.formHelp}>Hardware identifier confirmed by declarant</span>
                    </div>
                  </div>

                  <div className={styles.formGroup}>
                    <span className={styles.formLabel}>Human Declarations & Verification</span>

                    <div className={styles.checkboxRow}>
                      <input
                        type="checkbox"
                        id="lawful_control"
                        checked={certLawfulControlConfirmed}
                        onChange={(e) => setCertLawfulControlConfirmed(e.target.checked)}
                        className={styles.checkboxInput}
                      />
                      <label htmlFor="lawful_control" className={styles.checkboxLabel}>
                        <strong>Lawful Control:</strong> I confirm the computer device and storage media
                        were in lawful control of the person/organization during the material period.
                      </label>
                    </div>

                    <div className={styles.checkboxRow}>
                      <input
                        type="checkbox"
                        id="oper_cond"
                        checked={certOperationalConditionConfirmed}
                        onChange={(e) => setCertOperationalConditionConfirmed(e.target.checked)}
                        className={styles.checkboxInput}
                      />
                      <label htmlFor="oper_cond" className={styles.checkboxLabel}>
                        <strong>Operational Integrity:</strong> I confirm the computer system was
                        operating properly and no malfunction compromised electronic record integrity.
                      </label>
                    </div>

                    <div className={styles.checkboxRow} style={{ marginTop: "8px" }}>
                      <input
                        type="checkbox"
                        id="truth_affirmation"
                        checked={certStatutoryAffirmation}
                        onChange={(e) => setCertStatutoryAffirmation(e.target.checked)}
                        className={styles.checkboxInput}
                      />
                      <label htmlFor="truth_affirmation" className={styles.checkboxLabel}>
                        <strong style={{ color: "#fbbf24" }}>Truthful Declaration Affirmation:</strong> I
                        affirm to the best of my knowledge and belief that the statements in this
                        prepared Section 63 certificate draft are true and accurate.
                      </label>
                    </div>
                  </div>
                </div>

                <div className={styles.modalFooter}>
                  <button
                    type="button"
                    onClick={() => setCertificateModalOpen(false)}
                    className={styles.secondaryBtn}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submittingCert || !certStatutoryAffirmation}
                    className={styles.btnCertificate}
                  >
                    {submittingCert ? "Preparing Certificate..." : "Generate Section 63 Draft"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
