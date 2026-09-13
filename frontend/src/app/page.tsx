"use client";

import React, { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  CaseIcon,
  DocumentIcon,
  CalendarIcon,
  LawyerIcon,
  ShieldIcon,
  CheckCircleIcon,
  ArrowRightIcon,
} from "@/components/ui/Icons";
import styles from "./page.module.css";

export default function Home() {
  const [securityDetailsOpen, setSecurityDetailsOpen] = useState(false);

  return (
    <div className={styles.page}>
      {/* Hero Section: One Screen = One Clear Purpose */}
      <section className={styles.hero}>
        <div className="container">
          <div className={styles.heroBrand}>
            <div className={styles.heroBrandIcon} style={{ background: "var(--navy-primary)", overflow: "hidden", padding: "2px" }}>
              <Image
                src="/logo-icon-white.png"
                alt="LCC Logo"
                width={32}
                height={32}
                style={{ objectFit: "contain", width: "auto", height: "auto" }}
                priority
              />
            </div>
            <span className={styles.heroBrandText}>LCC · LEGAL CASE COMPANION</span>
          </div>

          <h1 className={styles.heroTitle}>Legal help, made simple.</h1>
          <p className={styles.heroSubtitle}>
            What do you need help with? Choose an option below to get started.
          </p>

          {/* 4 Clear Action Cards (Section 5) */}
          <div className={styles.actionsGrid}>
            {/* 1. My Case */}
            <Link href="/dashboard" className={styles.actionCard}>
              <div className={styles.actionCardIconWrap}>
                <CaseIcon size={24} />
              </div>
              <h2 className={styles.actionCardTitle}>My Case</h2>
              <p className={styles.actionCardDesc}>
                See what is happening with your case, what steps are completed, and what needs your attention next.
              </p>
              <div className={styles.actionCardFooter}>
                <span>View My Case</span>
                <ArrowRightIcon size={14} />
              </div>
            </Link>

            {/* 2. My Documents */}
            <Link href="/documents" className={styles.actionCard}>
              <div className={styles.actionCardIconWrap}>
                <DocumentIcon size={24} />
              </div>
              <h2 className={styles.actionCardTitle}>My Documents</h2>
              <p className={styles.actionCardDesc}>
                Store, view, and understand contracts, notices, and court orders explained in plain, simple language.
              </p>
              <div className={styles.actionCardFooter}>
                <span>Understand My Documents</span>
                <ArrowRightIcon size={14} />
              </div>
            </Link>

            {/* 3. My Hearing */}
            <Link href="/calendar" className={styles.actionCard}>
              <div className={styles.actionCardIconWrap}>
                <CalendarIcon size={24} />
              </div>
              <h2 className={styles.actionCardTitle}>My Hearing</h2>
              <p className={styles.actionCardDesc}>
                Know exactly when you need to be in court, where to go, and what documents to bring beforehand.
              </p>
              <div className={styles.actionCardFooter}>
                <span>See Hearing Details</span>
                <ArrowRightIcon size={14} />
              </div>
            </Link>

            {/* 4. Find a Lawyer */}
            <Link href="/lawyers" className={styles.actionCard}>
              <div className={styles.actionCardIconWrap}>
                <LawyerIcon size={24} />
              </div>
              <h2 className={styles.actionCardTitle}>Find a Lawyer</h2>
              <p className={styles.actionCardDesc}>
                Connect with verified Bar Council advocates across District Courts and High Courts with clear pricing.
              </p>
              <div className={styles.actionCardFooter}>
                <span>Find a Lawyer</span>
                <ArrowRightIcon size={14} />
              </div>
            </Link>
          </div>

          {/* Quick Demo Access Bar */}
          <div style={{ marginTop: "32px", display: "flex", justifyContent: "center", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>Trying LCC for the first time?</span>
            <Link
              id="demo-client-btn"
              href="/login"
              className="btn btn-secondary"
              style={{ padding: "6px 14px", fontSize: "12px" }}
            >
              Sign In or Try Demo Account →
            </Link>
          </div>
        </div>
      </section>

      {/* Trust & Credibility Bar */}
      <section className={styles.trustBar}>
        <div className="container">
          <div className={styles.trustBarInner}>
            <span className={styles.trustItem}>
              <CheckCircleIcon size={16} color="var(--status-success)" />
              Bar Council Verified Advocates
            </span>
            <span>•</span>
            <span className={styles.trustItem}>
              <CheckCircleIcon size={16} color="var(--status-success)" />
              High Court & District Court Coverage
            </span>
            <span>•</span>
            <span className={styles.trustItem}>
              <CheckCircleIcon size={16} color="var(--status-success)" />
              Plain-Language Legal Explanations
            </span>
            <span>•</span>
            <span className={styles.trustItem}>
              <CheckCircleIcon size={16} color="var(--status-success)" />
              Zero Jargon
            </span>
          </div>
        </div>
      </section>

      {/* How LCC Works */}
      <section id="how-it-works" className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <div className={styles.sectionEyebrow}>Simple 3-Step Process</div>
            <h2 className={styles.sectionTitle}>How LCC Helps You</h2>
            <p className={styles.sectionDesc}>
              You do not need to understand legal jargon or complex court procedures. LCC guides you step by step.
            </p>
          </div>

          <div className={styles.stepsGrid}>
            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>1</div>
              <h3 className={styles.stepTitle}>Tell Us What Happened</h3>
              <p className={styles.stepText}>
                Describe your situation in everyday words. We help categorize your case and organize your information clearly.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>2</div>
              <h3 className={styles.stepTitle}>Connect with Verified Counsel</h3>
              <p className={styles.stepText}>
                Consult a verified advocate who practices in your local court. Transparent pricing and no hidden costs.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>3</div>
              <h3 className={styles.stepTitle}>Stay Informed at Every Step</h3>
              <p className={styles.stepText}>
                Get timely reminders before every hearing, know what documents to carry, and receive simple case updates.
              </p>
            </div>
          </div>

          {/* Privacy & Security Box (Section 13) */}
          <div id="security" className={styles.securityBox}>
            <div className={styles.securityText}>
              <div className={styles.securityTitle}>
                <ShieldIcon size={20} color="var(--navy-primary)" />
                <span>Your information is protected</span>
              </div>
              <p className={styles.securitySubtitle}>
                Only you and advocates authorized by you can view your case details and documents. Your private files are protected with bank-grade safety.
              </p>
            </div>

            <div>
              <button
                type="button"
                onClick={() => setSecurityDetailsOpen((prev) => !prev)}
                className="btn btn-secondary"
                style={{ fontSize: "13px" }}
              >
                {securityDetailsOpen ? "Hide security details ▲" : "View security details ▼"}
              </button>
            </div>

            {securityDetailsOpen && (
              <div
                style={{
                  width: "100%",
                  padding: "16px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--surface-subtle)",
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  lineHeight: "1.6",
                }}
              >
                <div style={{ fontWeight: 600, color: "var(--navy-primary)", marginBottom: "4px" }}>
                  Security & Data Privacy Commitments:
                </div>
                <div>• Complete privacy compliance under the Digital Personal Data Protection (DPDP) framework.</div>
                <div>• Private document storage with malware scanning and tamper verification.</div>
                <div>• Object-level access control ensuring only assigned participants can view case records.</div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Clean Legal Footer */}
      <footer className={styles.footer}>
        <div className="container">
          <p>© {new Date().getFullYear()} Legal Case Companion (LCC). Plain-language legal assistance for everyday people.</p>
        </div>
      </footer>
    </div>
  );
}
