"use client";

import React from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell/AppShell";
import styles from "./trust.module.css";

const TRUST_PILLARS = [
  {
    icon: "⚖️",
    title: "1. Advocate Verification",
    description:
      "Every practicing advocate on Legal Case Companion undergoes statutory verification with their respective State Bar Council (e.g. Bar Council of Delhi, Bar Council of Maharashtra & Goa). Enrollment numbers are confirmed and certificates validated before consultation slots go live.",
    badges: ["Bar Council Verified", "No Fake Profiles", "Manual KYC Check"],
  },
  {
    icon: "🔒",
    title: "2. Secure Document Storage",
    description:
      "Litigation evidence and pleadings are stored in an encrypted vault with AES-256 encryption at rest and TLS 1.3 in transit. Every uploaded document is automatically scanned for malware and virus signatures before entry.",
    badges: ["AES-256 Encryption", "ClamAV Scanned", "Strict Zero AI Training"],
  },
  {
    icon: "💬",
    title: "3. Private Counsel Communication",
    description:
      "Communications between litigants and advocates operate under strict zero-trust tenant isolation. Attorney-client privileged conversations are protected, and support operators cannot view case contents without explicit legal authorization.",
    badges: ["Privilege Protected", "Tenant Isolated", "Zero Operator Snooping"],
  },
  {
    icon: "💳",
    title: "4. Transparent Payments & Refund Guarantee",
    description:
      "All consultation bookings are processed via PCI-DSS Level 1 compliant gateways (Stripe / Razorpay). No hidden fees or surprise charges. If an advocate fails to attend or cancels, a 100% deterministic refund is issued without dispute delays.",
    badges: ["PCI-DSS Level 1", "GST SAC 9982 Invoices", "Deterministic Refunds"],
  },
  {
    icon: "🏛️",
    title: "5. Official Court Data Provenance",
    description:
      "Court hearing dates, listings, orders, and judgment records are fetched directly from official Indian High Court and District Court eCourts registries. Every record clearly displays its source and exact last-synchronized timestamp.",
    badges: ["Official eCourts Sync", "Exact Sync Timestamps", "No Synthetic Real-Time Claims"],
  },
  {
    icon: "🛡️",
    title: "6. User Privacy & Data Deletion Controls",
    description:
      "In compliance with the Digital Personal Data Protection (DPDP) Act, you maintain complete ownership of your data. You can export your full litigation timeline at any time or request irrevocable account closure and data erasure.",
    badges: ["DPDP Act Compliant", "1-Click Data Export", "Complete Account Erasure"],
  },
];

const TRUST_FAQS = [
  {
    question: "Who can see my case documents?",
    answer: "Only you and the verified advocate you explicitly assign to your matter. Other users, unauthorized advocates, and general platform operators have zero access.",
  },
  {
    question: "What happens if a lawyer cancels our scheduled consultation?",
    answer: "Our automated billing engine immediately triggers a 100% full refund back to your original payment method, and notifies you immediately.",
  },
  {
    question: "Does LCC train artificial intelligence on my legal documents?",
    answer: "No. Under our strict non-AI policy and security baseline, client documents and confidential litigation narratives are never fed to external AI models or used for machine learning training.",
  },
  {
    question: "Where does hearing date information come from?",
    answer: "Directly from the official eCourts National Judicial Data Grid (NJDG) and respective High Court registries. We display the exact sync age so you know precisely how current the information is.",
  },
];

export default function TrustCenterPage() {
  return (
    <AppShell>
      <div className={styles.container}>
        <div className={styles.header}>
          <div className={styles.badge}>Security • Verification • Compliance</div>
          <h1 className={styles.title}>Legal Case Companion Trust Center</h1>
          <p className={styles.subtitle}>
            Transparent, verifiable answers to how we protect your confidential legal matters, verify legal practitioners, handle your money, and safeguard your constitutional privacy rights.
          </p>
        </div>

        <div className={styles.grid}>
          {TRUST_PILLARS.map((pillar) => (
            <div key={pillar.title} className={styles.card}>
              <div className={styles.cardIcon}>{pillar.icon}</div>
              <h3 className={styles.cardTitle}>{pillar.title}</h3>
              <p className={styles.cardDescription}>{pillar.description}</p>
              <div className={styles.pillList}>
                {pillar.badges.map((badge) => (
                  <span key={badge} className={styles.pill}>
                    {badge}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className={styles.faqSection}>
          <h2 className={styles.faqTitle}>Frequently Asked Questions About Trust & Safety</h2>
          <div className={styles.faqList}>
            {TRUST_FAQS.map((faq) => (
              <div key={faq.question} className={styles.faqItem}>
                <h4>{faq.question}</h4>
                <p>{faq.answer}</p>
              </div>
            ))}
          </div>
        </div>

        <div className={styles.contactBanner}>
          <p>
            Have a specific compliance, privacy, or security question?
            <Link href="/support" className={styles.contactLink}>
              Contact our Support & Compliance Desk →
            </Link>
          </p>
        </div>
      </div>
    </AppShell>
  );
}
