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
  ChatIcon,
  ClockIcon,
  ScalesIcon,
  SearchIcon,
} from "@/components/ui/Icons";
import { Badge } from "@/components/ui";
import styles from "./page.module.css";

const FAQS = [
  {
    q: "Do I need to understand legal terms or court jargon to use LCC?",
    a: "Not at all. LCC is designed specifically for ordinary people. Every case status, document, and hearing update is presented in calm, plain English with zero confusing legal terminology.",
  },
  {
    q: "Are the lawyers on LCC verified?",
    a: "Yes. Every advocate listed on LCC is verified with their respective State Bar Council. You can view their verified credentials, years of court experience, practice areas, and transparent consultation fees.",
  },
  {
    q: "Is my personal data and case paperwork private?",
    a: "Completely private. All your documents and case messages are protected under India's Digital Personal Data Protection (DPDP) framework. Only you and legal counsel you explicitly authorize can access your records.",
  },
  {
    q: "Can I use LCC if my case has already started in court?",
    a: "Yes. You can add ongoing cases, upload past court orders and notices, keep track of upcoming hearing dates, and invite your current lawyer or connect with a new advocate.",
  },
];

export default function Home() {
  const [securityDetailsOpen, setSecurityDetailsOpen] = useState(false);

  return (
    <div className={styles.page}>
      {/* 1. Hero Section */}
      <section className={styles.hero}>
        <div className="container">
          <div className={styles.heroBrand}>
            <div
              className={styles.heroBrandIcon}
              style={{
                background: "#102A43",
                border: "1px solid rgba(255, 255, 255, 0.18)",
                boxShadow: "0 2px 6px rgba(0, 0, 0, 0.2)",
                overflow: "hidden",
                padding: "3px",
              }}
            >
              <Image
                src="/logo-icon-white.png"
                alt="LCC Logo"
                width={20}
                height={20}
                style={{ objectFit: "contain", width: "100%", height: "100%" }}
                priority
              />
            </div>
            <span className={styles.heroBrandText}>
              LCC · LEGAL CASE COMPANION
            </span>
          </div>

          <h1 className={styles.heroTitle}>Legal matters, made easier.</h1>
          <p className={styles.heroSubtitle}>
            Keep your case, documents, important dates and lawyer communication
            in one simple place.
          </p>

          <div className={styles.heroCtas}>
            <Link
              href="/login"
              className="btn btn-primary"
              style={{
                minHeight: "46px",
                padding: "12px 28px",
                fontSize: "15px",
              }}
            >
              Get Started
            </Link>
            <a
              href="#how-it-works"
              className="btn btn-secondary"
              style={{
                minHeight: "46px",
                padding: "12px 24px",
                fontSize: "15px",
              }}
            >
              How LCC Works
            </a>
          </div>

          {/* Quick Navigation Action Cards */}
          <div className={styles.actionsGrid}>
            {/* 1. My Case */}
            <Link href="/dashboard" className={styles.actionCard}>
              <div className={styles.actionCardIconWrap}>
                <CaseIcon size={24} />
              </div>
              <h2 className={styles.actionCardTitle}>My Case</h2>
              <p className={styles.actionCardDesc}>
                See what is happening with your case, what steps are completed,
                and what needs your attention next.
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
                Store, view, and understand contracts, notices, and court orders
                explained in plain, simple language.
              </p>
              <div className={styles.actionCardFooter}>
                <span>Understand My Documents</span>
                <ArrowRightIcon size={14} />
              </div>
            </Link>

            {/* 3. Important Dates */}
            <Link href="/calendar" className={styles.actionCard}>
              <div className={styles.actionCardIconWrap}>
                <CalendarIcon size={24} />
              </div>
              <h2 className={styles.actionCardTitle}>Important Dates</h2>
              <p className={styles.actionCardDesc}>
                Know exactly when you need to be in court, where to go, and what
                documents to bring beforehand.
              </p>
              <div className={styles.actionCardFooter}>
                <span>See Hearing Dates</span>
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
                Connect with verified Bar Council advocates across District Courts
                and High Courts with clear pricing.
              </p>
              <div className={styles.actionCardFooter}>
                <span>Find an Advocate</span>
                <ArrowRightIcon size={14} />
              </div>
            </Link>
          </div>
        </div>
      </section>

      {/* 2. Trust & Credibility Bar */}
      <section className={styles.trustBar}>
        <div className="container">
          <div className={styles.trustBarInner}>
            <span className={styles.trustItem}>
              <CheckCircleIcon size={16} color="var(--status-safe-text)" />
              Bar Council Verified Advocates
            </span>
            <span>•</span>
            <span className={styles.trustItem}>
              <CheckCircleIcon size={16} color="var(--status-safe-text)" />
              High Court & District Court Coverage
            </span>
            <span>•</span>
            <span className={styles.trustItem}>
              <CheckCircleIcon size={16} color="var(--status-safe-text)" />
              Plain-Language Explanations
            </span>
            <span>•</span>
            <span className={styles.trustItem}>
              <CheckCircleIcon size={16} color="var(--status-safe-text)" />
              Zero Legal Jargon
            </span>
          </div>
        </div>
      </section>

      {/* 3. How LCC Helps (3 Core Pillars) */}
      <section className={styles.section} style={{ background: "var(--surface-card, #FFFFFF)" }}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <div className={styles.sectionEyebrow}>Core Benefits</div>
            <h2 className={styles.sectionTitle}>How LCC Helps You</h2>
            <p className={styles.sectionDesc}>
              LCC brings clarity and structure to what can otherwise feel
              overwhelming and confusing.
            </p>
          </div>

          <div className={styles.pillarGrid}>
            <div className={styles.pillarCard}>
              <div className={styles.pillarIconWrap}>
                <CaseIcon size={24} color="var(--navy-primary)" />
              </div>
              <h3 className={styles.pillarTitle}>Understand your case</h3>
              <p className={styles.pillarDesc}>
                A clear, plain-English timeline tracks exactly what has been
                filed, current status, and what happens next—free of confusing
                court terminology.
              </p>
            </div>

            <div className={styles.pillarCard}>
              <div className={styles.pillarIconWrap}>
                <DocumentIcon size={24} color="var(--navy-primary)" />
              </div>
              <h3 className={styles.pillarTitle}>Keep documents organized</h3>
              <p className={styles.pillarDesc}>
                Store and categorize court filings, evidence, agreements, and
                notices securely. Get key clauses explained in everyday language
                with one tap.
              </p>
            </div>

            <div className={styles.pillarCard}>
              <div className={styles.pillarIconWrap}>
                <ChatIcon size={24} color="var(--navy-primary)" />
              </div>
              <h3 className={styles.pillarTitle}>
                Stay connected with your lawyer
              </h3>
              <p className={styles.pillarDesc}>
                Direct messaging, scheduled video consultations, and transparent
                fee agreements. Stay aligned with your legal counsel without
                chasing phone calls.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 4. How It Works (4 Steps) */}
      <section id="how-it-works" className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <div className={styles.sectionEyebrow}>Simple 4-Step Process</div>
            <h2 className={styles.sectionTitle}>How It Works</h2>
            <p className={styles.sectionDesc}>
              You do not need to understand legal jargon or complex court
              procedures. LCC guides you step by step.
            </p>
          </div>

          <div className={styles.stepsGrid}>
            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>1</div>
              <h3 className={styles.stepTitle}>Tell us about your matter</h3>
              <p className={styles.stepText}>
                Describe your situation in everyday words. We help organize the
                facts and identify the right category for your legal situation.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>2</div>
              <h3 className={styles.stepTitle}>Organize your case</h3>
              <p className={styles.stepText}>
                Upload notices, court papers, or agreements into a private,
                encrypted vault with a simple chronological timeline.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>3</div>
              <h3 className={styles.stepTitle}>Connect with a lawyer</h3>
              <p className={styles.stepText}>
                Find a verified Bar Council advocate who practices in your local
                court with transparent fees and no hidden costs.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>4</div>
              <h3 className={styles.stepTitle}>Stay on top of what happens</h3>
              <p className={styles.stepText}>
                Receive timely reminders before hearings, understand what is
                required from you, and follow every step calmly.
              </p>
            </div>
          </div>

          {/* 5. Privacy & Security Assurance Box */}
          <div id="security" className={styles.securityBox}>
            <div className={styles.securityText}>
              <div className={styles.securityTitle}>
                <ShieldIcon size={20} color="var(--navy-primary)" />
                <span>Your information is private and protected</span>
              </div>
              <p className={styles.securitySubtitle}>
                Only you and advocates explicitly authorized by you can view your
                case details and documents. Compliant with India&apos;s DPDP framework.
              </p>
            </div>

            <div>
              <button
                type="button"
                onClick={() => setSecurityDetailsOpen((prev) => !prev)}
                className="btn btn-secondary"
                style={{ fontSize: "13px", minHeight: "42px" }}
              >
                {securityDetailsOpen
                  ? "Hide security details ▲"
                  : "View security details ▼"}
              </button>
            </div>

            {securityDetailsOpen && (
              <div
                style={{
                  width: "100%",
                  padding: "18px 20px",
                  borderRadius: "var(--radius-md)",
                  background: "var(--surface-subtle)",
                  fontSize: "13px",
                  color: "var(--text-secondary)",
                  lineHeight: "1.6",
                }}
              >
                <div
                  style={{
                    fontWeight: 700,
                    color: "var(--navy-primary)",
                    marginBottom: "6px",
                  }}
                >
                  Security & Data Privacy Commitments:
                </div>
                <div>
                  • Full privacy compliance under the Digital Personal Data
                  Protection (DPDP) Act.
                </div>
                <div>
                  • Private, encrypted document storage with tamper-evident audit
                  trails.
                </div>
                <div>
                  • Strict access controls: no advocate or third party can access
                  your case without your explicit invitation.
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 6. For Citizens & For Lawyers */}
      <section className={styles.section} style={{ background: "var(--surface-subtle)" }}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <div className={styles.sectionEyebrow}>Tailored Experience</div>
            <h2 className={styles.sectionTitle}>
              Designed for Both Citizens and Lawyers
            </h2>
            <p className={styles.sectionDesc}>
              A shared, dignified platform that bridges the communication gap
              between clients and legal professionals.
            </p>
          </div>

          <div className={styles.audienceGrid}>
            {/* For Citizens */}
            <div className={styles.audienceCard}>
              <div>
                <Badge variant="primary" size="sm">
                  For Citizens
                </Badge>
                <h3 className={styles.audienceTitle}>
                  Clarity and peace of mind
                </h3>
                <p className={styles.audienceDesc}>
                  Manage your legal matter without feeling lost or intimidated.
                  Know what is happening, what your lawyer is doing, and when you
                  need to take action.
                </p>
                <ul className={styles.audienceList}>
                  <li className={styles.audienceItem}>
                    <CheckCircleIcon size={16} color="var(--status-safe-text)" />
                    <span>Plain-English case updates and next steps</span>
                  </li>
                  <li className={styles.audienceItem}>
                    <CheckCircleIcon size={16} color="var(--status-safe-text)" />
                    <span>Verified advocate directory with transparent fees</span>
                  </li>
                  <li className={styles.audienceItem}>
                    <CheckCircleIcon size={16} color="var(--status-safe-text)" />
                    <span>Clear court hearing alerts & document checklists</span>
                  </li>
                  <li className={styles.audienceItem}>
                    <CheckCircleIcon size={16} color="var(--status-safe-text)" />
                    <span>Private, confidential document vault</span>
                  </li>
                </ul>
              </div>
              <Link
                href="/dashboard"
                className="btn btn-primary"
                style={{
                  minHeight: "44px",
                  fontSize: "14px",
                  textAlign: "center",
                }}
              >
                Go to Citizen Workspace
              </Link>
            </div>

            {/* For Lawyers */}
            <div className={styles.audienceCard}>
              <div>
                <Badge variant="default" size="sm">
                  For Advocates
                </Badge>
                <h3 className={styles.audienceTitle}>
                  A professional practice workspace
                </h3>
                <p className={styles.audienceDesc}>
                  Manage case matters, share updates with clients seamlessly, and
                  conduct live video consultations with zero administrative friction.
                </p>
                <ul className={styles.audienceList}>
                  <li className={styles.audienceItem}>
                    <CheckCircleIcon size={16} color="var(--navy-600)" />
                    <span>Centralized matter inbox & client record tracking</span>
                  </li>
                  <li className={styles.audienceItem}>
                    <CheckCircleIcon size={16} color="var(--navy-600)" />
                    <span>Structured document sharing & order logs</span>
                  </li>
                  <li className={styles.audienceItem}>
                    <CheckCircleIcon size={16} color="var(--navy-600)" />
                    <span>Secure live video consultation room integration</span>
                  </li>
                  <li className={styles.audienceItem}>
                    <CheckCircleIcon size={16} color="var(--navy-600)" />
                    <span>Direct, confidential client messaging</span>
                  </li>
                </ul>
              </div>
              <Link
                href="/register?role=lawyer"
                className="btn btn-secondary"
                style={{
                  minHeight: "44px",
                  fontSize: "14px",
                  textAlign: "center",
                }}
              >
                Register as an Advocate
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 7. Frequently Asked Questions */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <div className={styles.sectionEyebrow}>Common Questions</div>
            <h2 className={styles.sectionTitle}>Frequently Asked Questions</h2>
            <p className={styles.sectionDesc}>
              Everything you need to know about getting started with LCC.
            </p>
          </div>

          <div className={styles.faqGrid}>
            {FAQS.map((faq, idx) => (
              <div key={idx} className={styles.faqCard}>
                <h3 className={styles.faqQuestion}>{faq.q}</h3>
                <p className={styles.faqAnswer}>{faq.a}</p>
              </div>
            ))}
          </div>

          {/* 8. Final Call to Action */}
          <div className={styles.ctaBanner}>
            <h2 className={styles.ctaTitle}>
              Ready to organize your legal matter?
            </h2>
            <p className={styles.ctaSubtitle}>
              Experience a calmer, clearer way to handle legal affairs. No credit
              card required to start.
            </p>
            <div className={styles.ctaActions}>
              <Link
                href="/login"
                className={styles.ctaPrimaryBtn}
              >
                Get Started Today
              </Link>
              <Link
                href="/lawyers"
                className={styles.ctaSecondaryBtn}
              >
                Find an Advocate
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 9. Clean Legal Footer */}
      <footer className={styles.footer}>
        <div className="container">
          <p>
            © {new Date().getFullYear()} Legal Case Companion (LCC). Plain-language
            legal assistance for everyday people.
          </p>
        </div>
      </footer>
    </div>
  );
}
