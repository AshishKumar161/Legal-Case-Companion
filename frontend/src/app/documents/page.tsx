"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { apiClient } from "@/api/client";
import { CaseItem, DocumentItem, MatterRequestItem } from "@/types";
import {
  DocumentIcon,
  PlusIcon,
  ShieldIcon,
  CameraIcon,
} from "@/components/ui/Icons";
import { DocumentCard } from "@/components/ui/DocumentCard";
import { SearchBar } from "@/components/ui/SearchBar";
import styles from "./page.module.css";

export type ClientDocCategory =
  | "ALL"
  | "COURT"
  | "IDENTITY"
  | "EVIDENCE"
  | "LAWYER"
  | "OTHER";

interface ClientCategoryOption {
  id: ClientDocCategory;
  label: string;
}

const CATEGORY_OPTIONS: ClientCategoryOption[] = [
  { id: "ALL", label: "All" },
  { id: "COURT", label: "Court" },
  { id: "IDENTITY", label: "Identity" },
  { id: "EVIDENCE", label: "Evidence" },
  { id: "LAWYER", label: "Lawyer" },
  { id: "OTHER", label: "Other" },
];

function normalizeCategory(catStr?: string | null): ClientDocCategory {
  if (!catStr) return "OTHER";
  const s = catStr.toUpperCase();
  if (s.includes("ID") || s.includes("IDENTITY") || s.includes("KYC") || s.includes("AADHAAR") || s.includes("PAN") || s.includes("PASSPORT")) {
    return "IDENTITY";
  }
  if (s.includes("COURT") || s.includes("ORDER") || s.includes("PETITION") || s.includes("PLEADINGS") || s.includes("JUDGMENT") || s.includes("BENCH")) {
    return "COURT";
  }
  if (s.includes("LAWYER") || s.includes("ADVOCATE") || s.includes("VAKALATNAMA") || s.includes("OPINION") || s.includes("BRIEF")) {
    return "LAWYER";
  }
  if (s.includes("EVIDENCE") || s.includes("PROOF") || s.includes("PHOTO") || s.includes("INVOICE") || s.includes("RECEIPT") || s.includes("AGREEMENT") || s.includes("CONTRACT") || s.includes("DEED")) {
    return "EVIDENCE";
  }
  return "OTHER";
}

function getCategoryLabel(cat: ClientDocCategory): string {
  switch (cat) {
    case "IDENTITY": return "Identity";
    case "COURT": return "Court";
    case "LAWYER": return "Lawyer";
    case "EVIDENCE": return "Evidence";
    case "OTHER": return "Other";
    default: return "Document";
  }
}

interface EnrichedDoc extends DocumentItem {
  caseTitle: string;
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
  const [securityDetailsOpen, setSecurityDetailsOpen] = useState(false);

