"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/api/client";
import styles from "../onboarding.module.css";

type ClientIntent = "NEED_LAWYER" | "HAVE_CASE" | "RECEIVED_NOTICE" | "MANAGE_MATTER";

interface IntentConfig {
  id: ClientIntent;
  icon: string;
  title: string;
  description: string;
  actionTitle: string;
  actionSubtitle: string;
  actionHref: string;
}

const INTENT_OPTIONS: IntentConfig[] = [
  {
    id: "NEED_LAWYER",
    icon: "🔍",
    title: "I need legal help",
    description: "Find and consult a verified advocate for your situation",
    actionTitle: "Browse Verified Advocates",
    actionSubtitle: "Filter by jurisdiction, practice area, and consultation fees",
    actionHref: "/lawyers",
  },
  {
    id: "HAVE_CASE",
    icon: "🏛",
    title: "I have a court case",
    description: "Track hearings, daily orders, and cause lists via eCourts",
    actionTitle: "Track Indian Court Case",
    actionSubtitle: "Search by CNR, case number, or litigant party name",
    actionHref: "/court-tracking",
  },
  {
    id: "RECEIVED_NOTICE",
    icon: "📜",
    title: "I received a legal notice",
    description: "Analyze the notice, understand timelines, and prepare response",
    actionTitle: "Create Notice Matter Record",
    actionSubtitle: "Securely document claims and statutory reply deadlines",
    actionHref: "/cases/new",
  },
  {
    id: "MANAGE_MATTER",
    icon: "📁",
    title: "Manage existing matter",
    description: "Organize litigation files, evidence, and case calendar",
    actionTitle: "Open Evidence & Documents Locker",
    actionSubtitle: "Upload case records with automatic tamper-evident hashes",
    actionHref: "/documents",
  },
];

const PILOT_LOCATIONS = [
  { id: "delhi", name: "Delhi NCR", jurisdiction: "High Court of Delhi" },
  { id: "mumbai", name: "Mumbai / Maharashtra", jurisdiction: "High Court of Bombay" },
  { id: "allahabad", name: "Allahabad / Uttar Pradesh", jurisdiction: "High Court of Allahabad" },
  { id: "other", name: "Other Indian State", jurisdiction: "Nationwide (District Courts expanding)" },
];

