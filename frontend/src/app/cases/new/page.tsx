"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { apiClient } from "@/api/client";
import Link from "next/link";

const DISPUTE_CATEGORIES = [
  { id: "property", label: "Property & Land", icon: "🏡", hint: "Ownership, tenant eviction, partition, builder delay" },
  { id: "business", label: "Business & Contract", icon: "🏢", hint: "Commercial agreements, unpaid invoices, partnership" },
  { id: "money", label: "Money & Cheque Bounce", icon: "💰", hint: "Loan recovery, Sec. 138 NI Act, debt disputes" },
  { id: "family", label: "Family & Matrimonial", icon: "👨‍👩‍👧", hint: "Maintenance, custody, inheritance, succession" },
  { id: "employment", label: "Employment & Labour", icon: "💼", hint: "Wrongful termination, unpaid salary, PF disputes" },
  { id: "consumer", label: "Consumer Complaints", icon: "🛍️", hint: "Defective goods, unfair trade, insurance repudiation" },
  { id: "notice", label: "Legal Notice Received", icon: "📬", hint: "Urgent demand notice, court summons, show cause" },
  { id: "criminal", label: "Police & Criminal", icon: "⚖️", hint: "Bail, FIR quashing, cyber complaints, police inquiries" },
  { id: "other", label: "Other Legal Problem", icon: "📝", hint: "General advisory, document verification, RTI" },
];

