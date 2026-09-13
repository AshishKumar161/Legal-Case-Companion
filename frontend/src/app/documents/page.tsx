"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { apiClient } from "@/api/client";
import { CaseItem, DocumentItem, MatterRequestItem, SharedEvidenceItem } from "@/types";
import {
  DocumentIcon,
  SearchIcon,
  ShieldIcon,
  CheckCircleIcon,
  PlusIcon,
  AssistantIcon,
} from "@/components/ui/Icons";
import styles from "./page.module.css";

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
}

const CATEGORY_OPTIONS: ClientCategoryOption[] = [
  { id: "ALL", label: "All Documents" },
  { id: "AGREEMENT", label: "Agreements & Deeds" },
  { id: "COURT", label: "Court Orders" },
  { id: "NOTICE", label: "Legal Notices" },
  { id: "ID", label: "Identity Proof" },
  { id: "EVIDENCE", label: "Evidence & Receipts" },
  { id: "OTHER", label: "Other" },
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
    case "ID": return "Identity Proof";
    case "COURT": return "Court Order";
    case "NOTICE": return "Legal Notice";
    case "AGREEMENT": return "Agreement";
    case "EVIDENCE": return "Evidence";
    case "OTHER": return "Document";
    default: return "Document";
  }
}

function formatRelativeTime(dateStr?: string | null): string {
  if (!dateStr) return "Recently added";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "Recently added";
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "Added today";
    if (diffDays === 1) return "Added yesterday";
    if (diffDays < 7) return `Added ${diffDays} days ago`;
    return `Added on ${d.toLocaleDateString("en-IN", { day: "numeric", month: "short" })}`;
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
  const [sharedDocuments, setSharedDocuments] = useState<SharedEvidenceItem[]>([]);
  const [pendingRequests, setPendingRequests] = useState<MatterRequestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedCategory, setSelectedCategory] = useState<ClientDocCategory>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [securityDetailsOpen, setSecurityDetailsOpen] = useState(false);

  // Upload Modal State
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedCaseId, setSelectedCaseId] = useState<string>("");
  const [newTitle, setNewTitle] = useState("");
  const [newCategory, setNewCategory] = useState<ClientDocCategory>("EVIDENCE");
  const [newDescription, setNewDescription] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // "Explain This Document" Modal State (Section 9)
  const [explainingDoc, setExplainingDoc] = useState<EnrichedDoc | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchAllDocuments = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [casesRes, sharedRes] = await Promise.all([
        apiClient.get("/api/v1/cases").catch(() => ({ items: [] })),
        apiClient.get<SharedEvidenceItem[]>("/api/v1/documents/shared-with-me").catch(() => []),
      ]);

      const casesList: CaseItem[] = Array.isArray(casesRes)
        ? casesRes
        : (casesRes as { items?: CaseItem[] })?.items || [];
      setCases(casesList);
      setSharedDocuments(Array.isArray(sharedRes) ? sharedRes : []);

      if (casesList.length > 0 && !selectedCaseId) {
        setSelectedCaseId(casesList[0].id);
      }

      // Fetch documents and requests for all cases
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
                caseCourt: "Court Record",
                resolvedCategory: normalizeCategory(doc.category || doc.filename),
              });
            }

            if (Array.isArray(reqsRes)) {
              allReqs.push(...reqsRes.filter((r) => r.status === "PENDING" && r.request_type === "DOCUMENT_UPLOAD"));
            }
          } catch {
            // Ignore per-case failures
          }
        })
      );

      // Sort by creation date descending
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

  // Filter documents
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

  // Handle Download / Open
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

  // Handle Upload
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !selectedCaseId) return;

    try {
      setUploading(true);
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("title", newTitle || selectedFile.name);
      formData.append("category", newCategory);
      if (newDescription) formData.append("description", newDescription);

      await apiClient.post(`/api/v1/cases/${selectedCaseId}/documents`, formData);
      setUploadModalOpen(false);
      setSelectedFile(null);
      setNewTitle("");
      setNewDescription("");
      void fetchAllDocuments();
    } catch {
      alert("Upload failed. Please ensure the file is under 50MB.");
    } finally {
      setUploading(false);
    }
  };

  // Generate plain-language explanation data for document (Section 9)
  const getDocumentExplanation = (doc: EnrichedDoc) => {
    const cat = doc.resolvedCategory;
    const name = doc.filename.toLowerCase();

    if (cat === "COURT" || name.includes("order") || name.includes("judgment")) {
      return {
        whatItIs: "An official decision or direction issued by the court judge in your case.",
        whatItMeans: "It records what took place during the hearing and sets legal obligations or the next date of listing for both sides.",
        whatIsImportant: "Check the exact compliance dates mentioned in the order and confirm if any affidavits or fee deposits were directed.",
        whatYouNeedToDo: "Review this order with your advocate to ensure any response or filing is prepared before the next date.",
        questionsForLawyer: [
          "Do we need to file a compliance affidavit before the next date?",
          "Does this order grant an interim stay or protection?",
          "When is the next court listing scheduled?",
        ],
      };
    }

    if (cat === "AGREEMENT" || name.includes("sale") || name.includes("lease") || name.includes("deed") || name.includes("contract")) {
      return {
        whatItIs: "A binding legal agreement or deed setting out mutual terms, payments, and obligations.",
        whatItMeans: "This serves as foundational documentary proof of rights, possession, or financial transactions.",
        whatIsImportant: "The execution date, signatures, stamp duty payment, and registration number are critical for legal validity.",
        whatYouNeedToDo: "Keep the original paper document safe. Provide a high-resolution scan to your lawyer to enter into the court record.",
        questionsForLawyer: [
          "Is this document properly stamped under the relevant Stamp Act?",
          "Are there any disputed clauses or clauses that require clarification in court?",
          "Do we need to present the original copy for admission and denial?",
        ],
      };
    }

    if (cat === "NOTICE" || name.includes("notice") || name.includes("demand")) {
      return {
        whatItIs: "A formal statutory or demand notice communicating a legal claim before or during court proceedings.",
        whatItMeans: "The sender is asserting a right or demanding compliance, typically specifying a time limit (e.g. 15 or 30 days) to reply.",
        whatIsImportant: "The date on which you received the notice is critical because response deadlines start from the receipt date.",
        whatYouNeedToDo: "Share this immediately with your lawyer so a timely written reply can be drafted before the limitation expires.",
        questionsForLawyer: [
          "What is the exact deadline to dispatch our formal reply?",
          "Should we reply on merits or deny the allegations generally?",
          "What supporting receipts or proofs should we attach to our reply?",
        ],
      };
    }

    return {
      whatItIs: "A supporting case document or evidentiary proof added to your case record.",
      whatItMeans: "This document establishes factual facts or background records supporting your position.",
      whatIsImportant: "Ensure that all pages, stamps, and dates are legible without missing annexures.",
      whatYouNeedToDo: "Confirm with your lawyer if this document has been indexed and filed in the court registry.",
      questionsForLawyer: [
        "Has this document been marked as an exhibit in the court record?",
        "Do you need any additional proof to corroborate this document?",
      ],
    };
  };

  return (
    <div className={styles.container}>
      {/* Header (Section 9) */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>My Documents</h1>
          <p className={styles.subtitle}>
            Documents related to your case ({documents.length} files{sharedDocuments.length > 0 ? `, ${sharedDocuments.length} shared evidence items` : ""})
          </p>
        </div>

        <div className={styles.headerActions}>
          <button
            onClick={() => setUploadModalOpen(true)}
            className={styles.primaryBtn}
            disabled={cases.length === 0}
          >
            <PlusIcon size={16} color="#FFFFFF" />
            <span>Add Document</span>
          </button>
        </div>
      </div>

      {/* Pending Document Requests Banner */}
      {pendingRequests.length > 0 && (
        <div
          style={{
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.25)",
            borderRadius: "10px",
            padding: "14px 18px",
            marginBottom: "20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <div>
            <div style={{ color: "#ef4444", fontWeight: 700, fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              ⚡ Action Required · {pendingRequests.length} Pending Document {pendingRequests.length === 1 ? "Request" : "Requests"}
            </div>
            <div style={{ color: "#fff", fontSize: "14px", fontWeight: 600, marginTop: "2px" }}>
              {pendingRequests[0].title}
            </div>
            <div style={{ color: "#94a3b8", fontSize: "12px", marginTop: "2px" }}>
              {pendingRequests[0].description || "Your retained advocate requested this document for case filings."}
            </div>
          </div>
          <button
            onClick={() => setUploadModalOpen(true)}
            className={styles.primaryBtn}
            style={{ fontSize: "12px", padding: "8px 16px" }}
          >
            Upload Requested File →
          </button>
        </div>
      )}

      {/* Security Assurance Banner (Section 13) */}
      <div className={styles.securityBanner}>
        <div className={styles.securityText}>
          <ShieldIcon size={16} color="var(--navy-primary)" />
          <span>Your documents are encrypted and protected. Only you and authorized counsel can access them.</span>
        </div>
        <button
          type="button"
          onClick={() => setSecurityDetailsOpen((prev) => !prev)}
          className={styles.securityToggle}
        >
          {securityDetailsOpen ? "Hide details ▲" : "View security details ▼"}
        </button>
      </div>

      {securityDetailsOpen && (
        <div
          style={{
            background: "var(--surface-subtle)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "16px",
            marginBottom: "24px",
            fontSize: "13px",
            color: "var(--text-secondary)",
            lineHeight: "1.6",
          }}
        >
          <div style={{ fontWeight: 600, color: "var(--navy-primary)", marginBottom: "4px" }}>
            Document Protection Overview:
          </div>
          <div>• Storage is scanned automatically for malicious files.</div>
          <div>• Access is strictly limited to authenticated participants of your active case.</div>
          <div>• Documents can be downloaded anytime in authentic, original quality.</div>
        </div>
      )}

      {/* Categories Filter Bar */}
      <div className={styles.categoryBar} role="tablist">
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

      {/* Search Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.searchBox}>
          <SearchIcon size={14} />
          <input
            className={styles.searchInput}
            placeholder="Search documents by name or case..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search documents"
          />
        </div>

        <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>
          Showing <strong>{filteredDocs.length}</strong> {filteredDocs.length === 1 ? "document" : "documents"}
        </div>
      </div>

      {/* Document Grid (Section 9) */}
      {loading ? (
        <div style={{ padding: "60px 0", textAlign: "center", color: "var(--text-secondary)" }}>
          Loading your documents...
        </div>
      ) : error ? (
        <div style={{ padding: "24px", background: "rgba(220, 38, 38, 0.08)", color: "var(--status-urgent)", borderRadius: "8px" }}>
          {error}
        </div>
      ) : documents.length === 0 ? (
        /* Empty State */
        <div className={styles.emptyContainer}>
          <div className={styles.emptyIcon}>
            <DocumentIcon size={28} />
          </div>
          <h3 className={styles.emptyTitle}>You don&apos;t have any documents yet</h3>
          <p className={styles.emptyDesc}>
            Add contracts, court orders, notices, or identity proof to keep them organized and understand them in plain language.
          </p>
          <button
            onClick={() => setUploadModalOpen(true)}
            className="btn btn-primary"
            disabled={cases.length === 0}
          >
            <PlusIcon size={16} />
            <span>Add Your First Document</span>
          </button>
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className={styles.emptyContainer}>
          <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
            No documents match &ldquo;{searchQuery}&rdquo;. Try selecting &quot;All Documents&quot;.
          </p>
        </div>
      ) : (
        <div className={styles.docGrid}>
          {filteredDocs.map((doc) => (
            <div key={doc.id} className={styles.docCard}>
              <div>
                <div className={styles.docTopRow}>
                  <span className={styles.docCategoryPill}>
                    {getCategoryLabel(doc.resolvedCategory)}
                  </span>
                  <span className={styles.docAddedTime}>
                    {formatRelativeTime(doc.created_at)}
                  </span>
                </div>

                <h3 className={styles.docTitle}>{doc.filename}</h3>

                <div className={styles.docMeta}>
                  <div>Case: <strong>{doc.caseTitle}</strong></div>
                </div>
              </div>

              {/* Action Buttons (Section 9: [ Open ] and [ Understand This ]) */}
              <div className={styles.docFooter}>
                <button
                  onClick={() => handleDownload(doc)}
                  className={styles.openBtn}
                  title="Open and download file"
                >
                  <span>Open</span>
                </button>

                <button
                  onClick={() => setExplainingDoc(doc)}
                  className={styles.understandBtn}
                  title="Explain this document in plain language"
                >
                  <AssistantIcon size={14} color="#FFFFFF" />
                  <span>Understand This</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* "Explain This Document" Modal (Section 9) */}
      {explainingDoc && (() => {
        const exp = getDocumentExplanation(explainingDoc);
        return (
          <div className={styles.modalBackdrop} onClick={() => setExplainingDoc(null)}>
            <div className={styles.modalBox} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <div>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--accent-gold)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "4px" }}>
                    ⚖ Plain-Language Document Explanation
                  </div>
                  <h3 className={styles.modalTitle}>{explainingDoc.filename}</h3>
                  <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                    Case: {explainingDoc.caseTitle} · {getCategoryLabel(explainingDoc.resolvedCategory)}
                  </div>
                </div>
                <button
                  onClick={() => setExplainingDoc(null)}
                  className={styles.closeBtn}
                  aria-label="Close"
                >
                  ✕
                </button>
              </div>

              {/* 1. What this document is */}
              <div className={styles.explainSection}>
                <div className={styles.explainSectionHeading}>
                  <CheckCircleIcon size={16} color="var(--navy-primary)" />
                  <span>1. What this document is</span>
                </div>
                <p className={styles.explainSectionBody}>{exp.whatItIs}</p>
              </div>

              {/* 2. What it means */}
              <div className={styles.explainSection}>
                <div className={styles.explainSectionHeading}>
                  <CheckCircleIcon size={16} color="var(--navy-primary)" />
                  <span>2. What it means</span>
                </div>
                <p className={styles.explainSectionBody}>{exp.whatItMeans}</p>
              </div>

              {/* 3. What is important */}
              <div className={styles.explainSection}>
                <div className={styles.explainSectionHeading}>
                  <CheckCircleIcon size={16} color="var(--navy-primary)" />
                  <span>3. What is important</span>
                </div>
                <p className={styles.explainSectionBody}>{exp.whatIsImportant}</p>
              </div>

              {/* 4. What you need to do */}
              <div className={styles.explainSection}>
                <div className={styles.explainSectionHeading}>
                  <CheckCircleIcon size={16} color="var(--navy-primary)" />
                  <span>4. What you need to do</span>
                </div>
                <p className={styles.explainSectionBody}>{exp.whatYouNeedToDo}</p>
              </div>

              {/* 5. Questions to ask your lawyer */}
              <div className={styles.explainSection}>
                <div className={styles.explainSectionHeading}>
                  <AssistantIcon size={16} color="var(--accent-gold)" />
                  <span>5. Questions to ask your lawyer</span>
                </div>
                <ul style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "6px", fontSize: "14px", color: "var(--text-secondary)" }}>
                  {exp.questionsForLawyer.map((q, idx) => (
                    <li key={idx}>&ldquo;{q}&rdquo;</li>
                  ))}
                </ul>
              </div>

              {/* Legal Disclaimer */}
              <div className={styles.explainDisclaimer}>
                <strong>Important Note:</strong> This explanation is created by LCC to help you understand your legal documents in simple language. It does not constitute formal legal advice. Always review strategic decisions with your lawyer.
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "20px" }}>
                <button
                  onClick={() => setExplainingDoc(null)}
                  className="btn btn-primary"
                >
                  Got It
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Upload Document Modal */}
      {uploadModalOpen && (
        <div className={styles.modalBackdrop} onClick={() => setUploadModalOpen(false)}>
          <div className={styles.modalBox} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3 className={styles.modalTitle}>Add Document</h3>
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
              <div className="input-group">
                <label className="input-label">Select Case</label>
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

              {/* File Select */}
              <div className="input-group">
                <label className="input-label">Choose File (PDF, Images, Word)</label>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="input-field"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      const f = e.target.files[0];
                      setSelectedFile(f);
                      if (!newTitle) setNewTitle(f.name);
                    }
                  }}
                  required
                />
              </div>

              {/* Document Name */}
              <div className="input-group">
                <label className="input-label">Document Name</label>
                <input
                  className="input-field"
                  placeholder="e.g. Sale Agreement, Court Order"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  required
                />
              </div>

              {/* Category */}
              <div className="input-group">
                <label className="input-label">Document Type</label>
                <select
                  className="input-field"
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value as ClientDocCategory)}
                >
                  <option value="AGREEMENT">Agreement or Contract</option>
                  <option value="COURT">Court Order or Petition</option>
                  <option value="NOTICE">Legal Notice</option>
                  <option value="ID">Identity Proof (Aadhaar, PAN, Voter ID)</option>
                  <option value="EVIDENCE">Evidence, Receipts, Photos</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "20px" }}>
                <button
                  type="button"
                  onClick={() => setUploadModalOpen(false)}
                  className="btn btn-secondary"
                  disabled={uploading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={uploading}
                >
                  {uploading ? "Saving..." : "Save Document"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
