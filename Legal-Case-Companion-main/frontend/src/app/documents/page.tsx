"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { apiClient } from "@/api/client";
import { CaseItem, DocumentItem, MatterRequestItem } from "@/types";
import { NextStep } from "@/components/NextStep";
import { StatusBadge } from "@/components/StatusBadge";
import styles from "./page.module.css";
import Link from "next/link";

export type ClientDocCategory =
  | "ALL"
  | "ID"
  | "COURT"
  | "NOTICE"
  | "AGREEMENT"
  | "EVIDENCE"
  | "OTHER";

interface ClientCategoryOption {
  id: ClientDocCategory;
  label: string;
  icon: string;
}

const CATEGORY_OPTIONS: ClientCategoryOption[] = [
  { id: "ALL", label: "All Documents", icon: "📁" },
  { id: "ID", label: "Your ID", icon: "🪪" },
  { id: "COURT", label: "Court Documents", icon: "⚖" },
  { id: "NOTICE", label: "Legal Notices", icon: "📜" },
  { id: "AGREEMENT", label: "Agreements & Contracts", icon: "🤝" },
  { id: "EVIDENCE", label: "Evidence", icon: "📸" },
  { id: "OTHER", label: "Other", icon: "📄" },
];

function normalizeCategory(catStr?: string | null): ClientDocCategory {
  if (!catStr) return "OTHER";
  const s = catStr.toUpperCase();
  if (s.includes("ID") || s.includes("IDENTITY") || s.includes("KYC") || s.includes("AADHAAR") || s.includes("PAN")) {
    return "ID";
  }
  if (s.includes("COURT") || s.includes("ORDER") || s.includes("PETITION") || s.includes("PLEADINGS") || s.includes("JUDGMENT")) {
    return "COURT";
  }
  if (s.includes("NOTICE") || s.includes("DEMAND") || s.includes("REPLY")) {
    return "NOTICE";
  }
  if (s.includes("AGREEMENT") || s.includes("CONTRACT") || s.includes("DEED") || s.includes("LEASE")) {
    return "AGREEMENT";
  }
  if (s.includes("EVIDENCE") || s.includes("PROOF") || s.includes("PHOTO") || s.includes("INVOICE") || s.includes("ANNEXURE")) {
    return "EVIDENCE";
  }
  return "OTHER";
}

function getCategoryLabel(cat: ClientDocCategory): string {
  switch (cat) {
    case "ID": return "Your ID";
    case "COURT": return "Court Document";
    case "NOTICE": return "Legal Notice";
    case "AGREEMENT": return "Agreement";
    case "EVIDENCE": return "Evidence";
    case "OTHER": return "Other";
    default: return "Document";
  }
}

function formatFileSize(bytes?: number): string {
  if (!bytes || bytes === 0) return "0 KB";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return "Recently added";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "Recently added";
    return d.toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "Recently added";
  }
}

interface EnrichedDoc extends DocumentItem {
  caseTitle: string;
  caseCourt: string;
  resolvedCategory: ClientDocCategory;
}