export default function ClientOnboardingPage() {
  const router = useRouter();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedIntent, setSelectedIntent] = useState<ClientIntent>("NEED_LAWYER");
  const [location, setLocation] = useState("delhi");
  const [language, setLanguage] = useState("en");
  const [submitting, setSubmitting] = useState(false);

  const activeIntentConfig = INTENT_OPTIONS.find((opt) => opt.id === selectedIntent) || INTENT_OPTIONS[0];

  const handleNextFromIntent = async () => {
    // Record intent telemetry
    try {
      await apiClient.post(
        "/api/v1/pilot/telemetry/event",
        {
          event_type: "INTENT_SELECTED",
          metadata: { intent: selectedIntent },
        },
        { requireAuth: false }
      );
    } catch {
      // Telemetry should never block UX
    }
    setStep(2);
  };

  const handleCompleteOnboarding = async (targetHref: string) => {
    setSubmitting(true);
    try {
      await apiClient.post(
        "/api/v1/pilot/telemetry/event",
        {
          event_type: "CLIENT_ONBOARDING_COMPLETED",
          metadata: {
            intent: selectedIntent,
            location,
            language,
          },
        },
        { requireAuth: false }
      );
    } catch {
      // Best effort telemetry
    }
    router.push(targetHref);
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.badge}>Pilot Onboarding • Ordinary Litigant Journey</div>
          <h1 className={styles.title}>
            {step === 1 && "What brings you to LCC today?"}
            {step === 2 && "Jurisdiction & Preferred Language"}
            {step === 3 && "Your First Legal Action"}
          </h1>
          <p className={styles.subtitle}>
            {step === 1 && "Select what best describes your current legal situation. We will tailor your workspace immediately."}
            {step === 2 && "LCC is currently deployed in a controlled pilot across Delhi, Bombay, and Allahabad jurisdictions."}
            {step === 3 && "You are all set! Jump directly into the exact workflow you need with zero complex setup."}
          </p>
        </div>

        {/* Step Indicator */}
        <div className={styles.stepIndicator}>
          <div className={`${styles.stepDot} ${step >= 1 ? styles.stepDotActive : ""}`} />
          <div className={`${styles.stepDot} ${step >= 2 ? styles.stepDotActive : ""}`} />
          <div className={`${styles.stepDot} ${step >= 3 ? styles.stepDotActive : ""}`} />
        </div>

        {/* STEP 1: Intent Selection */}
        {step === 1 && (
          <div>
            <div className={styles.intentGrid}>
              {INTENT_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setSelectedIntent(opt.id)}
                  className={`${styles.intentOption} ${
                    selectedIntent === opt.id ? styles.intentOptionSelected : ""
                  }`}
                >
                  <span className={styles.intentIcon}>{opt.icon}</span>
                  <span className={styles.intentTitle}>{opt.title}</span>
                  <span className={styles.intentDesc}>{opt.description}</span>
                </button>
              ))}
            </div>

            <div className={styles.actions}>
              <button
                type="button"
                onClick={() => router.push("/dashboard")}
                className={styles.secondaryBtn}
              >
                Skip to Dashboard
              </button>
              <button
                type="button"
                onClick={handleNextFromIntent}
                className={styles.primaryBtn}
              >
                Continue →
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: Location & Language */}
        {step === 2 && (
          <div>
            <div className={styles.jurisdictionNotice}>
              <span>⚖</span>
              <div>
                <strong>Supported Pilot Jurisdictions:</strong> High Court of Delhi, High Court of Bombay, and High Court of Allahabad. District courts expanding in Cohort 2.
              </div>
            </div>

            <div className={styles.formGroup}>
              <label className={styles.label}>Primary Court Jurisdiction or Location</label>
              <select
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                className={styles.select}
              >
                {PILOT_LOCATIONS.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name} ({loc.jurisdiction})
                  </option>
                ))}
              </select>
            </div>

            <div className={styles.formGroup}>
              <label className={styles.label}>Preferred Language</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className={styles.select}
              >
                <option value="en">English</option>
                <option value="hi">हिन्दी (Hindi)</option>
                <option value="mr">मराठी (Marathi)</option>
                <option value="bn">বাংলা (Bengali)</option>
                <option value="ta">தமிழ் (Tamil)</option>
              </select>
            </div>

            <div className={styles.actions}>
              <button
                type="button"
                onClick={() => setStep(1)}
                className={styles.secondaryBtn}
              >
                ← Back
              </button>
              <button
                type="button"
                onClick={() => setStep(3)}
                className={styles.primaryBtn}
              >
                Confirm Preferences →
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: Instant Value Activation */}
        {step === 3 && (
          <div>
            <div style={{ textAlign: "center", marginBottom: "20px" }}>
              <span style={{ fontSize: "40px" }}>✨</span>
              <h2 style={{ fontSize: "18px", color: "#fff", marginTop: "8px", marginBottom: "4px" }}>
                Ready to take action
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                Selected focus: <strong>{activeIntentConfig.title}</strong> in{" "}
                <strong>{PILOT_LOCATIONS.find((l) => l.id === location)?.name}</strong>
              </p>
            </div>

            <div className={styles.activationCards}>
              <button
                type="button"
                onClick={() => handleCompleteOnboarding(activeIntentConfig.actionHref)}
                disabled={submitting}
                className={`${styles.activationCard} ${styles.activationCardPrimary}`}
                style={{ cursor: "pointer", width: "100%", border: "1px solid #3b82f6" }}
              >
                <div style={{ textAlign: "left" }}>
                  <div style={{ fontSize: "15px", fontWeight: 700, color: "#ffffff" }}>
                    🚀 {activeIntentConfig.actionTitle}
                  </div>
                  <div style={{ fontSize: "12px", color: "#93c5fd", marginTop: "2px" }}>
                    {activeIntentConfig.actionSubtitle}
                  </div>
                </div>
                <span style={{ fontSize: "18px", color: "#ffffff" }}>→</span>
              </button>

              <button
                type="button"
                onClick={() => handleCompleteOnboarding("/dashboard")}
                disabled={submitting}
                className={styles.activationCard}
                style={{ cursor: "pointer", width: "100%" }}
              >
                <div style={{ textAlign: "left" }}>
                  <div style={{ fontSize: "14px", fontWeight: 600, color: "#cbd5e1" }}>
                    📊 Go to General Dashboard
                  </div>
                  <div style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>
                    Overview of your matters, calendar, documents, and messages
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
