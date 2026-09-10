"use client";

import React from "react";
import Link from "next/link";
import {
  CaseIcon,
  CalendarIcon,
  LawyerIcon,
  DocumentIcon,
  CourthouseIcon,
  AssistantIcon,
  ArrowRightIcon,
} from "@/components/ui/Icons";
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

function getContextIcon(context: NextStepContext) {
  switch (context) {
    case "CASE":
      return <CaseIcon size={20} />;
    case "HEARING":
      return <CalendarIcon size={20} />;
    case "LAWYER_PROFILE":
      return <LawyerIcon size={20} />;
    case "COURT_TRACKING":
      return <CourthouseIcon size={20} />;
    case "DOCUMENT":
      return <DocumentIcon size={20} />;
    default:
      return <AssistantIcon size={20} />;
  }
}

const CONTEXT_TITLES: Record<NextStepContext, string> = {
  CASE: "Next Action",
  HEARING: "Upcoming Hearing",
  LAWYER_PROFILE: "Consultation",
  PAYMENT: "Payment",
  COURT_TRACKING: "Court Update",
  DASHBOARD: "Next Action",
  DOCUMENT: "Document Needed",
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
  let urgencyClass = styles.urgencyMedium;
  if (urgency === "CRITICAL") urgencyClass = styles.urgencyCritical;
  else if (urgency === "HIGH") urgencyClass = styles.urgencyHigh;
  else if (urgency === "LOW") urgencyClass = styles.urgencyLow;

  const kickerTitle = CONTEXT_TITLES[context] || "Next Step";

  const renderAction = (act: NextStepActionItem, isPrimary = true) => {
    const btnClass = isPrimary ? styles.primaryAction : styles.secondaryAction;
    if (act.href) {
      return (
        <Link href={act.href} className={btnClass}>
          <span>{act.label}</span>
          {isPrimary && <ArrowRightIcon size={12} />}
        </Link>
      );
    }
    return (
      <button type="button" onClick={act.onClick} className={btnClass}>
        <span>{act.label}</span>
        {isPrimary && <ArrowRightIcon size={12} />}
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
          {getContextIcon(context)}
        </div>
        <div className={styles.textBlock}>
          <div className={styles.kickerRow}>
            <span className={styles.kicker}>{kickerTitle}</span>
            {provenance && (
              <span className={styles.provenanceBadge}>
                {provenance === "OFFICIAL COURT DATA" ? "Court Record" : provenance === "LAWYER ENTERED" ? "From Lawyer" : "Case Guidance"}
              </span>
            )}
          </div>
          <h4 className={styles.headline}>{headline}</h4>
          {detail && <p className={styles.detail}>{detail}</p>}
        </div>
      </div>

      <div className={styles.actionsWrapper}>
        {secondaryAction && renderAction(secondaryAction, false)}
        {action && renderAction(action, true)}
      </div>
    </aside>
  );
}