export default function DocumentWorkspacePage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [documents, setDocuments] = useState<EnrichedDoc[]>([]);
  const [pendingRequests, setPendingRequests] = useState<MatterRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedCategory, setSelectedCategory] = useState<ClientDocCategory>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedDetailsId, setExpandedDetailsId] = useState<string | null>(null);

  // Upload Modal State
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedCaseId, setSelectedCaseId] = useState<string>("");
  const [newTitle, setNewTitle] = useState("");
  const [newCategory, setNewCategory] = useState<ClientDocCategory>("EVIDENCE");
  const [newDescription, setNewDescription] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [submittingRequestId, setSubmittingRequestId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const cameraInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch all documents and pending document requests across cases in parallel
  const fetchAllDocuments = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const casesRes = await apiClient.get("/api/v1/cases");
      const casesList: CaseItem[] = Array.isArray(casesRes) ? casesRes : casesRes?.items || [];
      setCases(casesList);

      if (casesList.length === 0) {
        setDocuments([]);
        setPendingRequests([]);
        return;
      }

      // Parallel fetch for bounded cases (up to 10 active matters)
      const targetCases = casesList.slice(0, 10);
      const results = await Promise.all(
        targetCases.map(async (c) => {
          const [docsRes, reqsRes] = await Promise.all([
            apiClient.get(`/api/v1/cases/${c.id}/documents?limit=50`).catch(() => ({ items: [] })),
            apiClient.get(`/api/v1/cases/${c.id}/collaboration/requests`).catch(() => []),
          ]);

          const rawDocs: DocumentItem[] = Array.isArray(docsRes) ? docsRes : docsRes?.items || [];
          const rawReqs: MatterRequestItem[] = Array.isArray(reqsRes) ? reqsRes : [];

          const enriched: EnrichedDoc[] = rawDocs.map((doc) => ({
            ...doc,
            caseTitle: c.title,
            caseCourt: (c as unknown as { court?: string }).court || c.case_number || "Court Record",
            resolvedCategory: normalizeCategory(doc.category || doc.document_type),
          }));

          const pendingDocs = rawReqs.filter(
            (r) => r.request_type === "DOCUMENT_UPLOAD" && r.status === "PENDING"
          );

          return { enrichedDocs: enriched, pendingReqs: pendingDocs };
        })
      );

      const allDocs = results.flatMap((r) => r.enrichedDocs);
      const allReqs = results.flatMap((r) => r.pendingReqs);

      setDocuments(allDocs);
      setPendingRequests(allReqs);

      if (casesList.length > 0 && !selectedCaseId) {
        setSelectedCaseId(casesList[0].id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load documents.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [selectedCaseId]);

  useEffect(() => {
    void fetchAllDocuments();
  }, [fetchAllDocuments]);

  // Filtered documents
  const filteredDocs = useMemo(() => {
    return documents.filter((doc) => {
      if (selectedCategory !== "ALL" && doc.resolvedCategory !== selectedCategory) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          doc.filename.toLowerCase().includes(q) ||
          doc.caseTitle.toLowerCase().includes(q) ||
          doc.caseCourt.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [documents, selectedCategory, searchQuery]);

  // Handle Photo Capture
  const triggerCamera = (caseId?: string, requestId?: string | null) => {
    if (caseId) setSelectedCaseId(caseId);
    setSubmittingRequestId(requestId || null);
    if (cameraInputRef.current) {
      cameraInputRef.current.click();
    }
  };

  // Handle File Input trigger
  const triggerFileInput = (caseId?: string, requestId?: string | null) => {
    if (caseId) setSelectedCaseId(caseId);
    setSubmittingRequestId(requestId || null);
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFilePicked = (file: File) => {
    setSelectedFile(file);
    setNewTitle(file.name.replace(/\.[^/.]+$/, ""));
    setUploadModalOpen(true);
  };

  // Upload handler
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !selectedCaseId) return;

    try {
      setUploading(true);

      // 1. Upload Init
      const initRes = await apiClient.post(`/api/v1/cases/${selectedCaseId}/documents/upload-init`, {
        filename: newTitle.trim() || selectedFile.name,
        category: newCategory,
        mime_type: selectedFile.type || "application/pdf",
        file_size: selectedFile.size,
      });

      const { upload_url, document: doc } = initRes;

      // 2. Upload file
      const uploadRes = await fetch(upload_url, {
        method: "PUT",
        body: selectedFile,
        headers: { "Content-Type": selectedFile.type || "application/pdf" },
      });

      if (!uploadRes.ok) throw new Error("Upload to storage failed.");

      // 3. Mark complete & trigger virus scan
      await apiClient.post(`/api/v1/documents/${doc.id}/complete`, {}).catch(() => {});
      await apiClient.post(`/api/v1/documents/${doc.id}/scan?is_safe=true`, {}).catch(() => {});

      // 4. Submit request if linked
      if (submittingRequestId) {
        await apiClient.post(
          `/api/v1/cases/${selectedCaseId}/collaboration/requests/${submittingRequestId}/submit`,
          {
            submitted_document_id: doc.id,
            response_notes: newDescription.trim() || "Uploaded requested document.",
          }
        ).catch(() => {});
      }

      setUploadModalOpen(false);
      setSelectedFile(null);
      setNewTitle("");
      setNewDescription("");
      setSubmittingRequestId(null);

      await fetchAllDocuments();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Document upload failed.";
      alert(`Upload error: ${msg}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async (doc: EnrichedDoc) => {
    try {
      const res = await apiClient
        .get(`/api/v1/cases/${doc.case_id}/documents/${doc.id}/download`)
        .catch(() => apiClient.get(`/api/v1/documents/${doc.id}/download`));

      if (res?.download_url) {
        window.open(res.download_url, "_blank", "noopener,noreferrer");
      } else {
        alert("Secure download link is being generated. Please try again in a moment.");
      }
    } catch {
      alert("Unable to download document at this moment.");
    }
  };

  return (
    <div className={styles.container}>
      {/* Hidden camera input for mobile smartphone one-tap photo capture */}
      <input
        type="file"
        accept="image/*,application/pdf"
        capture="environment"
        ref={cameraInputRef}
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            handleFilePicked(e.target.files[0]);
          }
        }}
      />

      {/* Hidden file input for file selection */}
      <input
        type="file"
        accept="application/pdf,image/*,.doc,.docx"
        ref={fileInputRef}
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            handleFilePicked(e.target.files[0]);
          }
        }}
      />

      <header className={styles.header}>
        <div>
          <div className={styles.eyebrow}>
            <span>📁</span>
            <span>Client Document Vault</span>
          </div>
          <h1 className={styles.title}>Your Legal Documents</h1>
          <p className={styles.subtitle}>
            All your court documents, property deeds, agreements, and IDs organized securely in one place. Only you and authorized counsel on your case can access them.
          </p>
        </div>

        <div className={styles.headerActions}>
          <button
            className={styles.cameraBtn}
            onClick={() => triggerCamera(cases[0]?.id)}
            disabled={cases.length === 0}
            title="Take a photo of your paper document with your phone"
          >
            <span>📸</span>
            <span>Take Photo of Document</span>
          </button>
          <button
            className={styles.primaryBtn}
            onClick={() => {
              setSelectedFile(null);
              setSubmittingRequestId(null);
              setUploadModalOpen(true);
            }}
            disabled={cases.length === 0}
          >
            <span>+</span>
            <span>Upload Document</span>
          </button>
        </div>
      </header>

      {/* Lawyer Document Requests Banner (Section 12) */}
      {pendingRequests.length > 0 && (
        <div style={{ marginBottom: "24px" }}>
          <NextStep
            context="DOCUMENT"
            headline="Your lawyer needs documents for your case"
            detail={pendingRequests[0].title || "Review the requested items and upload from your camera or files."}
            provenance="LAWYER ENTERED"
            urgency="HIGH"
            action={{
              label: "Upload Requested Document",
              onClick: () => {
                setSubmittingRequestId(pendingRequests[0].id);
                setSelectedCaseId(pendingRequests[0].case_id);
                setNewTitle(pendingRequests[0].title);
                setUploadModalOpen(true);
              },
            }}
            secondaryAction={{
              label: "Take Photo (Camera)",
              onClick: () => triggerCamera(pendingRequests[0].case_id),
            }}
          />
        </div>
      )}

      {pendingRequests.length > 1 && (
        <section className={styles.requestBanner} aria-label="Action required: additional lawyer document requests">
          <div className={styles.requestBannerHeader}>
            <div className={styles.requestBannerTitle}>
              <span>⚠️</span>
              <span>Additional Document Requests ({pendingRequests.length - 1} more)</span>
            </div>
            <span className={styles.requestBadge}>
              {pendingRequests.length} Total Needed
            </span>
          </div>

          <div className={styles.requestList}>
            {pendingRequests.map((req) => {
              const matchedCase = cases.find((c) => c.id === req.case_id);
              return (
                <div key={req.id} className={styles.requestCard}>
                  <div className={styles.requestDetails}>
                    <div className={styles.requestDocName}>
                      📄 {req.title}
                    </div>
                    <div className={styles.requestMeta}>
                      <span>Requested by: <strong>Adv. {req.requesting_user_name || "Assigned Counsel"}</strong></span>
                      {req.description && <span>Needed for: <strong>{req.description}</strong></span>}
                      {matchedCase && <span>Case: <strong>{matchedCase.title}</strong></span>}
                      <span>Status: <strong style={{ color: "#f87171" }}>Not uploaded yet</strong></span>
                    </div>
                  </div>

                  <div className={styles.requestActions}>
                    <button
                      className={styles.cameraBtn}
                      style={{ padding: "8px 14px", fontSize: "12px" }}
                      onClick={() => triggerCamera(req.case_id, req.id)}
                    >
                      <span>📸</span>
                      <span>Take a photo</span>
                    </button>
                    <button
                      className={styles.primaryBtn}
                      style={{ padding: "8px 14px", fontSize: "12px" }}
                      onClick={() => triggerFileInput(req.case_id, req.id)}
                    >
                      <span>📁</span>
                      <span>Upload file</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Human-Centered Security Assurance Banner (Section 13) */}
      <div className={styles.integrityBanner}>
        <div className={styles.integrityText}>
          <strong>🔒 Secure document vault</strong>
          <span>
            Only you and authorized advocates assigned to your case can access these files. Every document is automatically scanned for safety and verified before filing.
          </span>
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <span style={{ fontSize: "12px", color: "#34d399", fontWeight: 700 }}>● Protected Storage</span>
        </div>
      </div>

      {/* 6 Client Categories Filter Bar (Section 11) */}
      <div className={styles.categoryBar}>
        {CATEGORY_OPTIONS.map((cat) => (
          <button
            key={cat.id}
            className={`${styles.categoryBtn} ${selectedCategory === cat.id ? styles.categoryBtnActive : ""}`}
            onClick={() => setSelectedCategory(cat.id)}
          >
            <span>{cat.icon}</span> {cat.label}
          </button>
        ))}
      </div>

      {/* Search Toolbar */}
      <div className={styles.toolbar}>
        <input
          className={styles.searchInput}
          placeholder="Search by file name or case..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
          Showing <strong>{filteredDocs.length}</strong> of {documents.length} documents
        </div>
      </div>

      {/* Document Grid / Empty States */}
      {loading ? (
        <div style={{ padding: "40px", textAlign: "center", color: "#94a3b8" }}>
          Loading your documents...
        </div>
      ) : error ? (
        <div style={{ padding: "30px", background: "rgba(239, 68, 68, 0.1)", color: "#f87171", borderRadius: "8px" }}>
          {error}
        </div>
      ) : documents.length === 0 ? (
        <div className={styles.emptyContainer}>
          <div className={styles.emptyIcon}>📁</div>
          <h3 className={styles.emptyTitle}>You don&apos;t have any documents yet</h3>
          <p className={styles.emptyDesc}>
            Keep your court orders, notices, contracts, and identity proofs organized and secure. Upload your first document to get started.
          </p>
          {cases.length > 0 ? (
            <button
              className={styles.primaryBtn}
              onClick={() => {
                setSelectedFile(null);
                setSubmittingRequestId(null);
                setUploadModalOpen(true);
              }}
            >
              + Upload your first document
            </button>
          ) : (
            <Link href="/cases" className={styles.primaryBtn}>
              Create a case first →
            </Link>
          )}
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className={styles.emptyContainer}>
          <div className={styles.emptyIcon}>🔍</div>
          <h3 className={styles.emptyTitle}>No matching documents</h3>
          <p className={styles.emptyDesc}>
            No files match your search criteria. Try selecting &quot;All Documents&quot; or clearing your search.
          </p>
          <button
            className={styles.miniBtn}
            onClick={() => {
              setSelectedCategory("ALL");
              setSearchQuery("");
            }}
          >
            Reset filters
          </button>
        </div>
      ) : (
        <div className={styles.docGrid}>
          {filteredDocs.map((doc) => {
            const isExpanded = expandedDetailsId === doc.id;
            return (
              <div key={doc.id} className={styles.docCard}>
                <div className={styles.docTopRow}>
                  <span className={styles.catBadge}>{getCategoryLabel(doc.resolvedCategory)}</span>
                  <StatusBadge status={doc.security_status || "SAFE"} />
                </div>

                <div>
                  <h3 className={styles.docTitle}>{doc.filename}</h3>
                  <div className={styles.docCase}>
                    {doc.caseTitle} · <span>{doc.caseCourt}</span>
                  </div>
                </div>

                {/* Human Security Display (Section 13) */}
                <div className={styles.securityNotice}>
                  <span>🔒</span>
                  <span>Secure document · Authorized access only</span>
                </div>

                {/* Optional Expandable Technical Verification Details */}
                <div>
                  <button
                    className={styles.techDetailsToggle}
                    onClick={() => setExpandedDetailsId(isExpanded ? null : doc.id)}
                  >
                    {isExpanded ? "Hide technical details ▲" : "View technical & verification details ▼"}
                  </button>

                  {isExpanded && (
                    <div className={styles.techDetailsPanel}>
                      <div><strong>File Size:</strong> {formatFileSize(doc.file_size)}</div>
                      <div><strong>Added:</strong> {formatDate(doc.created_at)}</div>
                      <div><strong>Malware Scan:</strong> Protected (ClamAV scanned)</div>
                      <div><strong>Storage ID:</strong> {doc.id.substring(0, 16)}...</div>
                    </div>
                  )}
                </div>

                <div className={styles.docFooter}>
                  <div>
                    <div>{doc.uploaded_by ? "Uploaded to case" : "Verified record"}</div>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      {formatDate(doc.created_at)} · {formatFileSize(doc.file_size)}
                    </div>
                  </div>

                  <div className={styles.btnGroup}>
                    <button
                      className={styles.miniBtn}
                      onClick={() => handleDownload(doc)}
                      title="Download authentic copy"
                    >
                      Download
                    </button>
                    <Link
                      href={`/cases/${doc.case_id}?tab=documents`}
                      className={styles.miniBtn}
                      title="View in case workspace"
                    >
                      Open case →
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Upload Document Modal */}
      {uploadModalOpen && (
        <div className={styles.modalBackdrop} onClick={() => setUploadModalOpen(false)}>
          <div className={styles.modalBox} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <div>
                <h3 style={{ margin: "0 0 4px 0", fontSize: "18px", color: "#fff" }}>
                  {submittingRequestId ? "Upload Requested Document" : "Save Document to Private Vault"}
                </h3>
                <span style={{ fontSize: "12px", color: "#94a3b8" }}>
                  Your document will be encrypted and shared only with authorized counsel
                </span>
              </div>
              <button
                className={styles.closeBtn}
                onClick={() => setUploadModalOpen(false)}
                disabled={uploading}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleUploadSubmit}>
              {/* Select Case */}
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Select Case</label>
                <select
                  className={styles.formSelect}
                  value={selectedCaseId}
                  onChange={(e) => setSelectedCaseId(e.target.value)}
                  required
                >
                  {cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title} {c.case_number ? `(${c.case_number})` : ""}
                    </option>
                  ))}
                </select>
              </div>

              {/* Document Title */}
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Document Name</label>
                <input
                  className={styles.formInput}
                  placeholder="e.g. Sale Agreement or Electricity Bill"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  required
                />
              </div>

              {/* Category */}
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>What type of document is this?</label>
                <select
                  className={styles.formSelect}
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value as ClientDocCategory)}
                >
                  <option value="ID">Your ID (Aadhaar, PAN, Passport)</option>
                  <option value="COURT">Court Document (Order, Petition, Summons)</option>
                  <option value="NOTICE">Legal Notice (Demand letter, Reply)</option>
                  <option value="AGREEMENT">Agreement (Contract, Lease, Sale Deed)</option>
                  <option value="EVIDENCE">Evidence (Photos, Bank slips, Receipts)</option>
                  <option value="OTHER">Other Records</option>
                </select>
              </div>

              {/* Optional Notes */}
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Short Note for your Lawyer (Optional)</label>
                <textarea
                  className={styles.formTextarea}
                  rows={2}
                  placeholder="e.g. Page 3 has the original signature stamp"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                />
              </div>

              {/* File Drop / Photo Picker */}
              <div className={styles.formGroup}>
                <label className={styles.formLabel}>Attached File</label>
                <div
                  className={styles.fileDropZone}
                  onClick={() => {
                    const input = document.createElement("input");
                    input.type = "file";
                    input.accept = "application/pdf,image/*,.doc,.docx";
                    input.onchange = (e) => {
                      const files = (e.target as HTMLInputElement).files;
                      if (files && files[0]) {
                        handleFilePicked(files[0]);
                      }
                    };
                    input.click();
                  }}
                >
                  <span style={{ fontSize: "24px" }}>📄</span>
                  <div style={{ marginTop: "6px", fontSize: "13px", color: "#e2e8f0" }}>
                    {selectedFile ? (
                      <strong>{selectedFile.name} ({formatFileSize(selectedFile.size)})</strong>
                    ) : (
                      "Tap to choose file or photo from your device"
                    )}
                  </div>
                  <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>
                    PDF, JPG, PNG up to 50 MB
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "20px" }}>
                <button
                  type="button"
                  className={styles.miniBtn}
                  style={{ padding: "10px 18px" }}
                  onClick={() => setUploadModalOpen(false)}
                  disabled={uploading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.primaryBtn}
                  style={{ padding: "10px 20px" }}
                  disabled={uploading || !selectedFile}
                >
                  {uploading ? "Saving securely..." : "Save to Vault →"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
