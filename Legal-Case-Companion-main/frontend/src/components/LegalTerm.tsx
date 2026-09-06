"use client";

import React, { useState } from "react";

export interface LegalTermData {
  technicalTerm: string;
  humanTitle: string;
  humanExplanation: string;
  whatItMeansForYou: string;
  actionRequired?: string;
  source?: string;
}

export const INDIAN_LEGAL_TERMS: Record<string, LegalTermData> = {
  "judgment reserved": {
    technicalTerm: "Judgment Reserved",
    humanTitle: "Decision is pending",
    humanExplanation:
      "The court has concluded all oral hearings and legal arguments from both sides. The judge has reserved the matter to write and deliver the final written verdict.",
    whatItMeansForYou:
      "No more arguments or hearings will take place for now. You do not need to attend court until the judge pronounces the judgment date.",
    actionRequired: "Keep your contact information updated with your advocate to receive instant notification upon delivery.",
    source: "High Court / District Court Procedural Code (Order XX CPC)",
  },
  "admission & denial": {
    technicalTerm: "Admission & Denial of Documents",
    humanTitle: "Document verification stage",
    humanExplanation:
      "Both parties formally inspect the evidentiary records filed by the opposite side and officially state on affidavit which documents they accept as authentic or dispute.",
    whatItMeansForYou:
      "This speeds up the trial by focusing only on disputed documents. Undisputed agreements or receipts are accepted directly into evidence.",
    actionRequired: "Ensure your original receipts, agreements, and identity documents are accessible to your counsel.",
    source: "Civil Procedure Code (Order XI & XII CPC)",
  },
  "cause list": {
    technicalTerm: "Cause List / Daily Board",
    humanTitle: "Daily court schedule",
    humanExplanation:
      "The official daily listing published by the court registry showing the sequence of matters to be heard by each judge on a given date.",
    whatItMeansForYou:
      "Your matter is listed with an Item Number. Lower item numbers are heard earlier in the day; higher numbers are heard in the afternoon.",
    actionRequired: "Note your Court Room number and Item Number to track when your advocate will present your case.",
    source: "High Court Registry & eCourts National Portal",
  },
  "vakalatnama": {
    technicalTerm: "Vakalatnama",
    humanTitle: "Lawyer authorization document",
    humanExplanation:
      "A statutory power-of-attorney document signed by you authorizing your advocate to represent, plead, and act on your behalf before the court.",
    whatItMeansForYou:
      "It legally empowers your advocate to submit filings, make oral submissions, and receive court communications for your matter.",
    actionRequired: "Must be signed by the litigant with requisite court fee stamps (Welfare Fund stamp) affixed.",
    source: "Advocates Act, 1961 & Bar Council of India Rules",
  },
  "written statement": {
    technicalTerm: "Written Statement (WS)",
    humanTitle: "Defendant's formal response",
    humanExplanation:
      "The formal written defense filed by the respondent or defendant systematically answering each allegation made in the plaintiff's suit.",
    whatItMeansForYou:
      "This is your primary opportunity as a defendant to present your defense, refute claims, and raise preliminary legal objections.",
    actionRequired: "Must be filed strictly within 30 to 120 days of summons under the Commercial Courts Act / CPC.",
    source: "Order VIII CPC / Commercial Courts Act, 2015",
  },
  "plaint": {
    technicalTerm: "Plaint / Petition",
    humanTitle: "Initial court filing",
    humanExplanation:
      "The founding document of a civil lawsuit outlining the facts of the dispute, legal cause of action, and specific relief sought from the court.",
    whatItMeansForYou:
      "It defines the scope of the entire case. The court cannot grant reliefs that are not formally pleaded in the plaint.",
    source: "Order VII CPC",
  },
  "notice issued": {
    technicalTerm: "Notice Issued / Summons",
    humanTitle: "Formal alert sent to opposing party",
    humanExplanation:
      "The court has reviewed the initial petition and officially ordered that legal notice be served on the other party commanding their appearance.",
    whatItMeansForYou:
      "The opposite side is formally notified. Proceedings cannot continue against them until proof of valid service is established.",
    actionRequired: "Track tracking speed-post / dasti service confirmation with your advocate.",
    source: "Order V CPC",
  },
  "framing of issues": {
    technicalTerm: "Framing of Issues",
    humanTitle: "Identifying core disputes",
    humanExplanation:
      "The judge reads the plaint and written statement, and formally records the specific legal questions and factual disputes that must be decided.",
    whatItMeansForYou:
      "The trial will strictly focus on answering these specific questions. Evidence must address these framed issues.",
    source: "Order XIV CPC",
  },
  "status quo": {
    technicalTerm: "Status Quo Order",
    humanTitle: "Keep current state unchanged",
    humanExplanation:
      "A binding court injunction directing both parties to maintain the existing situation of the property or dispute without creating new rights or changes.",
    whatItMeansForYou:
      "Neither party is permitted to sell, construct, demolish, or alter the disputed property or contract until further orders.",
    actionRequired: "Strictly adhere to current possession and avoid altering the condition of the subject matter.",
    source: "Order XXXIX CPC / Section 151 CPC",
  },
  "stay order": {
    technicalTerm: "Stay Order",
    humanTitle: "Temporary halt on actions",
    humanExplanation:
      "A judicial order suspending the operation, execution, or enforcement of an administrative decision, lower court decree, or legal proceeding.",
    whatItMeansForYou:
      "The challenged action is frozen and cannot be executed while the stay order remains active.",
    source: "High Court Appellate & Writ Jurisdiction",
  },
  "interim relief": {
    technicalTerm: "Interim Relief / Injunction",
    humanTitle: "Urgent temporary protection",
    humanExplanation:
      "Temporary court protection granted during the pendency of a case to prevent irreparable injury before the final outcome is decided.",
    whatItMeansForYou:
      "Protects your immediate rights (e.g. preventing eviction, freezing bank guarantees, or stopping asset disposal) while the trial continues.",
    source: "Section 9 Arbitration Act / Order XXXIX CPC",
  },
  "evidence stage": {
    technicalTerm: "Evidence Stage / Examination of Witnesses",
    humanTitle: "Presenting testimony & exhibits",
    humanExplanation:
      "Parties submit affidavits in evidence, summon official witnesses, and submit to cross-examination by the opposing advocate.",
    whatItMeansForYou:
      "This is the most critical fact-finding phase. Litigants or witnesses may need to be physically or virtually present for deposition.",
    actionRequired: "Coordinate with your advocate for pre-trial witness briefing and document mark-ups.",
    source: "Indian Evidence Act, 1872 / Bharatiya Sakshya Adhiniyam, 2023",
  },
  "arguments": {
    technicalTerm: "Final Arguments / Hearing",
    humanTitle: "Final lawyer presentations",
    humanExplanation:
      "Advocates for both sides deliver oral legal submissions analyzing the recorded evidence, statutory laws, and Supreme Court/High Court case precedents.",
    whatItMeansForYou:
      "The trial has concluded. The judge is hearing concluding analysis before reserving or pronouncing the decision.",
    source: "Civil / Criminal Procedure Code",
  },
  "disposed": {
    technicalTerm: "Disposed / Concluded",
    humanTitle: "Case completed / closed",
    humanExplanation:
      "The court has concluded the proceedings and rendered a final decree, order, judgment, or mutual settlement dismissal.",
    whatItMeansForYou:
      "The matter is formally complete before this forum. Further action only arises if an appeal, review, or execution petition is filed.",
    actionRequired: "Obtain a certified copy of the final judgment and decree through your advocate.",
    source: "Official Court Decree Register",
  },
  "dismissed": {
    technicalTerm: "Dismissed",
    humanTitle: "Case rejected by court",
    humanExplanation:
      "The court has declined the petition or suit, concluding that it lacks legal merit, statutory jurisdiction, or sufficient evidence.",
    whatItMeansForYou:
      "The relief requested was not granted. Consult counsel immediately regarding limitation timelines for statutory appeal or revision.",
    source: "Court Judgment / Order Record",
  },
  "ex-parte": {
    technicalTerm: "Ex-Parte Proceedings",
    humanTitle: "Hearing without other side",
    humanExplanation:
      "Proceedings conducted in the presence of one party only, after the opposing party failed to appear despite receiving valid court summons.",
    whatItMeansForYou:
      "If you are the applicant, your matter proceeds without opposition. If you are the absent party, an adverse order may be issued.",
    actionRequired: "If an ex-parte order was made against you, file an application under Order IX Rule 13 CPC immediately.",
    source: "Order IX CPC",
  },
  "cnr number": {
    technicalTerm: "CNR Number (Case National Reference)",
    humanTitle: "Unique 16-digit court case ID",
    humanExplanation:
      "The permanent 16-character alphanumeric reference number assigned to every case across all Indian District and High Courts under the eCourts project.",
    whatItMeansForYou:
      "This single identifier lets you track daily orders, hearing dates, and case status anywhere across India without needing the local filing number.",
    source: "National Judicial Data Grid (NJDG) / eCourts Project",
  },
  "legal hold": {
    technicalTerm: "Legal Hold / Preservation Directive",
    humanTitle: "Mandatory document freeze",
    humanExplanation:
      "A binding legal requirement ordering that all emails, digital documents, files, and physical papers related to the matter must be preserved and not deleted.",
    whatItMeansForYou:
      "Routine document disposal schedules are paused. Deleting or modifying relevant files can result in court sanctions or adverse inferences.",
    actionRequired: "Do not discard, alter, or shred any matter-related correspondence or contracts.",
    source: "Civil Procedure & Electronic Evidence Governance",
  },
  "open": {
    technicalTerm: "Open / Active",
    humanTitle: "Active matter",
    humanExplanation: "This matter is actively proceeding. Evidence, hearings, and procedural actions are ongoing.",
    whatItMeansForYou: "Keep documents organized and review upcoming dates or requests from your counsel.",
    source: "Matter Case Register",
  },
  "in_progress": {
    technicalTerm: "In Progress / Trial Stage",
    humanTitle: "Waiting for next hearing",
    humanExplanation: "The case is actively underway before the forum. The next hearing or trial date will be scheduled on the court board.",
    whatItMeansForYou: "Your lawyer will represent you on the listed dates. Prepare any requested evidence.",
    source: "eCourts Case Status Portal",
  },
  "in_review": {
    technicalTerm: "In Review / Pre-Filing",
    humanTitle: "Under counsel review",
    humanExplanation: "Your advocate is reviewing facts, agreements, and drafts prior to official registry filing or next stage.",
    whatItMeansForYou: "No immediate court appearance needed. Verify any pending document requests.",
    source: "Counsel Matter Management",
  },
  "pending_court": {
    technicalTerm: "Pending Court Listing",
    humanTitle: "Waiting for court listing",
    humanExplanation: "The petition or application has been submitted to the court registry and is waiting to be allocated a date on the cause list.",
    whatItMeansForYou: "The court registry is verifying filing requirements before listing it before a judge.",
    source: "Court Filing & Scrutiny Registry",
  },
  "closed": {
    technicalTerm: "Disposed / Completed",
    humanTitle: "Matter concluded",
    humanExplanation: "The legal proceeding has formally concluded following an order, settlement, or decree.",
    whatItMeansForYou: "No further active steps are required unless an appeal or compliance execution is pursued.",
    source: "Official Court Judgment Record",
  },
  "archived": {
    technicalTerm: "Archived Record",
    humanTitle: "Archived file",
    humanExplanation: "This matter has been closed and retained in secure cold storage for record-keeping and compliance.",
    whatItMeansForYou: "All documents and orders remain accessible for your reference.",
    source: "Digital Case Archive",
  },
  "scheduled": {
    technicalTerm: "Listed on Cause List",
    humanTitle: "Hearing scheduled",
    humanExplanation: "The court has fixed a specific date and time for oral submissions or procedural steps.",
    whatItMeansForYou: "Note the court room number and confirm preparation steps with your advocate.",
    source: "Daily Cause List / eCourts",
  },
  "adjourned": {
    technicalTerm: "Adjourned to Future Date",
    humanTitle: "Hearing rescheduled",
    humanExplanation: "The court postponed the hearing to a subsequent date, often for filing replies, witness availability, or judicial time.",
    whatItMeansForYou: "No adverse decision was made. The next hearing date is recorded on the cause list.",
    source: "Court Daily Order Sheet",
  },
};

