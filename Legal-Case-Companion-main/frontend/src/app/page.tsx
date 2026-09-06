"use client";

import { useState } from "react";
import Link from "next/link";
import LegalTerm from "@/components/LegalTerm";
import styles from "./page.module.css";

const intentCards = [
  {
    icon: "📬",
    badge: "Urgent Response",
    title: "Received a legal notice?",
    desc: "Understand your response deadline, organize required proof, and consult a verified advocate before statutory limitation expires.",
    action: "Respond to Notice",
    href: "/cases/new?intent=notice",
  },
  {
    icon: "🏛",
    badge: "eCourts Sync",
    title: "I have a court case",
    desc: "Track case status, daily cause lists, order sheets, and upcoming hearings across High Courts and District Courts with your CNR number.",
    action: "Track Court Case",
    href: "/court-tracking",
  },
  {
    icon: "🤝",
    badge: "Guided Intake",
    title: "I need legal help",
    desc: "Tell us what happened in plain, simple everyday words. We will categorize your matter and prepare your structured case file.",
    action: "Start Free Intake",
    href: "/cases/new",
  },
  {
    icon: "📅",
    badge: "Limitation & Dates",
    title: "I want to check my hearing",
    desc: "Find out precisely when you need to be in court, which courtroom and bench is assigned, and what documents you must bring.",
    action: "Check Hearings",
    href: "/calendar",
  },
  {
    icon: "📁",
    badge: "Private Vault",
    title: "I need help with documents",
    desc: "Securely store, organize, and verify property deeds, contracts, police complaints, and notices with cryptographic SHA-256 integrity.",
    action: "Open Document Vault",
    href: "/documents",
  },
  {
    icon: "⚖",
    badge: "Verified Counsel",
    title: "I want to talk to a lawyer",
    desc: "Consult Bar Council verified advocates across High Courts and District Courts with transparent, itemized GST pricing.",
    action: "Find an Advocate",
    href: "/lawyers",
  },
];

const personas = [
  {
    id: "clients",
    label: "Individual Litigants & Citizens",
    icon: "👤",
    headline: "Clarity, security, and verified legal representation in plain language.",
    points: [
      "Plain-language explanations of every court status, order, and procedural step without legal jargon.",
      "Direct discovery of Bar Council verified advocates tailored to your jurisdiction and budget.",
      "Encrypted private document locker with mobile camera scan and cryptographic tamper detection.",
      "Clear, actionable notifications: know exactly when your next hearing is and what you need to bring.",
    ],
    metric: "100% Plain Language Transparency",
  },
  {
    id: "litigators",
    label: "Advocates & Litigation Chambers",
    icon: "⚖",
    headline: "Run high-stakes litigation with instant access to the entire matter record.",
    points: [
      "Track court listings across Supreme Court, High Courts, District Courts, and NCLT in one place.",
      "Statutory Limitation Act radar with automated countdowns for appeals, revisions, and filings.",
      "Organize case files, pleadings, vakalatnamas, and exhibits with zero-leakage security.",
      "Conduct encrypted video consultations with in-meeting exhibit presentation and time records.",
    ],
    metric: "Zero Missed Limitation Deadlines",
  },
  {
    id: "inhouse",
    label: "Corporate Legal & Law Firms",
    icon: "🏢",
    headline: "Dispute portfolio governance, counsel management, and compliance audit.",
    points: [
      "Centralized portfolio oversight for commercial suits, arbitrations, and statutory compliance.",
      "Tamper-evident audit trails and role-based permissions for legal teams and partners.",
      "GST-compliant billing, retainers, and transparent dispute cost tracking with itemized breakdowns.",
      "Secure client collaboration with granular document permissions and custody logs.",
    ],
    metric: "Verifiable Chain of Custody",
  },
];

