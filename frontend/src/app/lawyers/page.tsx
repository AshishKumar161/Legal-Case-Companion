"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiClient } from "@/api/client";
import { LawyerProfileItem } from "@/types";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { trackFunnelEvent } from "@/lib/analytics";
import {
  LawyerIcon,
  CheckCircleIcon,
  CourthouseIcon,
  SearchIcon,
  ScalesIcon,
} from "@/components/ui/Icons";
import { LawyerCard, EmptyState, Badge } from "@/components/ui";
import styles from "./discovery.module.css";

// ----------------------------------------------------------------------------
// 1. Plain-Language Intent Definitions (Section 2)
// ----------------------------------------------------------------------------

interface LegalIntentOption {
  id: string;
  label: string;
  practiceArea: string;
  explanation: string;
}

const INTENT_OPTIONS: LegalIntentOption[] = [
  {
    id: "property",
    label: "Property & Land",
    practiceArea: "Property",
    explanation: "Disagreement about land, house, rent, ownership, or property documents.",
  },
  {
    id: "family",
    label: "Family & Matrimonial",
    practiceArea: "Family",
    explanation: "Divorce, maintenance, child custody, domestic issues, or family property.",
  },
  {
    id: "money",
    label: "Money & Cheques",
    practiceArea: "Commercial",
    explanation: "Unpaid salary, loan recovery, bounced cheques, or financial disputes.",
  },
  {
    id: "employment",
    label: "Employment & Work",
    practiceArea: "Labor",
    explanation: "Wrongful termination, workplace issues, gratuity, or PF disputes.",
  },
  {
    id: "criminal",
    label: "Criminal & Bail",
    practiceArea: "Criminal",
    explanation: "Police complaints, FIR, bail, summons, or criminal defense.",
  },
  {
    id: "consumer",
    label: "Consumer Dispute",
    practiceArea: "Consumer",
    explanation: "Defective goods, service deficiency, insurance claims, or refund issues.",
  },
  {
    id: "business",
    label: "Business & Contracts",
    practiceArea: "Corporate",
    explanation: "Commercial agreements, partnership disputes, unpaid invoices, or vendor issues.",
  },
  {
    id: "court",
    label: "Court Case",
    practiceArea: "Civil",
    explanation: "Already listed in court, need an advocate to represent or appear.",
  },
  {
    id: "notice",
    label: "Legal Notice",
    practiceArea: "Litigation",
    explanation: "Received a legal notice or need to send a formal legal demand.",
  },
  {
    id: "other",
    label: "General Legal Advice",
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
        <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "12px", fontWeight: 700, color: "var(--navy-secondary)", marginBottom: "8px" }}>
          <ScalesIcon size={16} color="var(--gold-accent)" />
          <span>Verified Advocate Directory</span>
        </div>
        <h1 className={styles.title}>Find a Lawyer</h1>
        <p className={styles.subtitle}>
          Connect directly with verified advocates. Choose your issue, compare transparent fees, and talk to a legal professional today.
        </p>
      </header>

      {/* Primary Intent Entry: "What do you need help with?" (Section 1 & 11) */}
      <section style={{ marginBottom: "20px" }}>
        <h2 style={{ fontSize: "15px", fontWeight: 700, color: "var(--navy-primary)", marginBottom: "10px" }}>
          What kind of legal help do you need?
        </h2>
        <div className={styles.intentPills}>
          {INTENT_OPTIONS.map((intent) => {
            const isSelected = selectedIntentId === intent.id;
            return (
              <button
                key={intent.id}
                type="button"
                className={`${styles.intentPill} ${isSelected ? styles.intentPillActive : ""}`}
                onClick={() => handleSelectIntent(intent)}
              >
                <span>{intent.label}</span>
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
                    {loc}
                  </button>
                ))}
              </div>

              <div style={{ marginTop: "16px" }}>
                <label style={{ fontSize: "13px", color: "var(--text-secondary)", display: "block", marginBottom: "8px" }}>
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
                    {lang}
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
                    {b.label}
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
                    onClick={() => setUrgencyPreference(key as never)}
                  >
                    {label}
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

      {/* Filter Bar */}
      <section className={styles.filterBar} aria-label="Lawyer search filters">
        <div className={styles.searchBox}>
          <SearchIcon size={16} color="var(--text-muted)" />
          <input
            className={styles.searchInput}
            placeholder="Search by advocate name, court, or city..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <select
          className={styles.selectField}
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
          className={styles.selectField}
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
          className={styles.selectField}
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
          onClick={() => setShowAdvancedFilters((prev) => !prev)}
          className={styles.selectField}
          style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: "6px" }}
        >
          <span>{showAdvancedFilters ? "▲ Less Filters" : "▼ More Filters"}</span>
        </button>
      </section>

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
        <div style={{ padding: "24px", background: "rgba(239, 68, 68, 0.08)", color: "var(--status-urgent)", borderRadius: "8px" }}>
          {error}
        </div>
      ) : rankedLawyers.length === 0 ? (
        /* Empty State */
        <EmptyState
          icon={<SearchIcon size={28} color="var(--navy-600)" />}
          title="No matching advocates found"
          description="Try adjusting your court location, budget, or practice area to see more verified advocates."
          actionLabel="Reset All Filters"
          onAction={handleResetFilters}
        />
      ) : (
        /* Advocate Grid (Section 11) */
        <div className={styles.lawyerGrid}>
          {rankedLawyers.map(({ lawyer, matchExplanation }) => {
            const isVerified =
              lawyer.verification_status === "VERIFIED" ||
              lawyer.verification_status === "APPROVED";

            let practiceAreasArray: string[] = ["Civil", "General Practice"];
            if (lawyer.practice_areas) {
              if (Array.isArray(lawyer.practice_areas)) {
                practiceAreasArray = lawyer.practice_areas;
              } else if (typeof lawyer.practice_areas === "string") {
                practiceAreasArray = lawyer.practice_areas.split(",").map((s) => s.trim());
              }
            }

            const courtOrLocation =
              lawyer.court_jurisdictions && lawyer.court_jurisdictions.length > 0
                ? lawyer.court_jurisdictions[0]
                : lawyer.location
                ? `${lawyer.location} District Court`
                : "District & High Court";

            const languagesArray: string[] = Array.isArray(lawyer.languages)
              ? lawyer.languages
              : typeof (lawyer.languages as unknown) === "string"
              ? (lawyer.languages as unknown as string).split(",").map((s: string) => s.trim())
              : [];

            const lawyerId = lawyer.user_id || lawyer.id;
            const displayName = (lawyer.full_name || "Legal Professional").replace(/^(advocate|adv\.)\s+/i, "");

            return (
              <LawyerCard
                key={lawyer.id}
                id={lawyerId}
                name={`Advocate ${displayName}`}
                verified={isVerified}
                practiceAreas={practiceAreasArray}
                experienceYears={lawyer.experience_years}
                location={courtOrLocation}
                languages={languagesArray}
                consultationFee={lawyer.consultation_fee || 1500}
                matchExplanation={matchExplanation}
                profileHref={`/lawyers/${lawyerId}`}
                onViewProfile={() => {
                  trackFunnelEvent("profile_opened", { lawyer_id: lawyerId });
                  window.location.href = `/lawyers/${lawyerId}`;
                }}
                onBook={() => {
                  trackFunnelEvent("slot_selected", { lawyer_id: lawyerId });
                  window.location.href = `/lawyers/${lawyerId}?action=book`;
                }}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