export interface LegalTermProps {
  id?: string;
  term: string;
  source?: string;
  lastSynced?: string;
  showBadge?: boolean;
  interactive?: boolean;
  showHelpTrigger?: boolean;
  showTechnicalSubtitle?: boolean;
  layout?: "inline" | "stacked";
  compact?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export function LegalTerm({
  term,
  source,
  lastSynced = "Today",
  showBadge = true,
  interactive = true,
  showHelpTrigger = true,
  showTechnicalSubtitle = false,
  layout = "inline",
  className = "",
  style,
}: LegalTermProps) {
  const [expanded, setExpanded] = useState(false);

  const cleanKey = term.trim().toLowerCase();
  const termData = INDIAN_LEGAL_TERMS[cleanKey] || {
    technicalTerm: term,
    humanTitle: term,
    humanExplanation: "This is a court procedural or case status designation recorded for this matter.",
    whatItMeansForYou: "Review with your advocate for matter-specific legal implications.",
    source: source || "Court Case Record",
  };

  const effectiveSource = source || termData.source || "Official Court Registry";

  if (layout === "stacked" || showTechnicalSubtitle) {
    return (
      <span
        style={{
          position: "relative",
          display: "inline-flex",
          flexDirection: "column",
          gap: "2px",
          ...style,
        }}
        className={className}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
          <span style={{ fontWeight: 600, color: "var(--text-primary, #f8fafc)" }}>
            {termData.humanTitle}
          </span>
          {showHelpTrigger && (
            <button
              type="button"
              onClick={() => interactive && setExpanded(!expanded)}
              aria-expanded={expanded}
              aria-label={`What does ${termData.humanTitle} mean?`}
              style={{
                fontSize: "10px",
                color: "var(--brand-primary, #818cf8)",
                background: "rgba(99, 102, 241, 0.15)",
                border: "1px solid rgba(99, 102, 241, 0.3)",
                padding: "1px 6px",
                borderRadius: "var(--radius-xs, 4px)",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.03em",
                cursor: interactive ? "pointer" : "default",
                display: "inline-flex",
                alignItems: "center",
                gap: "3px",
              }}
            >
              <span>What does this mean?</span>
              <span style={{ fontSize: "9px" }}>{expanded ? "▲" : "▼"}</span>
            </button>
          )}
        </span>

        <span
          style={{
            fontSize: "11px",
            color: "var(--text-muted, #94a3b8)",
            fontFamily: "var(--font-mono, monospace)",
          }}
        >
          Technical status: {termData.technicalTerm}
        </span>

        {/* Layered Popover */}
        {expanded && (
          <span
            role="region"
            aria-label={`Plain language explanation for ${termData.humanTitle}`}
            style={{
              position: "absolute",
              top: "calc(100% + 8px)",
              left: 0,
              zIndex: "var(--z-popover, 1500)",
              width: "min(340px, 90vw)",
              background: "var(--surface-elevated, #151A24)",
              border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.12))",
              borderRadius: "var(--radius-lg, 12px)",
              padding: "16px",
              boxShadow: "var(--shadow-lg, 0 10px 25px -5px rgba(0,0,0,0.5))",
              color: "var(--text-primary, #f8fafc)",
              textAlign: "left",
              display: "block",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <span
              style={{
                display: "flex",
                alignItems: "flex-start",
                justifyContent: "space-between",
                gap: "8px",
                marginBottom: "10px",
              }}
            >
              <span
                style={{
                  fontSize: "10px",
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  color: "var(--brand-primary, #818cf8)",
                  display: "block",
                }}
              >
                Plain-Language Meaning
              </span>
              <button
                onClick={() => setExpanded(false)}
                aria-label="Close explanation"
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--text-muted, #64748b)",
                  cursor: "pointer",
                  padding: "2px 6px",
                  fontSize: "14px",
                  borderRadius: "var(--radius-xs, 4px)",
                }}
              >
                ✕
              </button>
            </span>

            <span style={{ display: "block", marginBottom: "12px" }}>
              <span
                style={{
                  display: "block",
                  margin: "0 0 4px 0",
                  fontSize: "var(--font-size-sm, 14px)",
                  fontWeight: 700,
                  color: "var(--text-primary, #f8fafc)",
                }}
              >
                {termData.humanTitle}
              </span>
              <span
                style={{
                  display: "block",
                  margin: 0,
                  fontSize: "var(--font-size-xs, 12px)",
                  lineHeight: 1.5,
                  color: "var(--text-secondary, #cbd5e1)",
                }}
              >
                {termData.humanExplanation}
              </span>
            </span>

            <span
              style={{
                background: "rgba(7, 9, 14, 0.7)",
                border: "1px solid rgba(255, 255, 255, 0.06)",
                padding: "8px 10px",
                borderRadius: "var(--radius-sm, 6px)",
                marginBottom: "12px",
                fontSize: "11px",
                display: "flex",
                flexDirection: "column",
                gap: "2px",
              }}
            >
              <span style={{ color: "var(--text-muted, #64748b)", textTransform: "uppercase", fontSize: "10px" }}>
                Technical status:
              </span>
              <span
                style={{
                  fontWeight: 600,
                  color: "#e2e8f0",
                  fontFamily: "var(--font-mono, monospace)",
                }}
              >
                {termData.technicalTerm}
              </span>
            </span>

            <span
              style={{
                borderTop: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                paddingTop: "10px",
                fontSize: "11px",
                color: "var(--text-muted, #64748b)",
                display: "flex",
                flexDirection: "column",
                gap: "2px",
              }}
            >
              <span style={{ display: "block" }}>
                <strong>Source:</strong> {effectiveSource}
              </span>
              <span style={{ display: "block" }}>
                <strong>Last synchronized:</strong> {lastSynced}
              </span>
            </span>

            <span
              style={{
                display: "block",
                marginTop: "10px",
                paddingTop: "8px",
                borderTop: "1px dashed rgba(255, 255, 255, 0.06)",
                fontSize: "10px",
                color: "var(--text-muted, #64748b)",
                fontStyle: "italic",
              }}
            >
              Informational plain-language glossary only · Does not constitute legal advice.
            </span>
          </span>
        )}
      </span>
    );
  }

  return (
    <span
      style={{
        position: "relative",
        display: "inline-flex",
        flexDirection: "column",
        verticalAlign: "middle",
        ...style,
      }}
      className={className}
    >
      {/* Compact Default Presentation */}
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          cursor: interactive ? "pointer" : "default",
          padding: showBadge ? "2px 8px" : "0",
          borderRadius: "var(--radius-sm, 6px)",
          background: showBadge ? "rgba(99, 102, 241, 0.12)" : "transparent",
          border: showBadge ? "1px solid rgba(99, 102, 241, 0.28)" : "none",
          color: "inherit",
          fontSize: "inherit",
          fontWeight: 500,
          transition: "var(--transition-fast, 0.15s ease)",
        }}
        title={interactive ? "Click for plain-language legal explanation" : undefined}
        role={interactive ? "button" : undefined}
        tabIndex={interactive ? 0 : undefined}
        aria-expanded={expanded}
        onClick={() => interactive && setExpanded(!expanded)}
        onKeyDown={(e) => {
          if (interactive && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            setExpanded(!expanded);
          } else if (e.key === "Escape" && expanded) {
            setExpanded(false);
          }
        }}
      >
        <span>{termData.humanTitle}</span>

        {showHelpTrigger && (
          <span
            style={{
              fontSize: "10px",
              color: "var(--brand-primary, #6366f1)",
              background: "rgba(99, 102, 241, 0.18)",
              padding: "1px 6px",
              borderRadius: "var(--radius-xs, 4px)",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.03em",
              display: "inline-flex",
              alignItems: "center",
              gap: "2px",
            }}
          >
            <span>What does this mean?</span>
            <span style={{ fontSize: "9px" }}>{expanded ? "▲" : "▼"}</span>
          </span>
        )}
      </span>

      {/* Layered Compact Popover / Card (No large modal forced) */}
      {expanded && (
        <span
          role="region"
          aria-label={`Plain language explanation for ${termData.humanTitle}`}
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            left: 0,
            zIndex: "var(--z-popover, 1500)",
            width: "min(340px, 90vw)",
            background: "var(--surface-elevated, #151A24)",
            border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.12))",
            borderRadius: "var(--radius-lg, 12px)",
            padding: "16px",
            boxShadow: "var(--shadow-lg)",
            color: "var(--text-primary, #f8fafc)",
            textAlign: "left",
            display: "block",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header with close button */}
          <span
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: "8px",
              marginBottom: "10px",
            }}
          >
            <span
              style={{
                fontSize: "10px",
                fontWeight: 700,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                color: "var(--brand-primary, #6366f1)",
                display: "block",
              }}
            >
              Plain-Language Meaning
            </span>
            <button
              onClick={() => setExpanded(false)}
              aria-label="Close explanation"
              style={{
                background: "transparent",
                border: "none",
                color: "var(--text-muted, #64748b)",
                cursor: "pointer",
                padding: "2px 6px",
                fontSize: "14px",
                borderRadius: "var(--radius-xs, 4px)",
              }}
            >
              ✕
            </button>
          </span>

          {/* LAYER 1: Human Explanation */}
          <span style={{ display: "block", marginBottom: "12px" }}>
            <span
              style={{
                display: "block",
                margin: "0 0 4px 0",
                fontSize: "var(--font-size-sm, 14px)",
                fontWeight: 700,
                color: "var(--text-primary, #f8fafc)",
              }}
            >
              {termData.humanTitle}
            </span>
            <span
              style={{
                display: "block",
                margin: 0,
                fontSize: "var(--font-size-xs, 12px)",
                lineHeight: 1.5,
                color: "var(--text-secondary, #cbd5e1)",
              }}
            >
              {termData.humanExplanation}
            </span>
          </span>

          {/* LAYER 2: Technical Legal Term */}
          <span
            style={{
              background: "rgba(7, 9, 14, 0.7)",
              border: "1px solid rgba(255, 255, 255, 0.06)",
              padding: "8px 10px",
              borderRadius: "var(--radius-sm, 6px)",
              marginBottom: "12px",
              fontSize: "11px",
              display: "flex",
              flexDirection: "column",
              gap: "2px",
            }}
          >
            <span style={{ color: "var(--text-muted, #64748b)", textTransform: "uppercase", fontSize: "10px" }}>
              Technical status:
            </span>
            <span
              style={{
                fontWeight: 600,
                color: "#e2e8f0",
                fontFamily: "var(--font-mono, monospace)",
              }}
            >
              {termData.technicalTerm}
            </span>
          </span>

          {/* LAYER 3: Source / Provenance */}
          <span
            style={{
              borderTop: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
              paddingTop: "10px",
              fontSize: "11px",
              color: "var(--text-muted, #64748b)",
              display: "flex",
              flexDirection: "column",
              gap: "2px",
            }}
          >
            <span style={{ display: "block" }}>
              <strong>Source:</strong> {effectiveSource}
            </span>
            <span style={{ display: "block" }}>
              <strong>Last synchronized:</strong> {lastSynced}
            </span>
          </span>

          {/* Informational Disclaimer */}
          <span
            style={{
              display: "block",
              marginTop: "10px",
              paddingTop: "8px",
              borderTop: "1px dashed rgba(255, 255, 255, 0.06)",
              fontSize: "10px",
              color: "var(--text-muted, #64748b)",
              fontStyle: "italic",
            }}
          >
            Informational plain-language glossary only · Does not constitute legal advice.
          </span>
        </span>
      )}
    </span>
  );
}

export default LegalTerm;
