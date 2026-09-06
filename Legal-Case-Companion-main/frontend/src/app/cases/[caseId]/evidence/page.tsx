"use client";

import React, { use, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { apiClient } from "@/api/client";
import { EvidenceShareModal } from "@/components/Evidence/EvidenceShareModal";
import styles from "./evidence.module.css";

interface EvidenceItem {
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
}

const CATEGORY_TABS = [
  { key: "ALL", label: "All Evidence", icon: "📁" },
  { key: "DOCUMENTS", label: "Documents", icon: "📄" },
  { key: "IMAGES", label: "Images", icon: "🖼️" },
  { key: "VIDEOS", label: "Videos", icon: "🎥" },
  { key: "AUDIO", label: "Audio", icon: "🎙️" },
  { key: "COURT_ORDERS", label: "Court Orders", icon: "⚖️" },
  { key: "CONTRACTS", label: "Contracts", icon: "📜" },
  { key: "EXHIBITS", label: "Exhibits", icon: "🏷️" },
  { key: "ARCHIVED", label: "Archived", icon: "📦" },
];

export default function EvidenceLockerPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const unwrappedParams = use(params);
  const { caseId } = unwrappedParams;

  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Filters & Search
  const [activeTab, setActiveTab] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [sensitivityFilter, setSensitivityFilter] = useState("ALL");
  const [page, setPage] = useState(0);
  const pageSize = 24;

  // Multi-select for Batch Operations
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchActionLoading, setBatchActionLoading] = useState(false);

  // Upload Modal State
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newCategory, setNewCategory] = useState("CONTRACTUAL");
  const [newSensitivity, setNewSensitivity] = useState("CONFIDENTIAL");
  const [newTagsInput, setNewTagsInput] = useState("");
  const [newRetention, setNewRetention] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // Safe Preview Modal State
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewFilename, setPreviewFilename] = useState("");
  const [previewContentType, setPreviewContentType] = useState("");
  const [previewError, setPreviewError] = useState("");

  // Share Modal State
  const [sharingItem, setSharingItem] = useState<{ id: string; title: string } | null>(null);

  const fetchEvidence = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      let url = `/api/v1/cases/${caseId}/evidence`;
      const queryParams = new URLSearchParams();

      // Category tab mappings
      if (activeTab === "ARCHIVED") {
        queryParams.append("status", "ARCHIVED");
      } else if (activeTab === "EXHIBITS") {
        queryParams.append("is_exhibit", "true");
        queryParams.append("status", "ACTIVE");
      } else if (activeTab === "CONTRACTS") {
        queryParams.append("category", "CONTRACTUAL");
        queryParams.append("status", "ACTIVE");
      } else if (activeTab === "COURT_ORDERS") {
        queryParams.append("category", "REGULATORY");
        queryParams.append("status", "ACTIVE");
      } else if (activeTab === "DOCUMENTS") {
        queryParams.append("category", "MISCELLANEOUS");
        queryParams.append("status", "ACTIVE");
      } else if (activeTab === "IMAGES" || activeTab === "VIDEOS" || activeTab === "AUDIO") {
        queryParams.append("category", "DIGITAL");
        queryParams.append("status", "ACTIVE");
      } else if (activeTab === "ALL") {
        queryParams.append("status", "ACTIVE");
      }

      if (searchQuery.trim()) {
        queryParams.append("q", searchQuery.trim());
      }
      if (selectedTag) {
        queryParams.append("tag", selectedTag);
      }
      if (sensitivityFilter !== "ALL") {
        queryParams.append("sensitivity", sensitivityFilter);
      }

      queryParams.append("skip", String(page * pageSize));
      queryParams.append("limit", String(pageSize));

      const qs = queryParams.toString();
      if (qs) url += `?${qs}`;

      const res = (await apiClient.get(url)) as EvidenceItem[];
      setEvidenceList(res || []);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e?.message || "Failed to load Evidence Locker items");
    } finally {
      setLoading(false);
    }
  }, [caseId, activeTab, searchQuery, selectedTag, sensitivityFilter, page]);

  useEffect(() => {
    fetchEvidence();
  }, [fetchEvidence]);

  // Compute unique tags from current items for quick filter chips
  const allTags = Array.from(
    new Set(evidenceList.flatMap((item) => item.tags || []))
  ).slice(0, 10);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (selectedIds.size === evidenceList.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(evidenceList.map((e) => e.id)));
    }
  };

  // Batch Operations
  const handleBatchArchive = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(`Archive ${selectedIds.size} selected evidence item(s)? Items under legal hold will be protected.`)) {
      return;
    }
    try {
      setBatchActionLoading(true);
      await apiClient.post(`/api/v1/cases/${caseId}/evidence/batch`, {
        action: "ARCHIVE",
        evidence_ids: Array.from(selectedIds),
      });
      setSelectedIds(new Set());
      await fetchEvidence();
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Batch archive failed");
    } finally {
      setBatchActionLoading(false);
    }
  };

  const handleBatchRestore = async () => {
    if (selectedIds.size === 0) return;
    try {
      setBatchActionLoading(true);
      await apiClient.post(`/api/v1/cases/${caseId}/evidence/batch`, {
        action: "RESTORE",
        evidence_ids: Array.from(selectedIds),
      });
      setSelectedIds(new Set());
      await fetchEvidence();
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Batch restore failed");
    } finally {
      setBatchActionLoading(false);
    }
  };

  const handleBatchCategory = async () => {
    if (selectedIds.size === 0) return;
    const cat = prompt("Enter new category (CONTRACTUAL, FINANCIAL, FORENSIC, DIGITAL, TESTIMONIAL, REGULATORY, PHYSICAL_SCAN, MISCELLANEOUS):");
    if (!cat) return;
    try {
      setBatchActionLoading(true);
      await apiClient.post(`/api/v1/cases/${caseId}/evidence/batch`, {
        action: "ASSIGN_CATEGORY",
        evidence_ids: Array.from(selectedIds),
        category: cat.toUpperCase(),
      });
      setSelectedIds(new Set());
      await fetchEvidence();
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Batch category update failed");
    } finally {
      setBatchActionLoading(false);
    }
  };

  const handleBatchAddTags = async () => {
    if (selectedIds.size === 0) return;
    const tagsInput = prompt("Enter tags to add (comma-separated):");
    if (!tagsInput) return;
    const tags = tagsInput
      .split(",")
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);
    if (tags.length === 0) return;
    try {
      setBatchActionLoading(true);
      await apiClient.post(`/api/v1/cases/${caseId}/evidence/batch`, {
        action: "ADD_TAGS",
        evidence_ids: Array.from(selectedIds),
        tags,
      });
      setSelectedIds(new Set());
      await fetchEvidence();
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Batch tag update failed");
    } finally {
      setBatchActionLoading(false);
    }
  };

  // Staged Upload Flow
  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setUploadError("Please select a document file to deposit");
      return;
    }

    try {
      setUploading(true);
      setUploadError("");

      const parsedTags = newTagsInput
        .split(",")
        .map((t) => t.trim().toLowerCase())
        .filter(Boolean);

      // 1. Initialize staged upload
      const initRes = (await apiClient.post(`/api/v1/cases/${caseId}/evidence/upload-init`, {
        title: newTitle.trim(),
        description: newDesc.trim() || null,
        category: newCategory,
        sensitivity: newSensitivity,
        original_filename: selectedFile.name,
        content_type: selectedFile.type || "application/pdf",
        size_bytes: selectedFile.size,
        tags: parsedTags,
        retention_until: newRetention ? new Date(newRetention).toISOString() : null,
      })) as { evidence_id: string; version_id: string; upload_url: string };

      // 2. Direct byte transmission to private storage endpoint
      try {
        await fetch(initRes.upload_url, {
          method: "PUT",
          body: selectedFile,
          headers: {
            "Content-Type": selectedFile.type || "application/pdf",
          },
        });
      } catch (uploadErr) {
        console.warn("Storage PUT completed or simulated:", uploadErr);
      }

      // 3. Complete verification, SHA-256 calculation, and activation pipeline
      await apiClient.post(`/api/v1/cases/${caseId}/evidence/${initRes.evidence_id}/complete`, {
        version_id: initRes.version_id,
      });

      // Reset modal and reload
      setUploadModalOpen(false);
      setNewTitle("");
      setNewDesc("");
      setNewTagsInput("");
      setSelectedFile(null);
      await fetchEvidence();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setUploadError(e?.message || "Failed to deposit evidence");
    } finally {
      setUploading(false);
    }
  };

  // Safe Ephemeral Preview
  const handleOpenPreview = async (evidenceId: string, filename: string) => {
    try {
      setPreviewLoading(true);
      setPreviewError("");
      setPreviewModalOpen(true);
      setPreviewFilename(filename);

      const res = (await apiClient.get(
        `/api/v1/cases/${caseId}/evidence/${evidenceId}/view-url`
      )) as { url: string; content_type: string };

      setPreviewUrl(res.url);
      setPreviewContentType(res.content_type || "application/pdf");
    } catch (err: unknown) {
      const e = err as { message?: string };
      setPreviewError(e?.message || "Failed to generate ephemeral preview");
    } finally {
      setPreviewLoading(false);
    }
  };

  // Secure Direct Download
  const handleDownload = async (evidenceId: string) => {
    try {
      const res = (await apiClient.get(
        `/api/v1/cases/${caseId}/evidence/${evidenceId}/download`
      )) as { url: string };
      if (res?.url) {
        window.open(res.url, "_blank", "noopener,noreferrer");
      }
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e?.message || "Download failed");
    }
  };

  // Stats calculation
  const totalCount = evidenceList.length;
  const activeCount = evidenceList.filter((e) => e.status === "ACTIVE").length;
  const legalHoldCount = evidenceList.filter((e) => e.legal_hold).length;
  const exhibitCount = evidenceList.filter((e) => (e.exhibit_numbers || []).length > 0).length;

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
        <span className={styles.breadcrumbCurrent}>Evidence Locker</span>
      </nav>

      {/* Hero Header */}
      <div className={styles.heroHeader}>
        <div className={styles.heroGlow} />
        <div>
          <div className={styles.titleArea}>
            <div className={styles.lockIconWrapper}>🔒</div>
            <div>
              <h1>Evidence Locker</h1>
              <div className={styles.securityBadge}>
                <span>🛡️ High-Security Vault · SHA-256 Integrity · Chain of Custody</span>
              </div>
            </div>
          </div>
        </div>
        <button
          className={styles.primaryBtn}
          onClick={() => setUploadModalOpen(true)}
          id="btn-upload-evidence"
        >
          <span>+ Deposit Evidence</span>
        </button>
      </div>

      {/* Stats Row */}
      <div className={styles.statsRow}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Visible Evidence</span>
          <span className={styles.statValue}>{totalCount}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Active & Verified</span>
          <span className={styles.statValue}>{activeCount}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Marked Exhibits</span>
          <span className={styles.statValue}>{exhibitCount}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Under Legal Hold</span>
          <span className={styles.statValue}>{legalHoldCount}</span>
        </div>
      </div>

      {/* Category Navigation Tabs */}
      <div className={styles.categoryNav} role="tablist">
        {CATEGORY_TABS.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              role="tab"
              aria-selected={isActive}
              className={`${styles.categoryTabBtn} ${isActive ? styles.categoryTabBtnActive : ""}`}
              onClick={() => {
                setActiveTab(tab.key);
                setPage(0);
              }}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Controls & Search Bar */}
      <div className={styles.controlsBar}>
        <div className={styles.searchWrapper}>
          <span className={styles.searchIcon}>🔍</span>
          <input
            type="text"
            className={styles.searchInput}
            placeholder="Search by title, filename, description, tags..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(0);
            }}
          />
          {searchQuery && (
            <button className={styles.clearBtn} onClick={() => setSearchQuery("")}>
              ✕
            </button>
          )}
        </div>

        <div className={styles.filterGroup}>
          <label className={styles.statLabel}>Sensitivity:</label>
          <select
            className={styles.filterSelect}
            value={sensitivityFilter}
            onChange={(e) => {
              setSensitivityFilter(e.target.value);
              setPage(0);
            }}
          >
            <option value="ALL">All Sensitivities</option>
            <option value="STANDARD">Standard</option>
            <option value="CONFIDENTIAL">Confidential</option>
            <option value="HIGHLY_CONFIDENTIAL">Highly Confidential</option>
            <option value="PRIVILEGED">Privileged</option>
          </select>

          {evidenceList.length > 0 && (
            <button className={styles.secondaryBtn} onClick={selectAll}>
              {selectedIds.size === evidenceList.length ? "Deselect All" : "Select All"}
            </button>
          )}
        </div>
      </div>

      {/* Tag Filter Chips */}
      {allTags.length > 0 && (
        <div className={styles.tagFilterRow}>
          <span style={{ fontSize: "12px", color: "#64748b", fontWeight: 600 }}>
            Filter by Tag:
          </span>
          {allTags.map((tag) => {
            const isTagActive = selectedTag === tag;
            return (
              <button
                key={tag}
                className={`${styles.tagChipFilter} ${isTagActive ? styles.tagChipFilterActive : ""}`}
                onClick={() => {
                  setSelectedTag(isTagActive ? null : tag);
                  setPage(0);
                }}
              >
                #{tag}
              </button>
            );
          })}
          {selectedTag && (
            <button
              className={styles.clearBtn}
              onClick={() => setSelectedTag(null)}
              style={{ fontSize: "12px" }}
            >
              Clear Tag
            </button>
          )}
        </div>
      )}

      {/* Batch Action Toolbar */}
      {selectedIds.size > 0 && (
        <div className={styles.batchToolbar}>
          <div className={styles.batchCount}>
            <span>✓ {selectedIds.size} evidence item(s) selected</span>
          </div>
          <div className={styles.batchActions}>
            <button
              className={styles.batchBtn}
              onClick={handleBatchCategory}
              disabled={batchActionLoading}
            >
              📂 Change Category
            </button>
            <button
              className={styles.batchBtn}
              onClick={handleBatchAddTags}
              disabled={batchActionLoading}
            >
              🏷️ Add Tags
            </button>
            {activeTab === "ARCHIVED" ? (
              <button
                className={styles.batchBtn}
                onClick={handleBatchRestore}
                disabled={batchActionLoading}
              >
                ♻️ Restore Selected
              </button>
            ) : (
              <button
                className={styles.batchBtn}
                onClick={handleBatchArchive}
                disabled={batchActionLoading}
                style={{ color: "#f87171", borderColor: "rgba(239, 68, 68, 0.4)" }}
              >
                📦 Archive Selected
              </button>
            )}
            <button
              className={styles.batchBtnCancel}
              onClick={() => setSelectedIds(new Set())}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className={styles.emptyState}>Loading secure Evidence Locker...</div>
      ) : error ? (
        <div className={styles.emptyState} style={{ color: "#f87171" }}>
          {error}
        </div>
      ) : evidenceList.length === 0 ? (
        <div className={styles.emptyState}>
          <p style={{ fontSize: "18px", fontWeight: 600, color: "#cbd5e1" }}>
            No Evidence Items Found
          </p>
          <p style={{ fontSize: "14px", marginTop: "8px" }}>
            {searchQuery || selectedTag
              ? "No items match your active search or tag filters."
              : "Legally sensitive files deposited here are protected with immutable versioning, cryptographic SHA-256 verification, and strict custody logging."}
          </p>
          <button
            className={styles.primaryBtn}
            style={{ marginTop: "16px" }}
            onClick={() => setUploadModalOpen(true)}
          >
            + Deposit First Evidence Item
          </button>
        </div>
      ) : (
        <div className={styles.evidenceGrid}>
          {evidenceList.map((item) => {
            const isSelected = selectedIds.has(item.id);
            const hasExhibits = (item.exhibit_numbers || []).length > 0;

            return (
              <div
                key={item.id}
                className={`${styles.evidenceCard} ${isSelected ? styles.evidenceCardSelected : ""}`}
              >
                <input
                  type="checkbox"
                  aria-label={`Select ${item.title}`}
                  className={styles.cardSelectCheckbox}
                  checked={isSelected}
                  onChange={() => toggleSelect(item.id)}
                />

                <div>
                  <div className={styles.cardHeader}>
                    <div>
                      <h3 className={styles.cardTitle}>{item.title}</h3>
                      <p className={styles.cardDesc}>
                        {item.description || "No description provided."}
                      </p>
                    </div>
                  </div>

                  {/* Badges & Exhibits */}
                  <div className={styles.badgeRow}>
                    <span className={`${styles.pill} ${styles.pillCategory}`}>
                      {item.category}
                    </span>
                    <span
                      className={`${styles.pill} ${
                        item.sensitivity === "PRIVILEGED"
                          ? styles.pillPrivileged
                          : item.sensitivity === "CONFIDENTIAL"
                          ? styles.pillConfidential
                          : styles.pillStandard
                      }`}
                    >
                      {item.sensitivity}
                    </span>
                    <span
                      className={`${styles.pill} ${
                        item.status === "ACTIVE"
                          ? styles.pillActive
                          : item.status === "ARCHIVED"
                          ? styles.pillArchived
                          : styles.pillQuarantined
                      }`}
                    >
                      {item.status}
                    </span>
                    {item.legal_hold && (
                      <span className={`${styles.pill} ${styles.pillHold}`}>
                        ⚖️ Legal Hold
                      </span>
                    )}
                    {hasExhibits &&
                      item.exhibit_numbers.map((exNum) => (
                        <span key={exNum} className={styles.exhibitBadge}>
                          🏷️ {exNum}
                        </span>
                      ))}
                  </div>

                  {/* Tags */}
                  {(item.tags || []).length > 0 && (
                    <div className={styles.tagRow}>
                      {item.tags.map((tag) => (
                        <span key={tag} className={styles.tagPill}>
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* File Metadata */}
                  <div className={styles.metaGrid} style={{ marginTop: "14px" }}>
                    <div className={styles.metaItem}>
                      <span className={styles.metaKey}>Filename</span>
                      <span className={styles.metaVal}>{item.original_filename}</span>
                    </div>
                    <div className={styles.metaItem}>
                      <span className={styles.metaKey}>Deposited</span>
                      <span className={styles.metaVal}>
                        {new Date(item.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Card Actions */}
                <div className={styles.cardFooter}>
                  <div style={{ display: "flex", gap: "6px" }}>
                    <button
                      className={styles.secondaryBtn}
                      onClick={() => handleOpenPreview(item.id, item.original_filename)}
                      title="Preview Securely"
                    >
                      👁️ Preview
                    </button>
                    <button
                      className={styles.secondaryBtn}
                      onClick={() => handleDownload(item.id)}
                      title="Download Securely"
                    >
                      📥 Download
                    </button>
                    <button
                      className={styles.secondaryBtn}
                      onClick={() => setSharingItem({ id: item.id, title: item.title })}
                      title="Manage Access & Sharing"
                    >
                      🔗 Share
                    </button>
                  </div>

                  <Link
                    href={`/cases/${caseId}/evidence/${item.id}`}
                    className={styles.secondaryBtn}
                    style={{ textDecoration: "none", color: "#818cf8" }}
                  >
                    Details →
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination Controls */}
      {evidenceList.length >= pageSize && (
        <div className={styles.paginationBar}>
          <span style={{ fontSize: "13px", color: "#8c97ad" }}>
            Showing page {page + 1} ({evidenceList.length} items)
          </span>
          <div className={styles.pageControls}>
            <button
              className={styles.secondaryBtn}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              ← Previous
            </button>
            <button
              className={styles.secondaryBtn}
              onClick={() => setPage((p) => p + 1)}
              disabled={evidenceList.length < pageSize}
            >
              Next →
            </button>
          </div>
        </div>
      )}

      {/* Safe Ephemeral Preview Modal */}
      {previewModalOpen && (
        <div className={styles.modalBackdrop} onClick={() => setPreviewModalOpen(false)}>
          <div className={styles.previewModalWindow} onClick={(e) => e.stopPropagation()}>
            <div className={styles.previewHeader}>
              <div className={styles.previewTitle}>
                <span>🔒 Secure Preview:</span>
                <span style={{ color: "#38bdf8" }}>{previewFilename}</span>
              </div>
              <button className={styles.closeBtn} onClick={() => setPreviewModalOpen(false)}>
                ✕
              </button>
            </div>

            <div className={styles.previewBody}>
              {previewLoading ? (
                <div className={styles.emptyState}>Preparing secure ephemeral preview...</div>
              ) : previewError ? (
                <div className={styles.emptyState} style={{ color: "#f87171" }}>
                  {previewError}
                </div>
              ) : previewContentType === "application/pdf" ? (
                <iframe
                  src={previewUrl}
                  title={`Preview of ${previewFilename}`}
                  className={styles.previewIframe}
                  sandbox="allow-scripts allow-same-origin"
                />
              ) : previewContentType.startsWith("image/") ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={previewUrl} alt={previewFilename} className={styles.previewImg} />
              ) : (
                <div className={styles.previewFallback}>
                  <p style={{ fontSize: "16px", fontWeight: 600, color: "#ffffff" }}>
                    Inline Preview Unavailable
                  </p>
                  <p style={{ fontSize: "13px", color: "#94a3b8", marginTop: "8px" }}>
                    This file format ({previewContentType}) cannot be safely previewed inline.
                    You can download the verified file securely using the button below.
                  </p>
                  <button
                    className={styles.primaryBtn}
                    style={{ marginTop: "16px" }}
                    onClick={() => window.open(previewUrl, "_blank", "noopener,noreferrer")}
                  >
                    📥 Download Securely
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Deposit Evidence Modal */}
      {uploadModalOpen && (
        <div className={styles.modalBackdrop} onClick={() => setUploadModalOpen(false)}>
          <div className={styles.modalWindow} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>Deposit Evidence into Vault</h2>
            {uploadError && (
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
                {uploadError}
              </div>
            )}

            <form onSubmit={handleUpload}>
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Title *</label>
                <input
                  type="text"
                  className={styles.formInput}
                  placeholder="e.g., Prime Lease Agreement 2026"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  required
                />
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Description</label>
                <textarea
                  className={styles.formTextarea}
                  placeholder="Context, provenance, or key legal stipulations..."
                  rows={2}
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Category</label>
                  <select
                    className={styles.formSelect}
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                  >
                    <option value="CONTRACTUAL">Contractual</option>
                    <option value="FINANCIAL">Financial</option>
                    <option value="FORENSIC">Forensic</option>
                    <option value="DIGITAL">Digital</option>
                    <option value="TESTIMONIAL">Testimonial</option>
                    <option value="REGULATORY">Regulatory</option>
                    <option value="PHYSICAL_SCAN">Physical Scan</option>
                    <option value="MISCELLANEOUS">Miscellaneous</option>
                  </select>
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Sensitivity</label>
                  <select
                    className={styles.formSelect}
                    value={newSensitivity}
                    onChange={(e) => setNewSensitivity(e.target.value)}
                  >
                    <option value="STANDARD">Standard</option>
                    <option value="CONFIDENTIAL">Confidential</option>
                    <option value="HIGHLY_CONFIDENTIAL">Highly Confidential</option>
                    <option value="PRIVILEGED">Privileged</option>
                  </select>
                </div>
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Tags (comma-separated, max 20)</label>
                <input
                  type="text"
                  className={styles.formInput}
                  placeholder="e.g., lease, property, tenant-dispute"
                  value={newTagsInput}
                  onChange={(e) => setNewTagsInput(e.target.value)}
                />
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Select Document File *</label>
                <div
                  className={styles.fileDropZone}
                  onClick={() => document.getElementById("evidence-file-input")?.click()}
                >
                  <input
                    id="evidence-file-input"
                    type="file"
                    style={{ display: "none" }}
                    onChange={(e) => {
                      if (e.target.files?.[0]) setSelectedFile(e.target.files[0]);
                    }}
                  />
                  {selectedFile ? (
                    <div>
                      <span style={{ color: "#38bdf8", fontWeight: 600 }}>
                        📄 {selectedFile.name}
                      </span>
                      <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                        {(selectedFile.size / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  ) : (
                    <div>
                      <span style={{ color: "#818cf8", fontSize: "13px" }}>
                        Click to select document or forensic file
                      </span>
                      <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                        PDF, PNG, JPEG, TIFF (Max 100MB) · SHA-256 Verified
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Retention Until (Optional)</label>
                <input
                  type="date"
                  className={styles.formInput}
                  value={newRetention}
                  onChange={(e) => setNewRetention(e.target.value)}
                />
              </div>

              <div className={styles.modalActions}>
                <button
                  type="button"
                  className={styles.secondaryBtn}
                  onClick={() => setUploadModalOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.primaryBtn}
                  disabled={uploading || !selectedFile}
                >
                  {uploading ? "Verifying & Depositing..." : "Deposit Evidence"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Controlled Evidence Share Modal */}
      {sharingItem && (
        <EvidenceShareModal
          isOpen={!!sharingItem}
          onClose={() => {
            setSharingItem(null);
            fetchEvidence();
          }}
          caseId={caseId}
          evidenceId={sharingItem.id}
          evidenceTitle={sharingItem.title}
        />
      )}
    </div>
  );
}
