import Link from "next/link";
import styles from "./page.module.css";

const features = [
  ["▣", "CASE OPERATIONS", "One workspace for matters, participants, documents, notes, deadlines and hearings."],
  ["✦", "LEGAL AI", "Evidence-grounded assistance and legal authority research designed for Indian workflows."],
  ["◉", "COUNSEL NETWORK", "Discover lawyers, review profiles, check availability and continue into consultations."],
  ["◇", "DOCUMENTS", "Organize sensitive evidence with controlled access and a private document architecture."],
  ["↗", "WORKFLOW", "Turn hearings, deadlines and tasks into visible next actions for the case team."],
  ["✓", "GOVERNANCE", "Role-aware access, auditability, observability and production controls for serious operations."],
];

const matters = [
  ["SM", "Sharma v. Mehta", "Hearing tomorrow · Delhi HC", "Urgent"],
  ["RS", "Rao & Sons — Contract", "Evidence review · 2 documents", "Review"],
  ["PA", "People v. Arora", "Deadline · 06 Sep", "Due soon"],
];

export default function Home() {
  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroGlow} aria-hidden="true" />
        <div className={styles.heroGrid} aria-hidden="true" />
        <div className={styles.heroInner}>
          <div className={styles.eyebrow}><span /> India-focused legal technology</div>
          <h1>Legal work,<br /><em>organized intelligently.</em></h1>
          <p className={styles.heroLead}>Legal Case Companion brings case management, evidence, legal research, counsel discovery and workflow into one professional workspace.</p>
          <div className={styles.actions}>
            <Link className={styles.primaryCta} href="/register">Start your workspace <b>→</b></Link>
            <Link className={styles.secondaryCta} href="/lawyers">Explore lawyers</Link>
          </div>
          <div className={styles.trustRow}><span>Designed for</span><b>Clients</b><i>·</i><b>Lawyers</b><i>·</i><b>Legal teams</b></div>

          <div className={styles.productFrame}>
            <div className={styles.browserBar}><div className={styles.browserDots}><span /><span /><span /></div><div className={styles.browserAddress}>app.legalcasecompanion.com</div><div className={styles.browserStatus}>Secure workspace</div></div>
            <div className={styles.productBody}>
              <aside className={styles.sidebar}>
                <div className={styles.brandMark}>⚖</div><div className={styles.sidebarTitle}>Workspace</div>
                {["Overview", "Cases", "Legal Copilot", "Documents", "Lawyers", "Tasks & hearings"].map((item, index) => <div className={`${styles.sideItem} ${index === 0 ? styles.sideItemActive : ""}`} key={item}><span>{["▦", "□", "✦", "◈", "◌", "◷"][index]}</span>{item}</div>)}
              </aside>
              <div className={styles.dashboardMock}>
                <div className={styles.mockTopline}><div><small>CASE COMMAND CENTER</small><h2>Good morning, Counsel.</h2><p>3 matters need attention today.</p></div><button>+ New case</button></div>
                <div className={styles.metricGrid}>{[["Active matters", "12", "+2 this month"], ["Upcoming hearings", "04", "Next: tomorrow"], ["Open tasks", "08", "3 due this week"], ["Documents", "148", "Processing healthy"]].map(([label, value, note]) => <div className={styles.metricCard} key={label}><span>{label}</span><strong>{value}</strong><small>{note}</small></div>)}</div>
                <div className={styles.mockColumns}>
                  <div className={styles.mockPanel}><div className={styles.panelHeading}><b>Priority matters</b><span>View all</span></div>{matters.map(([initials, title, detail, tag]) => <div className={styles.caseRow} key={title}><div className={styles.caseAvatar}>{initials}</div><div><strong>{title}</strong><span>{detail}</span></div><em>{tag}</em></div>)}</div>
                  <div className={styles.mockPanel}><div className={styles.panelHeading}><b>Legal Copilot</b><span className={styles.liveBadge}>● Live</span></div><div className={styles.copilotQuote}><span>✦</span><p>Summarize the strongest evidence supporting the limitation argument in this matter.</p></div><div className={styles.sourceLine}><span>3 grounded sources</span><span>Case docs + authorities</span></div></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.statsSection}><div className={styles.statsInner}>{[["Case management", "Structured"], ["Legal research", "Source-aware"], ["Counsel discovery", "Role-based"], ["Document storage", "Private"]].map(([label, value]) => <div className={styles.statItem} key={label}><span>{label}</span><strong>{value}</strong></div>)}</div></section>

      <section className={styles.featuresSection} id="platform">
        <div className={styles.sectionIntro}><div><div className={styles.sectionEyebrow}>THE PLATFORM</div><h2>Everything important,<br />connected in one place.</h2></div><p>A legal operating system should be focused, auditable and built around the matter—not around a pile of disconnected tools.</p></div>
        <div className={styles.featureGrid}>{features.map(([icon, eyebrow, text]) => <article className={styles.featureCard} key={eyebrow}><div className={styles.featureIcon}>{icon}</div><div className={styles.featureEyebrow}>{eyebrow}</div><h3>{text.split(".")[0]}.</h3><p>{text}</p><div className={styles.featureArrow}>↗</div></article>)}</div>
      </section>

      <section className={styles.workflowSection}><div className={styles.workflowCopy}><div className={styles.sectionEyebrow}>FROM ISSUE TO ACTION</div><h2>A clearer path through every matter.</h2><p>Start with the problem, build the record, validate the relevant authorities, bring in counsel and keep the next action visible.</p><Link className={styles.textCta} href="/register">Build a case workspace <span>→</span></Link></div><div className={styles.timeline}>{[["01", "Frame the matter", "Capture facts, parties, jurisdiction and the issue in a structured case record."], ["02", "Bring the evidence", "Upload and organize documents so the matter has one source of truth."], ["03", "Research with context", "Use grounded AI and legal authority retrieval against the actual case."], ["04", "Move the case forward", "Coordinate counsel, hearings, deadlines, tasks and follow-up."]].map(([number, title, text]) => <div className={styles.timelineRow} key={number}><div className={styles.timelineNumber}>{number}</div><div className={styles.timelineContent}><h3>{title}</h3><p>{text}</p></div></div>)}</div></section>

      <section className={styles.securitySection}><div className={styles.securityCard}><div><div className={styles.sectionEyebrow}>TRUST & GOVERNANCE</div><h2>Professional by design.<br />Responsible by default.</h2><p>Sensitive legal workflows need more than a polished interface. LCC is structured around authorization, document controls, auditability and evidence-grounded assistance.</p></div><div className={styles.securityList}>{["Role-aware access controls", "Private document storage", "Audit-friendly operations", "Evidence-grounded AI workflow"].map(item => <div className={styles.securityItem} key={item}><span>✓</span>{item}</div>)}</div></div></section>

      <section className={styles.finalCta}><div className={styles.finalGlow} aria-hidden="true" /><div className={styles.sectionEyebrow}>NEXT MATTER. BETTER SYSTEM.</div><h2>Give every case a command center.</h2><p>Set up a professional workspace for legal operations, research and client collaboration.</p><div className={styles.actions}><Link className={styles.primaryCta} href="/register">Get started <b>→</b></Link><Link className={styles.secondaryCta} href="/login">Sign in</Link></div></section>

      <footer className={styles.footer}><div className={styles.footerBrand}><div className={styles.footerLogo}>⚖</div><div><strong>Legal Case Companion</strong><span>India-focused legal technology</span></div></div><div className={styles.footerLinks}><Link href="/lawyers">Lawyers</Link><Link href="/login">Sign in</Link><Link href="/register">Create workspace</Link></div><div className={styles.footerMeta}>© 2026 Legal Case Companion</div></footer>
    </div>
  );
}