const features = [
  {
    icon: "📖",
    eyebrow: "PLAIN-LANGUAGE SYSTEM",
    title: "3-Layer Legal Translation",
    desc: "Every procedural status is explained in human language, accompanied by precise legal terminology and verifiable court provenance.",
  },
  {
    icon: "🏛",
    eyebrow: "ECOURTS & CAUSE LISTS",
    title: "Live Court Synchronization",
    desc: "Track case status by CNR, filing number, or party name with real-time updates from official High Court and District Court registries.",
  },
  {
    icon: "🛡",
    eyebrow: "PRIVATE EVIDENCE VAULT",
    title: "Cryptographic Document Security",
    desc: "Private document architecture with magic-byte file validation, SHA-256 cryptographic verification, and malware quarantine.",
  },
  {
    icon: "⏱",
    eyebrow: "STATUTORY GOVERNANCE",
    title: "Limitation Act Radar",
    desc: "Automated calculations for statutory limitation periods, appeal windows, and court vacation extensions to safeguard every claim.",
  },
  {
    icon: "⚖",
    eyebrow: "COUNSEL NETWORK",
    title: "Verified Advocate Roster",
    desc: "Direct access to Bar Council verified advocates across High Courts, NCLT, and Supreme Court with transparent GST pricing.",
  },
  {
    icon: "📋",
    eyebrow: "ENTERPRISE AUDIT",
    title: "Tamper-Evident Ledger",
    desc: "Append-only system logs, strict role segregation, and immutable custody records built for professional evidentiary scrutiny.",
  },
];

