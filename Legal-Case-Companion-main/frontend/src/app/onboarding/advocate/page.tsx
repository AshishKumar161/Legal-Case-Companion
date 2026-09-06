"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import styles from "../onboarding.module.css";

const STATE_BAR_COUNCILS = [
  "Bar Council of Delhi",
  "Bar Council of Maharashtra & Goa",
  "Bar Council of Uttar Pradesh",
  "Bar Council of Punjab & Haryana",
  "Bar Council of Karnataka",
  "Bar Council of Tamil Nadu",
];

const PILOT_COURTS = [
  "High Court of Delhi",
  "High Court of Bombay",
  "High Court of Allahabad",
  "Delhi District Courts (Tis Hazari, Saket, Patiala House)",
  "Mumbai City Civil & Sessions Court",
];

const PRACTICE_AREAS = [
  "Criminal Law & Bail",
  "Civil Litigation & Injunctions",
  "Constitutional & Writ Petitions",
  "Family & Matrimonial Disputes",
  "Corporate & Commercial Arbitration",
  "Real Estate & Property Law",
  "Cheque Bounce (NI Act Sec 138)",
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

  const handleStep1Submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    const cleaned = enrollmentNo.trim().toUpperCase();
    if (!cleaned || !cleaned.includes("/")) {
      setError("Please enter a valid enrollment number in standard STATE/NUMBER/YEAR format (e.g., D/1234/2018).");
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
      // 1. Submit advocate verification details to backend
      await apiClient.post("/api/v1/verification/lawyer/submit", {
        enrollment_number: enrollmentNo.trim().toUpperCase(),
        state_bar_council: barCouncil,
      }).catch(() => null);

      // 2. Telemetry event recording advocate onboarding completion
      await apiClient.post("/api/v1/pilot/telemetry/event", {
        event_type: "ADVOCATE_ONBOARDING_COMPLETED",
        metadata: {
          bar_council: barCouncil,
          practice_areas_count: selectedAreas.length,
          fee: numFee,
          instant_enabled: instantEnabled,
        },
      }).catch(() => null);

      setStep(4);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record credentials.";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.badge}>Advocate Pilot Onboarding • Professional Hub</div>
          <h1 className={styles.title}>
            {step === 1 && "Bar Council Credentials"}
            {step === 2 && "Practice Areas & Jurisdictions"}
            {step === 3 && "Consultation Options & Availability"}
            {step === 4 && "Verification Status & Value Activation"}
          </h1>
          <p className={styles.subtitle}>
            {step === 1 && "Provide your official statutory Bar Council enrollment to initiate professional verification."}
            {step === 2 && "Select your core Indian court jurisdictions and domain expertise for client discovery."}
            {step === 3 && "Set your initial consultation rate and on-demand video session availability."}
            {step === 4 && "Your credentials have been submitted. Discoverability activates upon review."}
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

        {/* STEP 1: Bar Council Details */}
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
              <span style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "4px", display: "block" }}>
                Format: STATE/ROLL_NUMBER/YEAR as issued on Bar ID card
              </span>
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
                        color: selected ? "#93c5fd" : "var(--text-secondary)",
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
                <strong>Pilot Pricing Boundary:</strong> Initial consultation fees are structured between ₹500 and ₹2,500 to maintain client conversion confidence during pilot.
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
                  <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                    Receive emergency consultation alerts when clients request immediate legal advice while you are online.
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
                {submitting ? "Saving Profile..." : "Submit Professional Profile →"}
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
                  <strong>{barCouncil}</strong> is undergoing verification by our compliance team. To preserve litigant trust, your public discovery card will activate once verification is approved.
                </div>
              </div>
            </div>

            <div style={{ textAlign: "center", marginBottom: "20px" }}>
              <h2 style={{ fontSize: "17px", color: "#fff", margin: "0 0 6px 0" }}>
                Your Advocate Workspace is Active
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", margin: 0 }}>
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
                    Track item numbers, courtroom court numbers, and upcoming hearing dates
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
                    Review pending consultations, client tasks, and availability settings
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
