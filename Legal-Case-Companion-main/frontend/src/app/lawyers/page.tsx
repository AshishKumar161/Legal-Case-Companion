"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiClient } from "@/api/client";
import { LawyerProfileItem } from "@/types";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { trackFunnelEvent } from "@/lib/analytics";
import styles from "./discovery.module.css";

// ----------------------------------------------------------------------------
// 1. Plain-Language Intent Definitions (Section 2)
// ----------------------------------------------------------------------------

interface LegalIntentOption {
  id: string;
  label: string;
  icon: string;
  practiceArea: string;
  explanation: string;
}

const INTENT_OPTIONS: LegalIntentOption[] = [
  {
    id: "property",
    label: "Property problem",
    icon: "🏡",
    practiceArea: "Property",
    explanation: "Disagreement about land, house, rent, ownership, or property documents.",
  },
  {
    id: "family",
    label: "Family problem",
    icon: "👨‍👩‍👧",
    practiceArea: "Family",
    explanation: "Divorce, maintenance, child custody, domestic issues, or family property.",
  },
  {
    id: "money",
    label: "Money / payment problem",
    icon: "💰",
    practiceArea: "Commercial",
    explanation: "Unpaid salary, loan recovery, bounced cheques, or financial disputes.",
  },
  {
    id: "employment",
    label: "Employment problem",
    icon: "💼",
    practiceArea: "Labor",
    explanation: "Wrongful termination, workplace issues, gratuity, or PF disputes.",
  },
  {
    id: "criminal",
    label: "Criminal matter",
    icon: "⚖️",
    practiceArea: "Criminal",
    explanation: "Police complaints, FIR, bail, summons, or criminal defense.",
  },
  {
    id: "consumer",
    label: "Consumer problem",
    icon: "🛍️",
    practiceArea: "Consumer",
    explanation: "Defective goods, service deficiency, insurance claims, or refund issues.",
  },
  {
    id: "business",
    label: "Business problem",
    icon: "🏢",
    practiceArea: "Corporate",
    explanation: "Commercial agreements, partnership disputes, unpaid invoices, or vendor issues.",
  },
  {
    id: "court",
    label: "Court case",
    icon: "🏛️",
    practiceArea: "Civil",
    explanation: "Already listed in court, need an advocate to represent or appear.",
  },
  {
    id: "notice",
    label: "Legal notice",
    icon: "📬",
    practiceArea: "Litigation",
    explanation: "Received a legal notice or need to send a formal legal demand.",
  },
  {
    id: "other",
    label: "Something else",
    icon: "📝",
    practiceArea: "",
    explanation: "General legal advice, document drafting, or regulatory guidance.",
  },
];

const POPULAR_LOCATIONS = [
  "All Locations",
  "Delhi NCR",
  "Mumbai",
  "Bengaluru",
  "Chennai",
  "Kolkata",
  "Hyderabad",
  "Pune",
  "Ahmedabad",
];

const LANGUAGE_OPTIONS = [
  "Any Language",
  "Hindi",
  "English",
  "Tamil",
  "Telugu",
  "Marathi",
  "Bengali",
  "Gujarati",
  "Kannada",
];

const BUDGET_OPTIONS = [
  { id: "all", label: "Any budget", maxFee: "" },
  { id: "1000", label: "Under ₹1,000", maxFee: "1000" },
  { id: "3000", label: "₹1,000 - ₹3,000", maxFee: "3000" },
  { id: "5000", label: "₹3,000 - ₹5,000", maxFee: "5000" },
];

