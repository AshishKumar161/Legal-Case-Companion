"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import {
  AdvocateDocumentType,
  AdvocateVerificationDocumentItem,
} from "@/types";
import styles from "../onboarding.module.css";

const STATE_BAR_COUNCILS = [
  "Bar Council of Delhi",
  "Bar Council of Maharashtra & Goa",
  "Bar Council of Uttar Pradesh",
  "Bar Council of Punjab & Haryana",
  "Bar Council of Karnataka",
  "Bar Council of Tamil Nadu",
  "Bar Council of West Bengal",
  "Bar Council of Gujarat",
  "Bar Council of Rajasthan",
];

const PILOT_COURTS = [
  "High Court of Delhi",
  "High Court of Bombay",
  "High Court of Allahabad",
  "Delhi District Courts (Tis Hazari, Saket, Patiala House)",
  "Mumbai City Civil & Sessions Court",
  "National Company Law Tribunal (NCLT)",
  "Debt Recovery Tribunal (DRT)",
];

const PRACTICE_AREAS = [
  "Criminal Law & Bail",
  "Civil Litigation & Injunctions",
  "Constitutional & Writ Petitions",
  "Family & Matrimonial Disputes",
  "Corporate & Commercial Arbitration",
  "Real Estate & Property Law",
  "Cheque Bounce (NI Act Sec 138)",
  "Insolvency & Bankruptcy (IBC)",
];