function NewCaseIntakeContent() {
  const searchParams = useSearchParams();
  const initialIntent = searchParams?.get("intent");

  const [step, setStep] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState(initialIntent === "notice" ? "notice" : "property");
  const [whatHappened, setWhatHappened] = useState("");
  const [locationCity, setLocationCity] = useState("Delhi NCR");
  const [oppositeParty, setOppositeParty] = useState("");
  const [existingCourtCase, setExistingCourtCase] = useState(false);
  const [cnrOrCaseNo, setCnrOrCaseNo] = useState("");
  const [goal, setGoal] = useState("defend");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [savedDraftNotice, setSavedDraftNotice] = useState(false);

  const [createdCaseId, setCreatedCaseId] = useState<string | null>(null);

  // Safe UI preferences auto-save (Section 16: Never store sensitive legal text in browser storage)
  useEffect(() => {
    const saved = localStorage.getItem("lcc_intake_safe_pref");
    if (saved) {
      try {
        const data = JSON.parse(saved);
        if (data.selectedCategory) setSelectedCategory(data.selectedCategory);
        if (data.locationCity) setLocationCity(data.locationCity);
      } catch {
        // ignore
      }
    }
  }, []);

  const saveDraft = () => {
    // Only safe non-sensitive preferences are persisted
    localStorage.setItem(
      "lcc_intake_safe_pref",
      JSON.stringify({ selectedCategory, locationCity })
    );
    setSavedDraftNotice(true);
    setTimeout(() => setSavedDraftNotice(false), 2500);
  };

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    saveDraft();
    setStep((prev) => Math.min(prev + 1, 4));
  };

  const handleBack = () => {
    setStep((prev) => Math.max(prev - 1, 1));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      // Create concise title and rich plain-language description
      const catObj = DISPUTE_CATEGORIES.find((c) => c.id === selectedCategory);
      const title = oppositeParty.trim()
        ? `${catObj?.label || "Legal Matter"}: Against ${oppositeParty.trim()}`
        : `${catObj?.label || "Legal Matter"} (${locationCity})`;

      const structuredDescription = [
        `Category: ${catObj?.label || selectedCategory}`,
        `Location / Jurisdiction: ${locationCity}`,
        oppositeParty ? `Opposite Party: ${oppositeParty}` : null,
        existingCourtCase && cnrOrCaseNo ? `Existing Court Case / CNR: ${cnrOrCaseNo}` : null,
        `Primary Objective: ${goal}`,
        "",
        "--- Factual Background (Human Intake) ---",
        whatHappened.trim(),
      ]
        .filter(Boolean)
        .join("\n");

      const res = (await apiClient.post("/api/v1/cases", {
        title,
        description: structuredDescription,
      })) as { id: string };

      localStorage.removeItem("lcc_intake_safe_pref");
      setCreatedCaseId(res.id);
      setStep(5);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to create matter. Please check your network connection and retry.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "32px 16px 80px" }}>
      <div style={{ maxWidth: "760px", margin: "0 auto" }}>
        {/* Navigation Breadcrumbs */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--text-muted)" }}>
            <Link href="/dashboard" style={{ color: "var(--text-secondary)" }}>
              My Cases
            </Link>
            <span>/</span>
            <span style={{ color: "#0f172a", fontWeight: 600 }}>Guided Legal Intake</span>
          </div>

          <button
            type="button"
            onClick={saveDraft}
            style={{
              background: "#ffffff",
              border: "1px solid #cbd5e1",
              color: "#475569",
              padding: "5px 14px",
              borderRadius: "6px",
              fontSize: "12px",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            {savedDraftNotice ? "✓ Draft Saved" : "Save Draft"}
          </button>
        </div>

        {/* Header */}
        <div style={{ marginBottom: "28px" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "11px",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "#2563eb",
              marginBottom: "8px",
            }}
          >
            <span>●</span> Plain-Language Case Setup
          </div>
          <h1 style={{ fontSize: "28px", fontWeight: 800, color: "#0f172a", letterSpacing: "-0.02em", margin: "0 0 6px 0" }}>
            Let&apos;s understand your situation.
          </h1>
          <p style={{ color: "#475569", fontSize: "14px", lineHeight: 1.5, margin: 0 }}>
            No legal terms needed. Answer a few simple questions and we&apos;ll organize your case file, identify deadlines, and prepare for your lawyer.
          </p>
        </div>

        {/* Step Progress Bar */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "28px" }}>
          {[
            ["1", "Type of Problem"],
            ["2", "What Happened"],
            ["3", "Parties & Place"],
            ["4", "Review & Open"],
          ].map(([stepNum, label], idx) => {
            const num = idx + 1;
            const isActive = step === num;
            const isDone = step > num;
            return (
              <div key={stepNum} style={{ flex: 1 }}>
                <div
                  style={{
                    height: "4px",
                    borderRadius: "2px",
                    background: isDone ? "#10b981" : isActive ? "#2563eb" : "#e2e8f0",
                    marginBottom: "6px",
                    transition: "all 0.3s ease",
                  }}
                />
                <div style={{ fontSize: "11px", color: isActive ? "#0f172a" : isDone ? "#059669" : "#64748b", fontWeight: isActive ? 700 : 500 }}>
                  {stepNum}. {label}
                </div>
              </div>
            );
          })}
        </div>

        {error && (
          <div
            style={{
              color: "#dc2626",
              background: "#fef2f2",
              border: "1px solid #fecaca",
              padding: "12px 16px",
              borderRadius: "8px",
              fontSize: "13px",
              marginBottom: "20px",
            }}
          >
            {error}
          </div>
        )}

        {/* Step 1: Category Selection */}
        {step === 1 && (
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "12px",
              padding: "28px",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
            }}
          >
            <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a", margin: "0 0 8px 0" }}>
              What kind of problem are you facing?
            </h2>
            <p style={{ color: "#475569", fontSize: "13px", margin: "0 0 20px 0" }}>
              Choose the category that best matches your situation:
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "12px", marginBottom: "24px" }}>
              {DISPUTE_CATEGORIES.map((cat) => {
                const isSelected = selectedCategory === cat.id;
                return (
                  <div
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                    style={{
                      background: isSelected ? "#eff6ff" : "#ffffff",
                      border: isSelected ? "2px solid #2563eb" : "1px solid #e2e8f0",
                      borderRadius: "10px",
                      padding: "16px",
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div style={{ fontSize: "24px", marginBottom: "6px" }}>{cat.icon}</div>
                    <strong style={{ display: "block", fontSize: "14px", color: isSelected ? "#1d4ed8" : "#0f172a" }}>
                      {cat.label}
                    </strong>
                    <span style={{ fontSize: "11px", color: isSelected ? "#2563eb" : "#64748b", marginTop: "4px", display: "block" }}>
                      {cat.hint}
                    </span>
                  </div>
                );
              })}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={handleNext}
                style={{
                  background: "#2563eb",
                  color: "#fff",
                  border: "none",
                  padding: "12px 28px",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                Continue → What Happened
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Factual Narrative in Plain Language */}
        {step === 2 && (
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "12px",
              padding: "28px",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
            }}
          >
            <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a", margin: "0 0 8px 0" }}>
              What happened? Tell us in your own words.
            </h2>
            <p style={{ color: "#475569", fontSize: "13px", margin: "0 0 20px 0" }}>
              Describe the situation simply. Include roughly when it started, what the other party did or failed to do, and if any money or property is involved.
            </p>

            <textarea
              rows={6}
              value={whatHappened}
              onChange={(e) => setWhatHappened(e.target.value)}
              placeholder="e.g. In January 2025, I signed a commercial lease agreement for my retail shop in Saket, New Delhi. The landlord has refused to hand over possession despite taking ₹5,00,000 security deposit. Last week I received a legal notice demanding more rent..."
              style={{
                width: "100%",
                background: "#ffffff",
                border: "1px solid #cbd5e1",
                borderRadius: "8px",
                color: "#0f172a",
                padding: "14px",
                fontSize: "14px",
                lineHeight: 1.6,
                fontFamily: "inherit",
                outline: "none",
                marginBottom: "20px",
              }}
              required
            />

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <button
                type="button"
                onClick={handleBack}
                style={{
                  background: "#ffffff",
                  border: "1px solid #cbd5e1",
                  color: "#334155",
                  padding: "10px 20px",
                  borderRadius: "8px",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                ← Back
              </button>
              <button
                type="button"
                onClick={handleNext}
                disabled={!whatHappened.trim()}
                style={{
                  background: whatHappened.trim() ? "#2563eb" : "#e2e8f0",
                  color: whatHappened.trim() ? "#fff" : "#94a3b8",
                  border: "none",
                  padding: "12px 28px",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: 700,
                  cursor: whatHappened.trim() ? "pointer" : "not-allowed",
                }}
              >
                Continue → Location & Parties
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Location, Parties, and Court Details */}
        {step === 3 && (
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "12px",
              padding: "28px",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
            }}
          >
            <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a", margin: "0 0 8px 0" }}>
              Where did this happen & who is the other side?
            </h2>
            <p style={{ color: "#475569", fontSize: "13px", margin: "0 0 20px 0" }}>
              This helps your lawyer understand jurisdiction and court rules.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginBottom: "24px" }}>
              <div>
                <label style={{ display: "block", fontSize: "13px", fontWeight: 600, color: "#334155", marginBottom: "6px" }}>
                  City or State where this happened
                </label>
                <input
                  type="text"
                  value={locationCity}
                  onChange={(e) => setLocationCity(e.target.value)}
                  placeholder="e.g. New Delhi, Mumbai, Bengaluru, Lucknow"
                  style={{
                    width: "100%",
                    background: "#ffffff",
                    border: "1px solid #cbd5e1",
                    borderRadius: "8px",
                    color: "#0f172a",
                    padding: "10px 14px",
                    fontSize: "14px",
                    outline: "none",
                  }}
                  required
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "13px", fontWeight: 600, color: "#334155", marginBottom: "6px" }}>
                  Name of the Opposite Party (Person or Company)
                </label>
                <input
                  type="text"
                  value={oppositeParty}
                  onChange={(e) => setOppositeParty(e.target.value)}
                  placeholder="e.g. Mehta Trading Corporation / Ramesh Kumar"
                  style={{
                    width: "100%",
                    background: "#ffffff",
                    border: "1px solid #cbd5e1",
                    borderRadius: "8px",
                    color: "#0f172a",
                    padding: "10px 14px",
                    fontSize: "14px",
                    outline: "none",
                  }}
                />
              </div>

              <div style={{ background: "#f8fafc", padding: "14px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "10px", cursor: "pointer", fontSize: "13px", color: "#334155", fontWeight: 500 }}>
                  <input
                    type="checkbox"
                    checked={existingCourtCase}
                    onChange={(e) => setExistingCourtCase(e.target.checked)}
                    style={{ width: "16px", height: "16px", accentColor: "#2563eb" }}
                  />
                  <span>Is there already a court case, FIR, or legal notice number?</span>
                </label>

                {existingCourtCase && (
                  <div style={{ marginTop: "12px" }}>
                    <input
                      type="text"
                      value={cnrOrCaseNo}
                      onChange={(e) => setCnrOrCaseNo(e.target.value)}
                      placeholder="Enter CNR number, Case number, or Notice reference..."
                      style={{
                        width: "100%",
                        background: "#ffffff",
                        border: "1px solid #cbd5e1",
                        borderRadius: "8px",
                        color: "#0f172a",
                        padding: "10px 14px",
                        fontSize: "13px",
                        fontFamily: "var(--font-mono, monospace)",
                        outline: "none",
                      }}
                    />
                    <span style={{ fontSize: "11px", color: "#64748b", marginTop: "4px", display: "block" }}>
                      Tip: We can automatically pull details and daily cause lists using your 16-digit CNR.
                    </span>
                  </div>
                )}
              </div>

              <div>
                <label style={{ display: "block", fontSize: "13px", fontWeight: 600, color: "#334155", marginBottom: "6px" }}>
                  What do you want to achieve?
                </label>
                <select
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  style={{
                    width: "100%",
                    background: "#ffffff",
                    border: "1px solid #cbd5e1",
                    borderRadius: "8px",
                    color: "#0f172a",
                    padding: "10px 14px",
                    fontSize: "14px",
                    outline: "none",
                  }}
                >
                  <option value="defend">Defend against a claim / Respond to notice</option>
                  <option value="recover">Recover money / Damages owed to me</option>
                  <option value="stay">Get an immediate stay order or injunction</option>
                  <option value="settle">Negotiate a mutual settlement</option>
                  <option value="advice">Get professional legal advice on my rights</option>
                </select>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <button
                type="button"
                onClick={handleBack}
                style={{
                  background: "#ffffff",
                  border: "1px solid #cbd5e1",
                  color: "#334155",
                  padding: "10px 20px",
                  borderRadius: "8px",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                ← Back
              </button>
              <button
                type="button"
                onClick={handleNext}
                style={{
                  background: "#2563eb",
                  color: "#fff",
                  border: "none",
                  padding: "12px 28px",
                  borderRadius: "8px",
                  fontSize: "14px",
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                Review Summary →
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Summary and Confirmation */}
        {step === 4 && (
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "12px",
              padding: "28px",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
            }}
          >
            <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a", margin: "0 0 8px 0" }}>
              Review your case summary
            </h2>
            <p style={{ color: "#475569", fontSize: "13px", margin: "0 0 20px 0" }}>
              We will set up your secure matter workspace with these details:
            </p>

            <div style={{ background: "#f8fafc", borderRadius: "10px", padding: "20px", marginBottom: "24px", border: "1px solid #e2e8f0" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px", marginBottom: "14px" }}>
                <div>
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Dispute Type</span>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#0f172a", marginTop: "2px" }}>
                    {DISPUTE_CATEGORIES.find((c) => c.id === selectedCategory)?.label}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Location</span>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#0f172a", marginTop: "2px" }}>{locationCity}</div>
                </div>

                <div>
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Opposite Party</span>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#0f172a", marginTop: "2px" }}>{oppositeParty || "Not specified yet"}</div>
                </div>

                <div>
                  <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Primary Goal</span>
                  <div style={{ fontSize: "14px", fontWeight: 700, color: "#2563eb", marginTop: "2px" }}>{goal}</div>
                </div>
              </div>

              <div>
                <span style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase", fontWeight: 600 }}>Your Description</span>
                <p style={{ fontSize: "13px", color: "#334155", lineHeight: 1.6, margin: "4px 0 0 0" }}>
                  {whatHappened}
                </p>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <button
                type="button"
                onClick={handleBack}
                style={{
                  background: "#ffffff",
                  border: "1px solid #cbd5e1",
                  color: "#334155",
                  padding: "10px 20px",
                  borderRadius: "8px",
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                ← Edit Details
              </button>

              <button
                type="button"
                onClick={handleSubmit}
                disabled={loading}
                style={{
                  background: "#2563eb",
                  color: "#fff",
                  border: "none",
                  padding: "14px 32px",
                  borderRadius: "8px",
                  fontSize: "15px",
                  fontWeight: 700,
                  cursor: loading ? "wait" : "pointer",
                  boxShadow: "0 2px 8px rgba(37, 99, 235, 0.25)",
                }}
              >
                {loading ? "Opening Your Workspace..." : "Establish Case Workspace →"}
              </button>
            </div>
          </div>
        )}

        {/* Step 5: Case Established & Optional Advocate Connection (Sections 15 & 17) */}
        {step === 5 && createdCaseId && (
          <div
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "12px",
              padding: "36px 28px",
              textAlign: "center",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
            }}
          >
            <div style={{ fontSize: "40px", marginBottom: "12px" }}>🎉</div>
            <h2 style={{ fontSize: "22px", fontWeight: 800, color: "#0f172a", margin: "0 0 8px 0" }}>
              Your case workspace is ready
            </h2>
            <p style={{ color: "#475569", fontSize: "14px", maxWidth: "520px", margin: "0 auto 24px", lineHeight: 1.6 }}>
              We have organized your facts, created your case file, and set up your private document vault. What would you like to do next?
            </p>

            <div
              style={{
                background: "#eff6ff",
                border: "1px solid #bfdbfe",
                borderRadius: "10px",
                padding: "20px",
                maxWidth: "560px",
                margin: "0 auto 28px",
                textAlign: "left",
              }}
            >
              <div style={{ fontSize: "12px", textTransform: "uppercase", letterSpacing: "0.08em", color: "#1d4ed8", fontWeight: 700, marginBottom: "6px" }}>
                Recommended Next Step
              </div>
              <h3 style={{ fontSize: "16px", color: "#1e3a8a", margin: "0 0 6px 0", fontWeight: 700 }}>
                Connect with an Advocate for this matter
              </h3>
              <p style={{ fontSize: "13px", color: "#334155", margin: "0 0 16px 0", lineHeight: 1.5 }}>
                Find verified High Court and District advocates specializing in{" "}
                <strong style={{ color: "#0f172a" }}>{DISPUTE_CATEGORIES.find((c) => c.id === selectedCategory)?.label || "your legal issue"}</strong>{" "}
                in <strong style={{ color: "#0f172a" }}>{locationCity}</strong>.
              </p>

              <Link
                href={`/lawyers?practice_area=${encodeURIComponent(
                  DISPUTE_CATEGORIES.find((c) => c.id === selectedCategory)?.label || ""
                )}&location=${encodeURIComponent(locationCity)}`}
                className="btn btn-primary"
                style={{ display: "inline-block", padding: "10px 20px", fontSize: "13px", fontWeight: 700, background: "#2563eb", color: "#ffffff", borderRadius: "8px", textDecoration: "none" }}
              >
                Browse Matching Advocates →
              </Link>
            </div>

            <div>
              <Link
                href={`/cases/${createdCaseId}`}
                style={{ color: "#64748b", fontSize: "13px", textDecoration: "underline" }}
              >
                Skip advocate search and go directly to Case Workspace →
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function NewCaseIntake() {
  return (
    <Suspense fallback={<div style={{ padding: "80px 20px", textAlign: "center", color: "#94a3b8" }}>Loading case intake wizard...</div>}>
      <NewCaseIntakeContent />
    </Suspense>
  );
}
