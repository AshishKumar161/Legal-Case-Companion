"use client";

import React from "react";
import Link from "next/link";
import styles from "./NextStep.module.css";

export type NextStepContext =
  | "CASE"
  | "HEARING"
  | "LAWYER_PROFILE"
  | "PAYMENT"
  | "COURT_TRACKING"
  | "DASHBOARD"
  | "DOCUMENT";

export interface NextStepActionItem {
  label: string;
  href?: string;
  onClick?: () => void;
}

export interface NextStepProps {
  context: NextStepContext;
  headline: string;
  detail?: string;
  provenance?: "OFFICIAL COURT DATA" | "LAWYER ENTERED" | "YOU ADDED" | "SYSTEM" | "LCC INFORMATION";
  action: NextStepActionItem;
  secondaryAction?: NextStepActionItem;
  urgency?: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  className?: string;
}

const CONTEXT_ICONS: Record<NextStepContext, string> = {
  CASE: "⚖",
  HEARING: "📅",
  LAWYER_PROFILE: "🧑‍⚖️",
  PAYMENT: "💳",
  COURT_TRACKING: "🏛",
  DASHBOARD: "⚡",
  DOCUMENT: "📄",
};

const CONTEXT_TITLES: Record<NextStepContext, string> = {
  CASE: "Case Action",
  HEARING: "Upcoming Hearing",
  LAWYER_PROFILE: "Consultation Booking",
  PAYMENT: "Payment Action",
  COURT_TRACKING: "Court Update",
  DASHBOARD: "Immediate Next Action",
  DOCUMENT: "Evidence Vault",
};

export function NextStep({
  context,
  headline,
  detail,
  provenance = "LCC INFORMATION",
  action,
  secondaryAction,
  urgency = "MEDIUM",
  className = "",
}: NextStepProps) {
  // Map urgency class
  let urgencyClass = styles.urgencyMedium;
  if (urgency === "CRITICAL") urgencyClass = styles.urgencyCritical;
  else if (urgency === "HIGH") urgencyClass = styles.urgencyHigh;
  else if (urgency === "LOW") urgencyClass = styles.urgencyLow;

  const icon = CONTEXT_ICONS[context] || "⚡";
  const kickerTitle = CONTEXT_TITLES[context] || "Next Step";

  const renderAction = (act: NextStepActionItem, isPrimary = true) => {
    const btnClass = isPrimary ? styles.primaryAction : styles.secondaryAction;
    if (act.href) {
      return (
        <Link href={act.href} className={btnClass}>
          {act.label}
        </Link>
      );
    }
    return (
      <button type="button" onClick={act.onClick} className={btnClass}>
        {act.label}
      </button>
    );
  };

  return (
    <aside
      className={`${styles.nextStepCard} ${urgencyClass} ${className}`}
      aria-label={`Next Step: ${headline}`}
      role="region"
    >
      <div className={styles.contentWrapper}>
        <div className={styles.contextIcon} aria-hidden="true">
          {icon}
        </div>
        <div className={styles.textBlock}>
          <div className={styles.kickerRow}>
            <span className={styles.kicker}>{kickerTitle}</span>
            {provenance && (
              <span className={styles.provenanceBadge} title={`Source: ${provenance}`}>
                {provenance}
              </span>
            )}
          </div>
          <h4 className={styles.headline}>{headline}</h4>
          {detail && <p className={styles.detail}>{detail}</p>}
        </div>
      </div>

      <div className={styles.actionGroup}>
        {secondaryAction && renderAction(secondaryAction, false)}
        {action && renderAction(action, true)}
      </div>
    </aside>
  );
}