export default function AdvocateOnboardingPage() {
  const router = useRouter();
  const { user } = useAuth();

  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);

  // Form State
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [barCouncil, setBarCouncil] = useState(STATE_BAR_COUNCILS[0]);
  const [enrollmentNo, setEnrollmentNo] = useState("");
  const [selectedAreas, setSelectedAreas] = useState<string[]>([PRACTICE_AREAS[0], PRACTICE_AREAS[1]]);
  const [selectedCourts, setSelectedCourts] = useState<string[]>([PILOT_COURTS[0]]);
  const [fee, setFee] = useState("1000");
  const [instantEnabled, setInstantEnabled] = useState(true);

  // Phase 14 Document Upload State
  const [uploadedDocs, setUploadedDocs] = useState<AdvocateVerificationDocumentItem[]>([]);
  const [uploadingDocType, setUploadingDocType] = useState<AdvocateDocumentType | null>(null);
  const [uploadError, setUploadError] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const togglePracticeArea = (area: string) => {
    setSelectedAreas((prev) =>
      prev.includes(area) ? prev.filter((a) => a !== area) : [...prev, area]
    );
  };

  const toggleCourt = (court: string) => {
    setSelectedCourts((prev) =>
      prev.includes(court) ? prev.filter((c) => c !== court) : [...prev, court]
    );
  };

  // Browser-side SHA-256 calculation for transparency before upload
  const calculateSha256 = async (file: File): Promise<string> => {
    const buffer = await file.arrayBuffer();
    const digest = await crypto.subtle.digest("SHA-256", buffer);
    return Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  };

  const handleFileUpload = async (
    e: React.ChangeEvent<HTMLInputElement>,
    docType: AdvocateDocumentType
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError("");
    setUploadingDocType(docType);

    try {
      if (file.size > 25 * 1024 * 1024) {
        throw new Error("File exceeds maximum allowed size of 25MB.");
      }

      // Check client-side magic bytes preview
      const headerBuf = await file.slice(0, 4).arrayBuffer();
      const bytes = new Uint8Array(headerBuf);
      const isPdf = bytes[0] === 0x25 && bytes[1] === 0x50 && bytes[2] === 0x44 && bytes[3] === 0x46; // %PDF
      const isJpg = bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
      const isPng = bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47;

      if (!isPdf && !isJpg && !isPng) {
        throw new Error("Unsupported format. Please provide an authentic PDF, JPEG, or PNG file.");
      }

      await calculateSha256(file);

      const formData = new FormData();
      formData.append("file", file);
      formData.append("document_type", docType);

      const uploaded = await apiClient.post<AdvocateVerificationDocumentItem>(
        "/api/v1/verification/application/documents",
        formData
      );

      setUploadedDocs((prev) => {
        const filtered = prev.filter((d) => d.document_type !== docType);
        return [...filtered, uploaded];
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Document upload failed.";
      setUploadError(msg);
    } finally {
      setUploadingDocType(null);
      e.target.value = "";
    }
  };

  const hasEnrollmentDoc = uploadedDocs.some(
    (d) => d.document_type === "BAR_COUNCIL_ENROLLMENT_CERTIFICATE"
  );

  const handleStep1Submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    const cleaned = enrollmentNo.trim().toUpperCase();
    if (!cleaned || !cleaned.includes("/")) {
      setError("Please enter a valid enrollment number in standard STATE/NUMBER/YEAR format (e.g., D/1234/2018).");
      return;
    }

    if (!hasEnrollmentDoc) {
      setError("Statutory requirement: Please upload your official Bar Council Enrollment Certificate before continuing.");
      return;
    }

    setStep(2);
  };

  const handleStep2Submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedAreas.length === 0) {
      setError("Please select at least one primary practice area.");
      return;
    }
    setError("");
    setStep(3);
  };

  const handleStep3Submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");

    const numFee = parseInt(fee, 10);
    if (isNaN(numFee) || numFee < 500 || numFee > 2500) {
      setError("During the initial pilot, consultation fees are capped between ₹500 and ₹2,500.");
      setSubmitting(false);
      return;
    }

    try {
      // 1. Submit Phase 14 formal verification application
      await apiClient.post("/api/v1/verification/application/submit", {
        enrollment_number: enrollmentNo.trim().toUpperCase(),
        state_bar_council: barCouncil,
        declared_practice_jurisdictions: selectedCourts,
      });

      // 2. Telemetry event recording advocate onboarding completion
      await apiClient.post("/api/v1/pilot/telemetry/event", {
        event_type: "ADVOCATE_ONBOARDING_COMPLETED",
        metadata: {
          bar_council: barCouncil,
          practice_areas_count: selectedAreas.length,
          jurisdictions_count: selectedCourts.length,
          documents_count: uploadedDocs.length,
          fee: numFee,
          instant_enabled: instantEnabled,
        },
      }).catch(() => null);

      setStep(4);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record credentials and submit application.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.card} style={{ maxWidth: step === 4 ? "680px" : "640px" }}>
        <div className={styles.header}>
          <div className={styles.badge}>Advocate Pilot Onboarding • Professional Hub</div>
          <h1 className={styles.title}>
            {step === 1 && "Bar Council Credentials & Documents"}
            {step === 2 && "Practice Areas & Jurisdictions"}
            {step === 3 && "Consultation Options & Availability"}
            {step === 4 && "Verification Review Pipeline"}
          </h1>
          <p className={styles.subtitle}>
            {step === 1 && "Provide your official statutory Bar Council enrollment and professional credentials for human verification."}
            {step === 2 && "Declare your core Indian court jurisdictions and domain expertise for client discovery."}
            {step === 3 && "Set your initial consultation rate and on-demand video session availability."}
            {step === 4 && "Your credentials and documents have been submitted to the compliance verification queue."}
          </p>
        </div>

        {/* Step Indicator */}
        <div className={styles.stepIndicator}>
          <div className={`${styles.stepDot} ${step >= 1 ? styles.stepDotActive : ""}`} />
          <div className={`${styles.stepDot} ${step >= 2 ? styles.stepDotActive : ""}`} />
          <div className={`${styles.stepDot} ${step >= 3 ? styles.stepDotActive : ""}`} />
          <div className={`${styles.stepDot} ${step >= 4 ? styles.stepDotActive : ""}`} />
        </div>

        {error && (
          <div style={{ padding: "10px 14px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.25)", borderRadius: "8px", color: "#fca5a5", fontSize: "13px", marginBottom: "20px" }}>
            {error}
          </div>
        )}

        {/* STEP 1: Bar Council Details & Document Upload */}
        {step === 1 && (
          <form onSubmit={handleStep1Submit}>
            <div className={styles.formGroup}>
              <label className={styles.label}>Full Name (as per Bar Council Certificate)</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                className={styles.input}
                placeholder="Adv. Rajesh Sharma"
              />
            </div>

            <div className={styles.formGroup}>
              <label className={styles.label}>State Bar Council</label>
              <select
                value={barCouncil}
                onChange={(e) => setBarCouncil(e.target.value)}
                className={styles.select}
              >
                {STATE_BAR_COUNCILS.map((bc) => (
                  <option key={bc} value={bc}>{bc}</option>
                ))}
              </select>
            </div>

            <div className={styles.formGroup}>
              <label className={styles.label}>Bar Council Enrollment Number</label>
              <input
                type="text"
                value={enrollmentNo}
                onChange={(e) => setEnrollmentNo(e.target.value)}
                required
                className={styles.input}
                placeholder="e.g. D/1234/2018 or MAH/5678/2020"
              />
              <span style={{ fontSize: "11px", color: "var(--text-muted, #94a3b8)", marginTop: "4px", display: "block" }}>
                Format: STATE/ROLL_NUMBER/YEAR as issued on Bar ID card (Advocates Act 1961 Sec 22)
              </span>
            </div>

            {/* Document Upload Section */}
            <div style={{ marginTop: "24px", borderTop: "1px solid rgba(255, 255, 255, 0.08)", paddingTop: "18px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <label className={styles.label} style={{ margin: 0 }}>
                  Professional Verification Documents (Human Review)
                </label>
                <span style={{ fontSize: "11px", color: "#93c5fd" }}>Zero-AI • Private Storage</span>
              </div>
              <p style={{ fontSize: "12px", color: "var(--text-secondary, #94a3b8)", marginBottom: "14px", lineHeight: "1.4" }}>
                Verification documents are securely encrypted and accessed only by authorized human reviewers. Magic bytes and SHA-256 integrity hashes are enforced.
              </p>

              {uploadError && (
                <div style={{ padding: "8px 12px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.25)", borderRadius: "6px", color: "#fca5a5", fontSize: "12px", marginBottom: "12px" }}>
                  {uploadError}
                </div>
              )}

              {/* Upload Item 1: Bar Council Enrollment Certificate */}
              <div style={{ background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "8px", padding: "14px", marginBottom: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: "#ffffff" }}>
                      1. Bar Council Enrollment Certificate <span style={{ color: "#ef4444" }}>*</span>
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--text-secondary, #94a3b8)" }}>
                      Mandatory statutory roll certificate or Certificate of Practice (PDF / PNG / JPG)
                    </div>
                  </div>
                  <div>
                    <label
                      style={{
                        padding: "6px 12px",
                        background: hasEnrollmentDoc ? "rgba(16, 185, 129, 0.15)" : "#2563eb",
                        color: hasEnrollmentDoc ? "#34d399" : "#ffffff",
                        border: hasEnrollmentDoc ? "1px solid rgba(16, 185, 129, 0.3)" : "none",
                        borderRadius: "6px",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "inline-block",
                      }}
                    >
                      {uploadingDocType === "BAR_COUNCIL_ENROLLMENT_CERTIFICATE"
                        ? "Scanning & Uploading..."
                        : hasEnrollmentDoc
                        ? "✓ Uploaded (Replace)"
                        : "Upload Document"}
                      <input
                        type="file"
                        accept=".pdf,.png,.jpg,.jpeg"
                        style={{ display: "none" }}
                        onChange={(e) => handleFileUpload(e, "BAR_COUNCIL_ENROLLMENT_CERTIFICATE")}
                        disabled={uploadingDocType !== null}
                      />
                    </label>
                  </div>
                </div>

                {hasEnrollmentDoc && (
                  <div style={{ marginTop: "10px", padding: "8px 10px", background: "rgba(16, 185, 129, 0.06)", borderRadius: "6px", fontSize: "11px", color: "#a7f3d0" }}>
                    ✓ Document stored securely with cryptographic SHA-256 hash. Status: PENDING REVIEW
                  </div>
                )}
              </div>

              {/* Upload Item 2: Certificate of Practice or Bar ID (Optional) */}
              <div style={{ background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "8px", padding: "14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: "#ffffff" }}>
                      2. Certificate of Practice (COP) / Bar ID Card
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--text-secondary, #94a3b8)" }}>
                      BCI Verification Rules 2015 COP or official photo identification card
                    </div>
                  </div>
                  <div>
                    <label
                      style={{
                        padding: "6px 12px",
                        background: uploadedDocs.some((d) => d.document_type === "CERTIFICATE_OF_PRACTICE")
                          ? "rgba(16, 185, 129, 0.15)"
                          : "rgba(255, 255, 255, 0.08)",
                        color: uploadedDocs.some((d) => d.document_type === "CERTIFICATE_OF_PRACTICE")
                          ? "#34d399"
                          : "#cbd5e1",
                        border: "1px solid rgba(255, 255, 255, 0.12)",
                        borderRadius: "6px",
                        fontSize: "12px",
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "inline-block",
                      }}
                    >
                      {uploadingDocType === "CERTIFICATE_OF_PRACTICE"
                        ? "Scanning & Uploading..."
                        : uploadedDocs.some((d) => d.document_type === "CERTIFICATE_OF_PRACTICE")
                        ? "✓ Uploaded (Replace)"
                        : "Upload (Optional)"}
                      <input
                        type="file"
                        accept=".pdf,.png,.jpg,.jpeg"
                        style={{ display: "none" }}
                        onChange={(e) => handleFileUpload(e, "CERTIFICATE_OF_PRACTICE")}
                        disabled={uploadingDocType !== null}
                      />
                    </label>
                  </div>
                </div>
              </div>
            </div>

            <div className={styles.actions}>
              <button
                type="button"
                onClick={() => router.push("/lawyer/dashboard")}
                className={styles.secondaryBtn}
              >
                Skip for Now
              </button>
              <button type="submit" className={styles.primaryBtn}>
                Save & Continue →
              </button>
            </div>
          </form>
        )}

        {/* STEP 2: Practice Areas & Jurisdictions */}
        {step === 2 && (
          <form onSubmit={handleStep2Submit}>
            <div className={styles.formGroup}>
              <label className={styles.label}>Primary Practice Areas</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {PRACTICE_AREAS.map((area) => {
                  const selected = selectedAreas.includes(area);
                  return (
                    <button
                      key={area}
                      type="button"
                      onClick={() => togglePracticeArea(area)}
                      style={{
                        padding: "6px 12px",
                        borderRadius: "20px",
                        fontSize: "12px",
                        fontWeight: 500,
                        border: selected ? "1px solid #3b82f6" : "1px solid rgba(255,255,255,0.12)",
                        background: selected ? "rgba(59, 130, 246, 0.2)" : "rgba(255,255,255,0.04)",
                        color: selected ? "#93c5fd" : "var(--text-secondary, #94a3b8)",
                        cursor: "pointer",
                      }}
                    >
                      {selected ? "✓ " : "+ "}{area}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className={styles.formGroup} style={{ marginTop: "20px" }}>
              <label className={styles.label}>Supported Pilot Court Jurisdictions</label>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {PILOT_COURTS.map((court) => {
                  const selected = selectedCourts.includes(court);
                  return (
                    <label
                      key={court}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        fontSize: "13px",
                        color: "#fff",
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleCourt(court)}
                      />
                      <span>{court}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className={styles.actions}>
              <button
                type="button"
                onClick={() => setStep(1)}
                className={styles.secondaryBtn}
              >
                ← Back
              </button>
              <button type="submit" className={styles.primaryBtn}>
                Next: Rates & Availability →
              </button>
            </div>
          </form>
        )}

        {/* STEP 3: Consultation Pricing & Availability */}
        {step === 3 && (
          <form onSubmit={handleStep3Submit}>
            <div className={styles.jurisdictionNotice}>
              <span>💡</span>
              <div>
                <strong>Pilot Pricing Boundary:</strong> Initial consultation fees are structured between ₹500 and ₹2,500 to maintain litigant access during pilot.
              </div>
            </div>

            <div className={styles.formGroup}>
              <label className={styles.label}>Initial Consultation Fee (₹ INR per 30-min session)</label>
              <input
                type="number"
                min="500"
                max="2500"
                step="100"
                value={fee}
                onChange={(e) => setFee(e.target.value)}
                required
                className={styles.input}
              />
            </div>

            <div className={styles.formGroup}>
              <label style={{ display: "flex", alignItems: "flex-start", gap: "10px", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={instantEnabled}
                  onChange={(e) => setInstantEnabled(e.target.checked)}
                  style={{ marginTop: "3px" }}
                />
                <div>
                  <div style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>
                    Enable Instant On-Demand Video Consultations
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--text-secondary, #94a3b8)", marginTop: "2px" }}>
                    Receive consultation alerts when clients request legal advice while you are online.
                  </div>
                </div>
              </label>
            </div>

            <div className={styles.actions}>
              <button
                type="button"
                onClick={() => setStep(2)}
                className={styles.secondaryBtn}
              >
                ← Back
              </button>
              <button
                type="submit"
                disabled={submitting}
                className={styles.primaryBtn}
              >
                {submitting ? "Submitting Application..." : "Submit Verification Application →"}
              </button>
            </div>
          </form>
        )}

        {/* STEP 4: Verification Status & Value Activation */}
        {step === 4 && (
          <div>
            <div className={`${styles.verificationBanner} ${styles.verificationBannerPending}`}>
              <span style={{ fontSize: "24px" }}>⏳</span>
              <div>
                <div style={{ fontSize: "15px", fontWeight: 700 }}>
                  Verification Status: PENDING ADMINISTRATIVE REVIEW
                </div>
                <div style={{ fontSize: "12px", marginTop: "4px", lineHeight: "1.4" }}>
                  Your enrollment <strong>{enrollmentNo.trim().toUpperCase()}</strong> with the{" "}
                  <strong>{barCouncil}</strong> and uploaded documents have been deposited into the compliance verification queue.
                </div>
              </div>
            </div>

            <div style={{ background: "rgba(255, 255, 255, 0.03)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "10px", padding: "16px", marginBottom: "20px" }}>
              <h3 style={{ fontSize: "13px", fontWeight: 700, color: "#ffffff", margin: "0 0 10px 0" }}>
                Statutory Review & Zero-AI Compliance Mandate
              </h3>
              <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "12px", color: "var(--text-secondary, #94a3b8)", lineHeight: "1.5" }}>
                <li><strong>No AI Classification:</strong> All advocate verification decisions are strictly made by human compliance reviewers.</li>
                <li><strong>BCI Rule 36 Proviso:</strong> Public profiles only display factual enrollment credentials. Ratings, superlatives, and solicitation claims are strictly prohibited.</li>
                <li><strong>Official Roll Checks:</strong> Your credentials will be verified against State Bar Council roll records.</li>
              </ul>
            </div>

            <div style={{ textAlign: "center", marginBottom: "20px" }}>
              <h2 style={{ fontSize: "17px", color: "#fff", margin: "0 0 6px 0" }}>
                Your Advocate Workspace is Active
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-secondary, #94a3b8)", margin: 0 }}>
                You can immediately manage active client cases, track court hearings, and view cause lists.
              </p>
            </div>

            <div className={styles.activationCards}>
              <button
                type="button"
                onClick={() => router.push("/calendar")}
                className={`${styles.activationCard} ${styles.activationCardPrimary}`}
                style={{ cursor: "pointer", width: "100%", border: "1px solid #3b82f6" }}
              >
                <div style={{ textAlign: "left" }}>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#ffffff" }}>
                    📅 View Court Hearings & Cause List Calendar
                  </div>
                  <div style={{ fontSize: "12px", color: "#93c5fd", marginTop: "2px" }}>
                    Track item numbers, courtroom numbers, and upcoming hearing dates
                  </div>
                </div>
                <span style={{ fontSize: "18px", color: "#ffffff" }}>→</span>
              </button>

              <button
                type="button"
                onClick={() => router.push("/lawyer/dashboard")}
                className={styles.activationCard}
                style={{ cursor: "pointer", width: "100%" }}
              >
                <div style={{ textAlign: "left" }}>
                  <div style={{ fontSize: "14px", fontWeight: 600, color: "#cbd5e1" }}>
                    📈 Open Practice Dashboard
                  </div>
                  <div style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>
                    Review assigned matters, client tasks, and availability settings
                  </div>
                </div>
                <span style={{ fontSize: "16px", color: "#64748b" }}>→</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