export default function Home() {
  const [activePersona, setActivePersona] = useState(0);

  return (
    <div className={styles.page}>
      {/* Hero Section */}
      <section className={styles.hero}>
        <div className={styles.heroGlow} aria-hidden="true" />
        <div className={styles.heroGlowSecondary} aria-hidden="true" />
        <div className={styles.heroGrid} aria-hidden="true" />

        <div className={styles.heroInner}>
          <div className={styles.eyebrow}>
            <span className="pulse-dot" style={{ background: "#10b981", boxShadow: "0 0 10px #10b981" }} />
            <span>Human-Centered Legal Platform · Built for Indian Citizens & Advocates</span>
          </div>

          <h1 className={styles.heroTitle}>
            Legal help shouldn&apos;t be<br />
            <span className="text-gradient">difficult to understand.</span>
          </h1>

          <p className={styles.heroLead}>
            Manage your case, documents, lawyer, hearings and important updates in one secure place.
          </p>

          <div className={styles.actions}>
            <Link className={styles.primaryCta} href="/lawyers">
              Find a Lawyer <b>→</b>
            </Link>
            <Link className={styles.secondaryCta} href="/dashboard">
              Manage My Case
            </Link>
            <Link className={styles.tertiaryCta} href="/login">
              Sign In
            </Link>
            <Link
              className={styles.tertiaryCta}
              id="demo-client-btn"
              href="/login"
              style={{ fontSize: "13px", color: "var(--accent-secondary)" }}
            >
              Demo Accounts →
            </Link>
          </div>

          <div className={styles.trustRow}>
            <span>Trusted across:</span>
            <b>Supreme Court of India</b>
            <i>·</i>
            <b>Delhi High Court</b>
            <i>·</i>
            <b>Bombay High Court</b>
            <i>·</i>
            <b>District Courts</b>
            <i>·</i>
            <b>NCLT & NCLAT</b>
            <i>·</i>
            <b>Commercial Arbitration</b>
          </div>

          {/* Interactive Product Frame: Attention Center & 3-Layer Legal Experience */}
          <div className={styles.productFrame}>
            <div className={styles.browserBar}>
              <div className={styles.browserDots}>
                <span style={{ background: "#ef4444" }} />
                <span style={{ background: "#f59e0b" }} />
                <span style={{ background: "#10b981" }} />
              </div>
              <div className={styles.browserAddress}>
                <span style={{ color: "#10b981", marginRight: "6px" }}>🔒</span>
                app.legalcasecompanion.com/dashboard
              </div>
              <div className={styles.browserStatus}>
                <span className="pulse-dot" style={{ background: "#6366f1", marginRight: "6px" }} />
                AWS Mumbai (ap-south-1) · TLS 1.3
              </div>
            </div>

            <div className={styles.productBody}>
              <aside className={styles.sidebar}>
                <div className={styles.brandMark}>⚖</div>
                <div className={styles.sidebarTitle}>Navigation</div>
                {[
                  ["▦", "Overview", true],
                  ["🏛", "Court Tracking", false],
                  ["📅", "Hearing Calendar", false],
                  ["📁", "Document Vault", false],
                  ["👥", "Find a Lawyer", false],
                  ["💬", "Messages", false],
                ].map(([icon, label, active]) => (
                  <div
                    key={label as string}
                    className={`${styles.sideItem} ${active ? styles.sideItemActive : ""}`}
                  >
                    <span>{icon as string}</span>
                    {label as string}
                  </div>
                ))}

                <div style={{ marginTop: "auto", padding: "12px 10px", borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                  <div style={{ fontSize: "10px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Connected Bench</div>
                  <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 600, marginTop: "2px" }}>Delhi High Court</div>
                </div>
              </aside>

              <div className={styles.dashboardMock}>
                {/* Litigant Attention Center Banner */}
                <div className={styles.mockAttentionBanner}>
                  <div className={styles.mockAttentionHeader}>
                    <div className={styles.mockAttentionTitle}>
                      <span>⚡</span> Action Center: You have 2 things to take care of
                    </div>
                    <span style={{ fontSize: "11px", color: "#fbbf24", fontWeight: 600 }}>Needs Attention</span>
                  </div>

                  <div className={styles.mockAttentionItems}>
                    <div className={styles.mockAttentionRow}>
                      <div className={styles.mockAttentionText}>
                        <strong>Your hearing is tomorrow at 10:30 AM</strong>
                        <span>Delhi High Court · Court Room 4, Item 12 · Please carry your original property conveyance deed.</span>
                      </div>
                      <Link href="/calendar" className={styles.mockAttentionAction}>
                        View Hearing →
                      </Link>
                    </div>

                    <div className={styles.mockAttentionRow}>
                      <div className={styles.mockAttentionText}>
                        <strong>Your advocate requested 2 documents</strong>
                        <span>Proof of Possession & Recent Electricity Bill required for the supplementary affidavit.</span>
                      </div>
                      <Link href="/documents" className={styles.mockAttentionAction}>
                        Upload Documents →
                      </Link>
                    </div>
                  </div>
                </div>

                <div className={styles.mockTopline}>
                  <div>
                    <div className={styles.mockKicker}>MY ACTIVE MATTERS</div>
                    <h2>Case Overview & Status</h2>
                    <p>Track court updates, hearing dates, and counsel instructions in plain language.</p>
                  </div>
                  <Link href="/cases/new" className={styles.mockBtn}>
                    + Add New Case
                  </Link>
                </div>

                <div className={styles.metricGrid}>
                  {[
                    ["Active Matters", "02", "Up to date", "#6366f1"],
                    ["Next Hearing", "Tomorrow", "10:30 AM · Court 4", "#ef4444"],
                    ["Stored Documents", "12 Docs", "100% SHA-256 Verified", "#10b981"],
                    ["Advocate Assigned", "Adv. Ananya Roy", "Bar Council Verified", "#818cf8"],
                  ].map(([label, value, note, color]) => (
                    <div className={styles.metricCard} key={label}>
                      <span>{label}</span>
                      <strong style={{ color }}>{value}</strong>
                      <small>{note}</small>
                    </div>
                  ))}
                </div>

                <div className={styles.mockColumns}>
                  {/* Left Column: Active Cases with 3-Layer Legal Meaning */}
                  <div className={styles.mockPanel}>
                    <div className={styles.panelHeading}>
                      <b>Cases & Plain-Language Status</b>
                      <span style={{ color: "var(--accent-secondary)", fontSize: "11px" }}>
                        Click any term to learn what it means
                      </span>
                    </div>

                    {/* Case 1 */}
                    <div className={styles.caseRow}>
                      <div className={styles.caseAvatar}>SE</div>
                      <div className={styles.caseInfo}>
                        <strong>Sharma Estates v. Mehta Trading Corp</strong>
                        <span className={styles.caseForum}>Delhi High Court · CS(COMM) 412/2025</span>
                        <div style={{ marginTop: "4px" }}>
                          <LegalTerm term="Judgment Reserved" showBadge={true} />
                        </div>
                        <span className={styles.provenanceTag}>
                          🔒 Source: Court Record (eCourts) · Last synced: Today, 10:30 AM IST
                        </span>
                      </div>
                      <div className={`${styles.statusBadge} ${styles.info}`}>
                        Hearing Tomorrow
                      </div>
                    </div>

                    {/* Case 2 */}
                    <div className={styles.caseRow}>
                      <div className={styles.caseAvatar}>AI</div>
                      <div className={styles.caseInfo}>
                        <strong>Apex Infrastructure v. Union of India</strong>
                        <span className={styles.caseForum}>Commercial Division · OMP(I)(COMM) 88/2026</span>
                        <div style={{ marginTop: "4px" }}>
                          <LegalTerm term="Admission & Denial" showBadge={true} />
                        </div>
                        <span className={styles.provenanceTag}>
                          🔒 Source: Advocate Chamber Filing · Verified
                        </span>
                      </div>
                      <div className={`${styles.statusBadge} ${styles.safe}`}>
                        Pleadings Complete
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Three-Layer Information Architecture Callout */}
                  <div className={styles.mockPanel}>
                    <div className={styles.panelHeading}>
                      <b>3-Layer Legal Clarity Model</b>
                      <span className={styles.liveBadge}>● Always Transparent</span>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                      <div style={{ background: "rgba(99, 102, 241, 0.08)", borderLeft: "3px solid #6366f1", padding: "10px 12px", borderRadius: "0 8px 8px 0" }}>
                        <div style={{ fontSize: "10px", fontWeight: 700, color: "#818cf8", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                          Layer 1: Human Explanation
                        </div>
                        <div style={{ fontSize: "13px", color: "#f1f5f9", marginTop: "2px", fontWeight: 500 }}>
                          &ldquo;Your case is waiting for the court&apos;s decision.&rdquo;
                        </div>
                        <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>
                          Clear, plain everyday words so you always know what is happening.
                        </div>
                      </div>

                      <div style={{ background: "rgba(15, 23, 42, 0.8)", borderLeft: "3px solid #64748b", padding: "10px 12px", borderRadius: "0 8px 8px 0" }}>
                        <div style={{ fontSize: "10px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                          Layer 2: Technical Legal Detail
                        </div>
                        <div style={{ fontSize: "12px", color: "#cbd5e1", marginTop: "2px", fontFamily: "var(--font-mono, monospace)" }}>
                          Technical status: Judgment Reserved (Order XX CPC)
                        </div>
                        <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                          Exact procedural terminology preserved for advocates and court records.
                        </div>
                      </div>

                      <div style={{ background: "rgba(16, 185, 129, 0.08)", borderLeft: "3px solid #10b981", padding: "10px 12px", borderRadius: "0 8px 8px 0" }}>
                        <div style={{ fontSize: "10px", fontWeight: 700, color: "#34d399", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                          Layer 3: Verifiable Provenance
                        </div>
                        <div style={{ fontSize: "11px", color: "#a7f3d0", marginTop: "2px" }}>
                          Source: Official Court Record · Last synchronized: Today 10:30 AM
                        </div>
                        <div style={{ fontSize: "10px", color: "#6ee7b7", marginTop: "1px" }}>
                          Clear distinction between Court records, Advocate inputs, and Client data.
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* "How can we help you today?" Intent-First Section */}
      <section className={styles.intentSection}>
        <div className="container">
          <div className={styles.intentIntro}>
            <div className={styles.sectionEyebrow}>START HERE</div>
            <h2>How can we help you today?</h2>
            <p>
              Select what you are facing right now. We guide you step by step with zero legal jargon and complete transparency.
            </p>
          </div>

          <div className={styles.intentGrid}>
            {intentCards.map((card) => (
              <Link key={card.title} href={card.href} className={styles.intentCard}>
                <div className={styles.intentCardHeader}>
                  <div className={styles.intentIconBox}>{card.icon}</div>
                  <span className={styles.intentBadge}>{card.badge}</span>
                </div>
                <h3>{card.title}</h3>
                <p>{card.desc}</p>
                <div className={styles.intentCardFooter}>
                  <span>{card.action}</span>
                  <span className={styles.intentArrow}>→</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Role-Based Interactive Persona Section */}
      <section className={styles.personaSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <div className={styles.sectionEyebrow}>TAILORED FOR INDIA</div>
            <h2>Engineered for every participant in the justice system.</h2>
            <p>Select your role to see how Legal Case Companion simplifies and accelerates your legal experience.</p>
          </div>

          <div className={styles.personaTabs}>
            {personas.map((p, idx) => (
              <button
                key={p.id}
                onClick={() => setActivePersona(idx)}
                className={`${styles.personaTabBtn} ${activePersona === idx ? styles.personaTabActive : ""}`}
              >
                <span>{p.icon}</span>
                {p.label}
              </button>
            ))}
          </div>

          <div className={styles.personaCard}>
            <div className={styles.personaContent}>
              <div className={styles.personaHeadlineTag}>{personas[activePersona].label}</div>
              <h3>{personas[activePersona].headline}</h3>
              <ul className={styles.personaList}>
                {personas[activePersona].points.map((pt) => (
                  <li key={pt}>
                    <span className={styles.checkIcon}>✓</span>
                    <span>{pt}</span>
                  </li>
                ))}
              </ul>
              <div className={styles.personaCtaRow}>
                <Link className={styles.primaryCta} href="/register">
                  Launch {personas[activePersona].label} Workspace <b>→</b>
                </Link>
                <div className={styles.personaMetricBadge}>
                  ⚡ {personas[activePersona].metric}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Core Platform Capabilities Grid */}
      <section className={styles.featuresSection} id="features">
        <div className="container">
          <div className={styles.sectionIntro}>
            <div>
              <div className={styles.sectionEyebrow}>THE PLATFORM ARCHITECTURE</div>
              <h2>Professional infrastructure underneath.<br />Simple human experience on top.</h2>
            </div>
            <p>
              Legal matters demand tamper-evident records, strict statutory adherence, and absolute data privacy. LCC delivers enterprise-grade legal engineering with an approachable, compassionate interface.
            </p>
          </div>

          <div className={styles.featureGrid}>
            {features.map((f) => (
              <article className={styles.featureCard} key={f.title}>
                <div className={styles.featureIcon}>{f.icon}</div>
                <div className={styles.featureEyebrow}>{f.eyebrow}</div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
                <div className={styles.featureArrow}>↗</div>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Workflow: From Issue to Resolution */}
      <section className={styles.workflowSection}>
        <div className="container">
          <div className={styles.workflowGrid}>
            <div className={styles.workflowCopy}>
              <div className={styles.sectionEyebrow}>STRUCTURED LITIGATION TIMELINE</div>
              <h2>A clear, transparent path through every stage.</h2>
              <p>
                From initial legal notice to final decree execution, keep every fact, hearing date, document, and lawyer instruction synchronized in one trustworthy place.
              </p>
              <Link className={styles.primaryCta} href="/register">
                Start Your Case File <b>→</b>
              </Link>
            </div>

            <div className={styles.timeline}>
              {[
                ["01", "Plain-Language Intake", "Describe what happened in everyday language. LCC structures your facts, parties, and dates into an organized matter file."],
                ["02", "Cryptographic Evidence Storage", "Upload notices, deeds, and agreements with SHA-256 cryptographic verification, magic-byte inspection, and zero data leakage."],
                ["03", "Statutory Limitation Tracking", "Automated calculations for limitation cutoffs, appeal filing windows, and court vacation extensions under Indian procedural codes."],
                ["04", "Verified Counsel Collaboration", "Connect with Bar Council verified advocates, attend secure video consultations, and track daily court hearing lists in real time."],
              ].map(([step, title, text]) => (
                <div className={styles.timelineRow} key={step}>
                  <div className={styles.timelineNumber}>{step}</div>
                  <div className={styles.timelineContent}>
                    <h3>{title}</h3>
                    <p>{text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Security, Data Residency & Trust Section */}
      <section className={styles.securitySection} id="security">
        <div className="container">
          <div className={styles.securityCard}>
            <div>
              <div className={styles.sectionEyebrow}>SOVEREIGNTY & COMPLIANCE</div>
              <h2>Engineered for legal confidentiality.<br />Hosted securely in India.</h2>
              <p>
                Legal confidentiality is non-negotiable. LCC strictly enforces Indian data localization, end-to-end cryptographic integrity, and compliance with the Bar Council of India standards.
              </p>
            </div>

            <div className={styles.securityList}>
              {[
                "Data stored exclusively in AWS Asia Pacific (Mumbai) ap-south-1",
                "Strict alignment with Digital Personal Data Protection (DPDP) Act 2023 principles",
                "TLS 1.3 encrypted transport & AES-256 GCM storage encryption",
                "ClamAV multi-layer malware scanning on all uploaded court records",
                "Tamper-evident append-only audit trail for all user and case events",
                "Bar Council of India compliant communication & dispute safeguards",
              ].map((item) => (
                <div className={styles.securityItem} key={item}>
                  <span className={styles.checkIcon}>✓</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Final Call to Action */}
      <section className={styles.finalCta}>
        <div className={styles.finalGlow} aria-hidden="true" />
        <div className="container" style={{ position: "relative", zIndex: 2 }}>
          <div className={styles.sectionEyebrow}>JOIN CITIZENS, ADVOCATES & IN-HOUSE COUNSEL</div>
          <h2>Bring clarity and control to your legal matters.</h2>
          <p>Start today. Track hearings, store evidence safely, and consult verified advocates with complete peace of mind.</p>
          <div className={styles.actions} style={{ justifyContent: "center" }}>
            <Link className={styles.primaryCta} href="/cases/new">
              Start Free Case Intake <b>→</b>
            </Link>
            <Link className={styles.secondaryCta} href="/lawyers">
              Find a Verified Lawyer
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className={styles.footer}>
        <div className="container">
          <div className={styles.footerInner}>
            <div className={styles.footerBrand}>
              <div className={styles.footerLogo}>⚖</div>
              <div>
                <strong>Legal Case Companion</strong>
                <span>Human-centered Indian legal SaaS platform</span>
              </div>
            </div>

            <div className={styles.footerLinks}>
              <Link href="/court-tracking">Court Tracking</Link>
              <Link href="/calendar">Hearing Calendar</Link>
              <Link href="/lawyers">Advocate Directory</Link>
              <Link href="/documents">Document Vault</Link>
              <Link href="/#features">Features</Link>
              <Link href="/#security">Security & DPDP</Link>
              <Link href="/login">Sign In</Link>
              <Link href="/register">Create Account</Link>
            </div>

            <div className={styles.footerMeta}>
              © 2026 Legal Case Companion. Professional infrastructure underneath. Simple human experience on top.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