  // Upload Modal State (Section 15: 2-step flow)
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadStep, setUploadStep] = useState<1 | 2>(1);
  const [selectedCaseId, setSelectedCaseId] = useState<string>("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [newCategory, setNewCategory] = useState<string>("EVIDENCE");
  const [uploading, setUploading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const fetchAllDocuments = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const casesRes = await apiClient.get("/api/v1/cases").catch(() => ({ items: [] }));
      const casesList: CaseItem[] = Array.isArray(casesRes)
        ? casesRes
        : (casesRes as { items?: CaseItem[] })?.items || [];
      setCases(casesList);

      if (casesList.length > 0 && !selectedCaseId) {
        setSelectedCaseId(casesList[0].id);
      }

      const allDocs: EnrichedDoc[] = [];
      const allReqs: MatterRequestItem[] = [];

      await Promise.all(
        casesList.map(async (c) => {
          try {
            const [docsRes, reqsRes] = await Promise.all([
              apiClient.get<DocumentItem[]>(`/api/v1/cases/${c.id}/documents`).catch(() => []),
              apiClient.get<MatterRequestItem[]>(`/api/v1/cases/${c.id}/collaboration/requests`).catch(() => []),
            ]);

            const docsList: DocumentItem[] = Array.isArray(docsRes)
              ? docsRes
              : (docsRes as { items?: DocumentItem[] })?.items || [];

            for (const doc of docsList) {
              allDocs.push({
                ...doc,
                caseTitle: c.title,
                resolvedCategory: normalizeCategory(doc.category || doc.filename),
              });
            }

            if (Array.isArray(reqsRes)) {
              allReqs.push(...reqsRes.filter((r) => r.status === "PENDING" && r.request_type === "DOCUMENT_UPLOAD"));
            }
          } catch {
            // Ignore individual case errors
          }
        })
      );

      // Sort by newest first
      allDocs.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setDocuments(allDocs);
      setPendingRequests(allReqs);
    } catch {
      setError("Unable to load documents. Please check your connection.");
    } finally {
      setLoading(false);
    }
  }, [selectedCaseId]);

  useEffect(() => {
    void fetchAllDocuments();
  }, [fetchAllDocuments]);

  // Filter documents by category and search
  const filteredDocs = useMemo(() => {
    return documents.filter((doc) => {
      const matchesCat = selectedCategory === "ALL" || doc.resolvedCategory === selectedCategory;
      const matchesQuery =
        searchQuery === ""
          ? true
          : doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
            doc.caseTitle.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCat && matchesQuery;
    });
  }, [documents, selectedCategory, searchQuery]);

  // Download / View document
  const handleDownload = async (doc: EnrichedDoc) => {
    try {
      const res = await apiClient.get<{ download_url?: string }>(`/api/v1/cases/${doc.case_id}/documents/${doc.id}/download`);
      if (res?.download_url) {
        window.open(res.download_url, "_blank");
      }
    } catch {
      alert("Unable to open document. Please try again.");
    }
  };

  // Upload Submission
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !selectedCaseId) return;

    try {
      setUploading(true);
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("title", newTitle || selectedFile.name);
      formData.append("category", newCategory);

      await apiClient.post(`/api/v1/cases/${selectedCaseId}/documents`, formData);
      setUploadModalOpen(false);
      setUploadStep(1);
      setSelectedFile(null);
      setNewTitle("");
      void fetchAllDocuments();
    } catch {
      alert("Upload failed. Please ensure the file is under 50MB and try again.");
    } finally {
      setUploading(false);
    }
  };

  const handleFilePicked = (file: File) => {
    setSelectedFile(file);
    setNewTitle(file.name);
    setUploadStep(2);
  };

  const closeUploadModal = () => {
    if (uploading) return;
    setUploadModalOpen(false);
    setUploadStep(1);
    setSelectedFile(null);
    setNewTitle("");
  };

  return (
    <div className={styles.container}>
      {/* 1. Header (Section 14) */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Your Documents</h1>
          <p className={styles.subtitle}>
            All your important legal papers, court orders, and evidence in one place.
          </p>
        </div>

        <div className={styles.headerActions}>
          <button
            onClick={() => {
              setUploadStep(1);
              setUploadModalOpen(true);
            }}
            className="btn btn-primary"
            disabled={cases.length === 0}
          >
            <PlusIcon size={16} />
            <span>Upload Document</span>
          </button>
        </div>
      </div>

      {/* Action Notice Banner if lawyer requested a document */}
      {pendingRequests.length > 0 && (
        <div
          style={{
            background: "var(--surface-card, #FFFFFF)",
            border: "2px solid var(--status-urgent, #C53030)",
            borderRadius: "12px",
            padding: "18px 22px",
            marginBottom: "24px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "14px",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div>
            <div style={{ color: "var(--status-urgent, #C53030)", fontWeight: 700, fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Action Required · Document Needed by Your Lawyer
            </div>
            <div style={{ color: "var(--text-primary, #17212B)", fontSize: "16px", fontWeight: 700, marginTop: "3px" }}>
              {pendingRequests[0].title}
            </div>
            <div style={{ color: "var(--text-secondary, #52606D)", fontSize: "13px", marginTop: "2px" }}>
              {pendingRequests[0].description || "Your retained lawyer requested this document to proceed with your case."}
            </div>
          </div>
          <button
            onClick={() => {
              setUploadStep(1);
              setUploadModalOpen(true);
            }}
            className="btn btn-primary"
            style={{ fontSize: "13px", padding: "8px 18px" }}
          >
            Upload Requested File →
          </button>
        </div>
      )}

      {/* Security & Privacy Line */}
      <div className={styles.securityBanner}>
        <div className={styles.securityText}>
          <ShieldIcon size={16} color="var(--navy-primary)" />
          <span>Your documents are encrypted. Only you and authorized legal counsel can access them.</span>
        </div>
        <button
          type="button"
          onClick={() => setSecurityDetailsOpen((prev) => !prev)}
          className={styles.securityToggle}
        >
          {securityDetailsOpen ? "Hide details ▲" : "Security info ▼"}
        </button>
      </div>

      {securityDetailsOpen && (
        <div
          style={{
            background: "var(--surface-card, #FFFFFF)",
            border: "1px solid var(--border-subtle, #D9E2EC)",
            borderRadius: "10px",
            padding: "16px 20px",
            marginBottom: "24px",
            fontSize: "13px",
            color: "var(--text-secondary, #52606D)",
            lineHeight: "1.6",
          }}
        >
          <div>• Storage is scanned automatically for malicious content and encrypted at rest.</div>
          <div>• Access is strictly limited to authenticated participants of your active case.</div>
          <div>• You can view and download original, high-resolution copies at any time.</div>
        </div>
      )}

      {/* 2. Categories Filter (Section 14: All, Court, Identity, Evidence, Lawyer, Other) */}
      <div className={styles.categoryBar} role="tablist" aria-label="Document Categories">
        {CATEGORY_OPTIONS.map((cat) => (
          <button
            key={cat.id}
            role="tab"
            aria-selected={selectedCategory === cat.id}
            className={`${styles.categoryBtn} ${selectedCategory === cat.id ? styles.categoryBtnActive : ""}`}
            onClick={() => setSelectedCategory(cat.id)}
          >
            <span>{cat.label}</span>
          </button>
        ))}
      </div>

      {/* 3. Search Bar */}
      <div className={styles.toolbar}>
        <SearchBar
          placeholder="Search documents by name or case..."
          value={searchQuery}
          onChange={setSearchQuery}
        />

        <div style={{ fontSize: "14px", color: "var(--text-muted, #7B8794)" }}>
          Showing <strong>{filteredDocs.length}</strong> {filteredDocs.length === 1 ? "document" : "documents"}
        </div>
      </div>

      {/* 4. Document Grid */}
      {loading ? (
        <div style={{ padding: "60px 0", textAlign: "center", color: "var(--text-secondary, #52606D)" }}>
          Loading your documents...
        </div>
      ) : error ? (
        <div style={{ padding: "20px", background: "rgba(197, 48, 48, 0.08)", color: "var(--status-urgent, #C53030)", borderRadius: "10px", border: "1px solid rgba(197, 48, 48, 0.2)" }}>
          {error}
        </div>
      ) : documents.length === 0 ? (
        <div className={styles.emptyContainer}>
          <div className={styles.emptyIcon}>
            <DocumentIcon size={32} color="var(--navy-primary)" />
          </div>
          <h3 className={styles.emptyTitle}>No documents yet</h3>
          <p className={styles.emptyDesc}>
            Upload court notices, agreements, evidence, or identity documents to keep your case organized.
          </p>
          <button
            onClick={() => {
              setUploadStep(1);
              setUploadModalOpen(true);
            }}
            className="btn btn-primary"
            disabled={cases.length === 0}
          >
            <PlusIcon size={16} />
            <span>Upload your first document</span>
          </button>
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className={styles.emptyContainer}>
          <p style={{ color: "var(--text-secondary, #52606D)", fontSize: "15px" }}>
            No documents match &ldquo;{searchQuery}&rdquo;. Try choosing &quot;All&quot;.
          </p>
        </div>
      ) : (
        <div className={styles.docGrid}>
          {filteredDocs.map((doc) => (
            <DocumentCard
              key={doc.id}
              id={doc.id}
              title={doc.filename}
              categoryLabel={getCategoryLabel(doc.resolvedCategory)}
              uploadedDate={doc.created_at ? new Date(doc.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : undefined}
              fileSize={doc.file_size ? `${Math.round(doc.file_size / 1024)} KB` : undefined}
              onView={() => handleDownload(doc)}
              onDownload={() => handleDownload(doc)}
            />
          ))}
        </div>
      )}

      {/* Hidden native pickers */}
      <input
        type="file"
        ref={fileInputRef}
        accept=".pdf,.png,.jpg,.jpeg,.docx"
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            handleFilePicked(e.target.files[0]);
          }
        }}
      />
      <input
        type="file"
        ref={cameraInputRef}
        accept="image/*,application/pdf"
        capture="environment"
        style={{ display: "none" }}
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            handleFilePicked(e.target.files[0]);
          }
        }}
      />

      {/* 5. Upload Modal (Section 15: Add a document flow) */}
      {uploadModalOpen && (
        <div className={styles.modalBackdrop} onClick={closeUploadModal}>
          <div className={styles.modalBox} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3 className={styles.modalTitle}>Add a document</h3>
              <button
                className={styles.closeBtn}
                onClick={closeUploadModal}
                disabled={uploading}
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>

            {uploadStep === 1 ? (
              /* Step 1: "What would you like to upload?" */
              <div>
                <p style={{ fontSize: "15px", color: "var(--text-secondary, #52606D)", marginBottom: "20px" }}>
                  What would you like to upload?
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <button
                    type="button"
                    onClick={() => cameraInputRef.current?.click()}
                    className="btn btn-secondary"
                    style={{
                      justifyContent: "flex-start",
                      padding: "16px 20px",
                      minHeight: "56px",
                      fontSize: "15px",
                    }}
                  >
                    <CameraIcon size={20} color="var(--navy-primary)" />
                    <span>Take a photo</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="btn btn-secondary"
                    style={{
                      justifyContent: "flex-start",
                      padding: "16px 20px",
                      minHeight: "56px",
                      fontSize: "15px",
                    }}
                  >
                    <DocumentIcon size={20} color="var(--navy-primary)" />
                    <span>Choose from phone / computer</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="btn btn-secondary"
                    style={{
                      justifyContent: "flex-start",
                      padding: "16px 20px",
                      minHeight: "56px",
                      fontSize: "15px",
                    }}
                  >
                    <PlusIcon size={20} color="var(--navy-primary)" />
                    <span>Choose a file (PDF, Image, Word)</span>
                  </button>
                </div>
              </div>
            ) : (
              /* Step 2: "What is this document?" */
              <form onSubmit={handleUploadSubmit}>
                <div style={{ marginBottom: "16px", padding: "12px 14px", background: "var(--surface-base, #F7F9FC)", borderRadius: "8px", border: "1px solid var(--border-subtle, #D9E2EC)" }}>
                  <span style={{ fontSize: "12px", color: "var(--text-muted, #7B8794)", display: "block" }}>Selected File</span>
                  <span style={{ fontSize: "14px", fontWeight: 700, color: "var(--navy-primary, #17324D)" }}>{selectedFile?.name}</span>
                </div>

                {cases.length > 1 && (
                  <div className="input-group" style={{ marginBottom: "16px" }}>
                    <label className="input-label">Case</label>
                    <select
                      className="input-field"
                      value={selectedCaseId}
                      onChange={(e) => setSelectedCaseId(e.target.value)}
                      required
                    >
                      {cases.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.title}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="input-group" style={{ marginBottom: "16px" }}>
                  <label className="input-label">Document name</label>
                  <input
                    className="input-field"
                    placeholder="e.g. Property Agreement, Court Notice"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    required
                  />
                </div>

                <div className="input-group" style={{ marginBottom: "24px" }}>
                  <label className="input-label">What is this document?</label>
                  <select
                    className="input-field"
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                  >
                    <option value="COURT">Court notice or order</option>
                    <option value="IDENTITY">Identity document (Aadhaar, PAN, Voter ID)</option>
                    <option value="AGREEMENT">Agreement or contract</option>
                    <option value="EVIDENCE">Evidence or receipt</option>
                    <option value="OTHER">Other</option>
                    <option value="UNKNOWN">I don&apos;t know</option>
                  </select>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", gap: "10px" }}>
                  <button
                    type="button"
                    onClick={() => setUploadStep(1)}
                    className="btn btn-secondary"
                    disabled={uploading}
                  >
                    ← Back
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={uploading}
                  >
                    {uploading ? "Uploading..." : "Save document"}
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