export default function LawyerDiscoveryPage() {
  const searchParams = useSearchParams();

  // URL Query Sync
  const initialPracticeArea = searchParams?.get("practice_area") || "";
  const initialLocation = searchParams?.get("location") || "";

  const [rawLawyers, setRawLawyers] = useState<LawyerProfileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Progressive Wizard State (Section 3)
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);

  // Wizard selections
  const [selectedIntentId, setSelectedIntentId] = useState<string>(() => {
    if (initialPracticeArea) {
      const match = INTENT_OPTIONS.find((i) => i.practiceArea.toLowerCase() === initialPracticeArea.toLowerCase());
      return match ? match.id : "other";
    }
    return "";
  });
  const [hasCourtCase, setHasCourtCase] = useState<"yes" | "no" | "">("");
  const [knownCourt, setKnownCourt] = useState("");
  const [urgencyPreference, setUrgencyPreference] = useState<"not_urgent" | "few_days" | "this_week" | "urgent" | "">("");

  // Filter States (Section 6)
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedLocation, setSelectedLocation] = useState(initialLocation || "All Locations");
  const [selectedLanguage, setSelectedLanguage] = useState("Any Language");
  const [selectedBudget, setSelectedBudget] = useState("all");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [minExp, setMinExp] = useState("");
  const [courtJurisdiction, setCourtJurisdiction] = useState("");

  // Telemetry on mount
  useEffect(() => {
    trackFunnelEvent("discovery_started", {
      intent: selectedIntentId || undefined,
      location: selectedLocation !== "All Locations" ? selectedLocation : undefined,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch lawyers from real backend API (bounded, unauthenticated public view supported)
  const fetchLawyers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (searchTerm.trim()) params.set("search", searchTerm.trim());

      if (selectedLocation !== "All Locations") {
        params.set("location", selectedLocation);
      }

      // Map chosen intent to backend practice area
      const activeIntent = INTENT_OPTIONS.find((i) => i.id === selectedIntentId);
      if (activeIntent?.practiceArea) {
        params.set("practice_area", activeIntent.practiceArea);
      }

      if (selectedLanguage !== "Any Language") {
        params.set("language", selectedLanguage);
      }

      const activeBudget = BUDGET_OPTIONS.find((b) => b.id === selectedBudget);
      if (activeBudget?.maxFee) {
        params.set("max_fee", activeBudget.maxFee);
      }

      if (minExp) params.set("min_experience", minExp);
      if (courtJurisdiction) params.set("court_jurisdiction", courtJurisdiction);
      if (verifiedOnly) params.set("verified_only", "true");

      params.set("limit", "50");

      const res = await apiClient.get(`/api/v1/lawyers?${params.toString()}`, { requireAuth: false });
      const items: LawyerProfileItem[] = Array.isArray(res) ? res : res?.items || [];
      setRawLawyers(items);

      trackFunnelEvent("results_shown", {
        results_count: items.length,
        intent: selectedIntentId,
        location: selectedLocation,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load advocates.";
      setError(msg);
      setRawLawyers([]);
    } finally {
      setLoading(false);
    }
  }, [
    searchTerm,
    selectedLocation,
    selectedIntentId,
    selectedLanguage,
    selectedBudget,
    minExp,
    courtJurisdiction,
    verifiedOnly,
  ]);

  // Debounced fetch on filter change
  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchLawyers();
    }, 250);
    return () => clearTimeout(timer);
  }, [fetchLawyers]);

  // Deterministic Explainable Ranking (Section 5)
  const rankedLawyers = useMemo(() => {
    const activeIntent = INTENT_OPTIONS.find((i) => i.id === selectedIntentId);

    return rawLawyers
      .map((lawyer) => {
        let score = 0;
        const matchReasons: string[] = [];

        // 1. Practice area match
        if (activeIntent?.practiceArea && lawyer.practice_areas) {
          const areas = Array.isArray(lawyer.practice_areas) ? lawyer.practice_areas : [lawyer.practice_areas];
          const hasArea = areas.some((pa) =>
            pa.toLowerCase().includes(activeIntent.practiceArea.toLowerCase())
          );
          if (hasArea) {
            score += 4;
            matchReasons.push(`Practice area (${activeIntent.label})`);
          }
        }

        // 2. Location match
        if (selectedLocation !== "All Locations" && lawyer.location) {
          if (lawyer.location.toLowerCase().includes(selectedLocation.toLowerCase())) {
            score += 3;
            matchReasons.push(`Location (${selectedLocation})`);
          }
        }

        // 3. Language match
        if (selectedLanguage !== "Any Language" && lawyer.languages) {
          const langs = Array.isArray(lawyer.languages) ? lawyer.languages : [lawyer.languages];
          if (langs.some((l) => l.toLowerCase().includes(selectedLanguage.toLowerCase()))) {
            score += 2;
            matchReasons.push(`Language (${selectedLanguage})`);
          }
        }

        // 4. Budget match
        const budgetObj = BUDGET_OPTIONS.find((b) => b.id === selectedBudget);
        if (budgetObj?.maxFee && lawyer.consultation_fee) {
          if (lawyer.consultation_fee <= parseFloat(budgetObj.maxFee)) {
            score += 2;
            matchReasons.push(`Within budget`);
          }
        }

        // 5. Verification status
        if (lawyer.verification_status === "VERIFIED") {
          score += 2;
        }

        return {
          lawyer,
          score,
          matchExplanation:
            matchReasons.length > 0 ? `Matches your ${matchReasons.join(" and ")}` : null,
        };
      })
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return (b.lawyer.experience_years || 0) - (a.lawyer.experience_years || 0);
      });
  }, [rawLawyers, selectedIntentId, selectedLocation, selectedLanguage, selectedBudget]);

  // Handle Intent Selection
  const handleSelectIntent = (intent: LegalIntentOption) => {
    if (selectedIntentId === intent.id) {
      setSelectedIntentId("");
    } else {
      setSelectedIntentId(intent.id);
      trackFunnelEvent("intent_selected", { intent: intent.id });
    }
  };

  const handleResetFilters = () => {
    setSelectedIntentId("");
    setSelectedLocation("All Locations");
    setSelectedLanguage("Any Language");
    setSelectedBudget("all");
    setSearchTerm("");
    setMinExp("");
    setCourtJurisdiction("");
    setVerifiedOnly(false);
    setHasCourtCase("");
    setKnownCourt("");
    setUrgencyPreference("");
    setWizardOpen(false);
  };

  return (
    <div className={styles.pageContainer}>
      {/* Header */}
      <header className={styles.discoveryHeader}>
        <div className={styles.eyebrow}>
          <span>⚖️</span>
          <span>Verified Advocate Directory</span>
        </div>
        <h1 className={styles.title}>Find Legal Help in India</h1>
        <p className={styles.subtitle}>
          Connect directly with verified High Court and District advocates. Choose your issue in plain language, compare transparent consultation fees, and schedule an appointment securely.
        </p>
      </header>

      {/* Primary Intent Entry: "How can we help you?" (Section 2) */}
      <section className={styles.intentSection} aria-label="Select legal issue">
        <div className={styles.intentSectionHeader}>
          <div>
            <h2 className={styles.intentSectionTitle}>
              <span>🎯</span> What kind of legal help do you need?
            </h2>
            <span className={styles.intentSectionHint}>
              Select the option closest to your situation. No legal background needed.
            </span>
          </div>

          <button
            type="button"
            className={styles.advancedToggleBtn}
            onClick={() => setWizardOpen(!wizardOpen)}
          >
            {wizardOpen ? "Close Guided Questions ▲" : "✨ Answer 3 Quick Questions →"}
          </button>
        </div>

        <div className={styles.intentGrid}>
          {INTENT_OPTIONS.map((intent) => {
            const isSelected = selectedIntentId === intent.id;
            return (
              <button
                key={intent.id}
                type="button"
                className={`${styles.intentCard} ${isSelected ? styles.intentCardActive : ""}`}
                onClick={() => handleSelectIntent(intent)}
              >
                <div className={styles.intentCardTop}>
                  <span className={styles.intentIcon}>{intent.icon}</span>
                  <span className={styles.intentLabel}>{intent.label}</span>
                </div>
                <p className={styles.intentDesc}>{intent.explanation}</p>
              </button>
            );
          })}
        </div>
      </section>

      {/* Progressive Guided Wizard (Section 3) */}
      {wizardOpen && (
        <section className={styles.wizardBox} aria-label="Guided discovery wizard">
          <div className={styles.wizardHeader}>
            <div className={styles.wizardStepTitle}>
              Step {wizardStep} of 4: Guided Advocate Matching
            </div>
            <span className={styles.wizardStepCounter}>
              {wizardStep === 1
                ? "Location & Court"
                : wizardStep === 2
                ? "Preferred Language"
                : wizardStep === 3
                ? "Budget"
                : "Timeline / Urgency"}
            </span>
          </div>

          {/* Wizard Step 1: Location & Court */}
          {wizardStep === 1 && (
            <div>
              <h3 className={styles.questionTitle}>Where is your matter located?</h3>
              <p className={styles.questionSubtitle}>
                Advocates practice in specific state high courts and district jurisdictions.
              </p>

              <div className={styles.pillGroup}>
                {POPULAR_LOCATIONS.map((loc) => (
                  <button
                    key={loc}
                    type="button"
                    className={`${styles.choicePill} ${selectedLocation === loc ? styles.choicePillActive : ""}`}
                    onClick={() => setSelectedLocation(loc)}
                  >
                    📍 {loc}
                  </button>
                ))}
              </div>

              <div style={{ marginTop: "16px" }}>
                <label style={{ fontSize: "13px", color: "#cbd5e1", display: "block", marginBottom: "8px" }}>
                  Do you already have an ongoing court case?
                </label>
                <div style={{ display: "flex", gap: "10px" }}>
                  <button
                    type="button"
                    className={`${styles.choicePill} ${hasCourtCase === "yes" ? styles.choicePillActive : ""}`}
                    onClick={() => setHasCourtCase("yes")}
                  >
                    Yes, already in court
                  </button>
                  <button
                    type="button"
                    className={`${styles.choicePill} ${hasCourtCase === "no" ? styles.choicePillActive : ""}`}
                    onClick={() => setHasCourtCase("no")}
                  >
                    No, not filed yet / Pre-litigation
                  </button>
                </div>
              </div>

              {hasCourtCase === "yes" && (
                <div style={{ marginTop: "12px" }}>
                  <input
                    className={styles.searchInput}
                    placeholder="Which court? (e.g., Delhi High Court, Saket District Court)"
                    value={knownCourt}
                    onChange={(e) => setKnownCourt(e.target.value)}
                  />
                </div>
              )}
            </div>
          )}

          {/* Wizard Step 2: Language Preference */}
          {wizardStep === 2 && (
            <div>
              <h3 className={styles.questionTitle}>What language would you prefer to speak in?</h3>
              <p className={styles.questionSubtitle}>
                Choose the language you feel most comfortable discussing your situation in.
              </p>

              <div className={styles.pillGroup}>
                {LANGUAGE_OPTIONS.map((lang) => (
                  <button
                    key={lang}
                    type="button"
                    className={`${styles.choicePill} ${selectedLanguage === lang ? styles.choicePillActive : ""}`}
                    onClick={() => setSelectedLanguage(lang)}
                  >
                    🗣️ {lang}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Wizard Step 3: Budget Preference */}
          {wizardStep === 3 && (
            <div>
              <h3 className={styles.questionTitle}>What is your approximate budget for initial consultation?</h3>
              <p className={styles.questionSubtitle}>
                Advocates list their transparent consultation fees with zero hidden charges.
              </p>

              <div className={styles.pillGroup}>
                {BUDGET_OPTIONS.map((b) => (
                  <button
                    key={b.id}
                    type="button"
                    className={`${styles.choicePill} ${selectedBudget === b.id ? styles.choicePillActive : ""}`}
                    onClick={() => setSelectedBudget(b.id)}
                  >
                    💳 {b.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Wizard Step 4: Urgency Preference */}
          {wizardStep === 4 && (
            <div>
              <h3 className={styles.questionTitle}>How soon do you need to speak with an advocate?</h3>
              <p className={styles.questionSubtitle}>
                This indicates your stated preference for scheduling. (Does not constitute legal advice).
              </p>

              <div className={styles.pillGroup}>
                {[
                  ["not_urgent", "Not urgent (just exploring)"],
                  ["few_days", "Within a few days"],
                  ["this_week", "This week"],
                  ["urgent", "Urgent / Immediate notice deadline"],
                ].map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    className={`${styles.choicePill} ${urgencyPreference === key ? styles.choicePillActive : ""}`}
                    onClick={() => setUrgencyPreference(key as any)}
                  >
                    ⏱️ {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Wizard Navigation */}
          <div className={styles.wizardNav}>
            {wizardStep > 1 ? (
              <button
                type="button"
                className={styles.secondaryActionBtn}
                onClick={() => setWizardStep((prev) => prev - 1)}
              >
                ← Back
              </button>
            ) : (
              <div />
            )}

            {wizardStep < 4 ? (
              <button
                type="button"
                className={styles.primaryActionBtn}
                style={{ maxWidth: "160px" }}
                onClick={() => setWizardStep((prev) => prev + 1)}
              >
                Next Step →
              </button>
            ) : (
              <button
                type="button"
                className={styles.primaryActionBtn}
                style={{ maxWidth: "200px" }}
                onClick={() => setWizardOpen(false)}
              >
                Show Matching Advocates ({rankedLawyers.length}) ✓
              </button>
            )}
          </div>
        </section>
      )}

      {/* Simplified Filter Experience (Section 6) */}
      <section className={styles.filterContainer} aria-label="Lawyer search filters">
        <div className={styles.mainFiltersRow}>
          <input
            className={styles.searchInput}
            placeholder="Search by advocate name, court, or city..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />

          <select
            className={styles.filterSelect}
            value={selectedLocation}
            onChange={(e) => setSelectedLocation(e.target.value)}
          >
            {POPULAR_LOCATIONS.map((loc) => (
              <option key={loc} value={loc}>
                {loc}
              </option>
            ))}
          </select>

          <select
            className={styles.filterSelect}
            value={selectedLanguage}
            onChange={(e) => setSelectedLanguage(e.target.value)}
          >
            {LANGUAGE_OPTIONS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>

          <select
            className={styles.filterSelect}
            value={selectedBudget}
            onChange={(e) => setSelectedBudget(e.target.value)}
          >
            {BUDGET_OPTIONS.map((b) => (
              <option key={b.id} value={b.id}>
                {b.label}
              </option>
            ))}
          </select>

          <button
            type="button"
            className={styles.advancedToggleBtn}
            onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
          >
            {showAdvancedFilters ? "Less Filters ▲" : "More Filters ▼"}
          </button>
        </div>

        {/* Collapsible Advanced Filters Drawer */}
        {showAdvancedFilters && (
          <div className={styles.advancedDrawer}>
            <div>
              <label style={{ fontSize: "11px", color: "#94a3b8", display: "block", marginBottom: "4px" }}>
                Court Jurisdiction
              </label>
              <input
                className={styles.searchInput}
                placeholder="e.g. High Court of Delhi"
                value={courtJurisdiction}
                onChange={(e) => setCourtJurisdiction(e.target.value)}
              />
            </div>

            <div>
              <label style={{ fontSize: "11px", color: "#94a3b8", display: "block", marginBottom: "4px" }}>
                Minimum Experience (Years)
              </label>
              <select
                className={styles.filterSelect}
                style={{ width: "100%" }}
                value={minExp}
                onChange={(e) => setMinExp(e.target.value)}
              >
                <option value="">Any Experience</option>
                <option value="3">3+ Years</option>
                <option value="5">5+ Years</option>
                <option value="10">10+ Years</option>
                <option value="15">15+ Years</option>
              </select>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px", paddingTop: "20px" }}>
              <input
                type="checkbox"
                id="verifiedOnlyCb"
                checked={verifiedOnly}
                onChange={(e) => setVerifiedOnly(e.target.checked)}
                style={{ width: "16px", height: "16px", accentColor: "#6366f1" }}
              />
              <label htmlFor="verifiedOnlyCb" style={{ fontSize: "13px", color: "#fff", cursor: "pointer" }}>
                Verified Bar Counsel only
              </label>
            </div>
          </div>
        )}
      </section>

      {/* Results Header */}
      <div className={styles.resultsHeader}>
        <div className={styles.resultsCount}>
          Showing <strong>{rankedLawyers.length}</strong> available advocates
          {selectedIntentId && (
            <span> for <strong>{INTENT_OPTIONS.find((i) => i.id === selectedIntentId)?.label}</strong></span>
          )}
        </div>

        {(selectedIntentId || selectedLocation !== "All Locations" || selectedLanguage !== "Any Language" || selectedBudget !== "all" || searchTerm) && (
          <button
            type="button"
            className={styles.advancedToggleBtn}
            style={{ fontSize: "11px", padding: "4px 10px" }}
            onClick={handleResetFilters}
          >
            Reset all choices ✕
          </button>
        )}
      </div>

      {/* Directory Grid / Empty / Loading */}
      {loading ? (
        <div style={{ padding: "40px 0" }}>
          <LoadingSkeleton type="card" count={3} />
        </div>
      ) : error ? (
        <div style={{ padding: "24px", background: "rgba(239, 68, 68, 0.12)", color: "#f87171", borderRadius: "8px" }}>
          {error}
        </div>
      ) : rankedLawyers.length === 0 ? (
        /* Empty State (Section 28) */
        <div className={styles.emptyStateContainer}>
          <div className={styles.emptyStateIcon}>🔍</div>
          <h3 className={styles.emptyStateTitle}>We couldn&apos;t find an advocate matching all your choices</h3>
          <p className={styles.emptyStateDesc}>
            Try changing your location, preferred language, or budget range to see more advocates.
          </p>
          <div className={styles.emptyStateActions}>
            <button
              type="button"
              className={styles.primaryActionBtn}
              onClick={() => {
                setSelectedLocation("All Locations");
                setSelectedBudget("all");
                setSelectedLanguage("Any Language");
              }}
            >
              Broaden Location & Budget
            </button>
            <button
              type="button"
              className={styles.secondaryActionBtn}
              onClick={handleResetFilters}
            >
              Reset All Filters
            </button>
          </div>
        </div>
      ) : (
        /* Advocate Grid */
        <div className={styles.lawyerGrid}>
          {rankedLawyers.map(({ lawyer, matchExplanation }) => {
            const isVerified = lawyer.verification_status === "VERIFIED";
            const languagesList = Array.isArray(lawyer.languages)
              ? lawyer.languages.join(", ")
              : lawyer.languages || "English, Hindi";
            const practiceAreasList = Array.isArray(lawyer.practice_areas)
              ? lawyer.practice_areas.join(", ")
              : lawyer.practice_areas || "General Practice";

            const lawyerId = lawyer.user_id || lawyer.id;

            return (
              <div key={lawyer.id} className={styles.lawyerCard}>
                <div className={styles.lawyerTopRow}>
                  <div>
                    <h3 className={styles.lawyerName}>Adv. {lawyer.full_name}</h3>
                    <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                      {lawyer.experience_years ? `${lawyer.experience_years} Years at Bar` : "Enrolled Counsel"}
                      {lawyer.location ? ` · ${lawyer.location}` : ""}
                    </div>
                  </div>

                  {isVerified && (
                    <span className={styles.verifiedBadge}>
                      <span>✓</span> Verified Counsel
                    </span>
                  )}
                </div>

                {/* Deterministic Explainability Tags (Phase 9 Section 10) */}
                {lawyer.match_reasons && lawyer.match_reasons.length > 0 ? (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", margin: "8px 0" }}>
                    {lawyer.match_reasons.map((reason, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          background: "rgba(56, 189, 248, 0.12)",
                          color: "#38bdf8",
                          border: "1px solid rgba(56, 189, 248, 0.3)",
                          padding: "2px 8px",
                          borderRadius: "4px",
                        }}
                      >
                        ✓ {reason}
                      </span>
                    ))}
                  </div>
                ) : matchExplanation ? (
                  <div className={styles.explainabilityTag}>
                    <span>🎯</span> {matchExplanation}
                  </div>
                ) : null}

                {/* Practice Areas */}
                <div className={styles.metaRow}>
                  <strong style={{ color: "#ffffff" }}>Practice:</strong>
                  <span>{practiceAreasList}</span>
                </div>

                {/* Languages */}
                <div className={styles.metaRow}>
                  <strong style={{ color: "#ffffff" }}>Languages:</strong>
                  <span>{languagesList}</span>
                </div>

                {/* Fee Display */}
                <div className={styles.feeDisplay}>
                  <div>
                    <div className={styles.feeLabel}>Consultation Fee</div>
                    <div className={styles.feeAmount}>₹{lawyer.consultation_fee || 2500}</div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className={styles.feeLabel}>Duration</div>
                    <div style={{ fontSize: "12px", color: "#cbd5e1", fontWeight: 600 }}>30 Minutes</div>
                  </div>
                </div>

                {/* Actions */}
                <div className={styles.cardFooter}>
                  <Link
                    href={`/lawyers/${lawyerId}`}
                    className={styles.secondaryActionBtn}
                    onClick={() => trackFunnelEvent("profile_opened", { lawyer_id: lawyerId })}
                  >
                    View Profile
                  </Link>

                  <Link
                    href={`/lawyers/${lawyerId}?action=book`}
                    className={styles.primaryActionBtn}
                    onClick={() => trackFunnelEvent("slot_selected", { lawyer_id: lawyerId })}
                  >
                    Schedule Session →
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
