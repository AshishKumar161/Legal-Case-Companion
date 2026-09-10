"use client";

import React, { useState } from "react";
import {
  CaseIntelligenceResponse,
  CaseParticipantItem,
  RetrievedLegalAuthorityItem,
} from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { EvidenceAuthorityMatrix } from "./EvidenceAuthorityMatrix";
import { IntelligenceGraph } from "./IntelligenceGraph";
import { TemporalValidityBadge } from "./TemporalValidityBadge";
import { apiClient } from "@/api/client";

interface IntelligenceCenterProps {
  caseId: string;
  caseTitle: string;
  intel: CaseIntelligenceResponse | null;
  participants: CaseParticipantItem[];
  onRefresh: () => Promise<void>;
  refreshing: boolean;
  onAskCopilot?: (prompt: string) => void;
}

type SubView = "OVERVIEW" | "MATRIX" | "GRAPH" | "CHRONOLOGY" | "AUTHORITY_SEARCH";

export function IntelligenceCenter({
  caseId,
  caseTitle,
  intel,
  participants,
  onRefresh,
  refreshing,
  onAskCopilot,
}: IntelligenceCenterProps) {
  const [activeSubView, setActiveSubView] = useState<SubView>("OVERVIEW");

  // Authority Search State
  const [authQuery, setAuthQuery] = useState("");
  const [authResults, setAuthResults] = useState<RetrievedLegalAuthorityItem[]>([]);
  const [searchingAuth, setSearchingAuth] = useState(false);

  const facts = intel?.facts || [];
  const issues = intel?.issues || [];
  const gaps = intel?.evidence_gaps || [];
  const risks = intel?.risks || [];
  const timeline = intel?.timeline || [];
  const summary = intel?.summary;

  const handleSearchAuthorities = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authQuery.trim() || searchingAuth) return;
    setSearchingAuth(true);
    try {
      const res = await apiClient.post("/api/v1/legal-authorities/search", {
        query: authQuery.trim(),
        top_k: 8,
        search_mode: "HYBRID",
      });
      setAuthResults(res.results || []);
    } catch (err) {
      console.error("Legal authority search error:", err);
      setAuthResults([]);
    } finally {
      setSearchingAuth(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Top Header & Sub-navigation */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
          borderBottom: "1px solid var(--border-subtle)",
          paddingBottom: "16px",
        }}
      >
        <div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "11px",
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--accent-secondary)",
              marginBottom: "4px",
            }}
          >
            <span>●</span> Legal Case Intelligence 1.0
          </div>
          <h2 style={{ fontSize: "22px", fontWeight: 700, color: "var(--text-primary)" }}>
            Matter Intelligence Center
          </h2>
        </div>

        {/* View Switcher */}
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
          <button
            onClick={() => setActiveSubView("OVERVIEW")}
            className={`btn ${activeSubView === "OVERVIEW" ? "btn-primary" : "btn-secondary"}`}
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            📊 Executive Ledger
          </button>
          <button
            onClick={() => setActiveSubView("MATRIX")}
            className={`btn ${activeSubView === "MATRIX" ? "btn-primary" : "btn-secondary"}`}
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            ⚖ Evidence ↔ Authorities
          </button>
          <button
            onClick={() => setActiveSubView("GRAPH")}
            className={`btn ${activeSubView === "GRAPH" ? "btn-primary" : "btn-secondary"}`}
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            🕸 Knowledge Graph
          </button>
          <button
            onClick={() => setActiveSubView("CHRONOLOGY")}
            className={`btn ${activeSubView === "CHRONOLOGY" ? "btn-primary" : "btn-secondary"}`}
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            ◷ Chronology & Conflicts
          </button>
          <button
            onClick={() => setActiveSubView("AUTHORITY_SEARCH")}
            className={`btn ${activeSubView === "AUTHORITY_SEARCH" ? "btn-primary" : "btn-secondary"}`}
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            🔍 Indian Statutes
          </button>
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="btn btn-secondary"
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            {refreshing ? "Synthesizing..." : "↻ Re-extract Intelligence"}
          </button>
        </div>
      </div>

      {/* Summary KPI Strip */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "12px",
        }}
      >
        <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", padding: "14px 16px" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>Verified Facts</div>
          <div style={{ fontSize: "22px", fontWeight: 700, color: "#10b981", marginTop: "2px" }}>
            {summary?.verified_facts ?? facts.filter((f) => f.verification_status === "HUMAN_CONFIRMED" || f.verification_status === "AI_VERIFIED").length}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
            {facts.length} total on record
          </div>
        </div>

        <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", padding: "14px 16px" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>Contested Issues</div>
          <div style={{ fontSize: "22px", fontWeight: 700, color: "#60a5fa", marginTop: "2px" }}>
            {summary?.open_issues ?? issues.length}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
            Legal controversies identified
          </div>
        </div>

        <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", padding: "14px 16px" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>Evidence Gaps</div>
          <div style={{ fontSize: "22px", fontWeight: 700, color: gaps.length > 0 ? "#f59e0b" : "#10b981", marginTop: "2px" }}>
            {summary?.evidence_gaps ?? gaps.length}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
            Missing proofs & corroborations
          </div>
        </div>

        <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", padding: "14px 16px" }}>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 700, textTransform: "uppercase" }}>High / Critical Risks</div>
          <div style={{ fontSize: "22px", fontWeight: 700, color: risks.length > 0 ? "#ef4444" : "#10b981", marginTop: "2px" }}>
            {(summary?.high_risks || 0) + (summary?.critical_risks || 0) || risks.filter((r) => r.severity === "HIGH" || r.severity === "CRITICAL").length}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "2px" }}>
            Limitation & procedural alerts
          </div>
        </div>
      </div>

      {/* VIEW 1: EXECUTIVE LEDGER (OVERVIEW) */}
      {activeSubView === "OVERVIEW" && (
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "20px", alignItems: "start" }}>
          {/* Left Column: Facts Ledger */}
          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "24px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h3 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)" }}>
                  Verified Case Facts Ledger ({facts.length})
                </h3>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                  Facts grounded in active evidence documents with verification provenance.
                </p>
              </div>
            </div>

            {facts.length === 0 ? (
              <div style={{ padding: "32px 0", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                No facts extracted yet. Refresh intelligence to process active case documents.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {facts.map((f) => (
                  <div
                    key={f.id}
                    style={{
                      padding: "14px",
                      borderRadius: "var(--radius-sm)",
                      background: "var(--surface-subtle)",
                      border: "1px solid var(--border-subtle)",
                      display: "flex",
                      flexDirection: "column",
                      gap: "6px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "11px", fontWeight: 600, color: "#60a5fa" }}>
                        📄 {f.source_filename || "Document Extract"}
                      </span>
                      <StatusBadge status={f.verification_status} />
                    </div>
                    <div style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: 1.5 }}>
                      {f.fact_text || f.fact_statement}
                    </div>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      Category: {f.category || "General"} • Source: {f.source_type}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right Column: Evidence Gaps & Risks Radar */}
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {/* Gaps */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px",
              }}
            >
              <h3 style={{ fontSize: "15px", fontWeight: 700, color: "#f59e0b", marginBottom: "12px" }}>
                ⚠ Evidence Gaps ({gaps.length})
              </h3>
              {gaps.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: "12px" }}>No unresolved evidence gaps.</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {gaps.map((g) => (
                    <div
                      key={g.id}
                      style={{
                        padding: "10px 12px",
                        borderRadius: "var(--radius-sm)",
                        background: "rgba(245, 158, 11, 0.06)",
                        border: "1px solid rgba(245, 158, 11, 0.2)",
                        fontSize: "12px",
                      }}
                    >
                      <div style={{ fontWeight: 600, color: "#f59e0b" }}>{g.gap_type}</div>
                      <div style={{ color: "var(--text-primary)", marginTop: "2px" }}>{g.description}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Procedural Risks */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px",
              }}
            >
              <h3 style={{ fontSize: "15px", fontWeight: 700, color: "#ef4444", marginBottom: "12px" }}>
                🚨 Risk Radar ({risks.length})
              </h3>
              {risks.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: "12px" }}>No high risks detected.</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {risks.map((r) => (
                    <div
                      key={r.id}
                      style={{
                        padding: "10px 12px",
                        borderRadius: "var(--radius-sm)",
                        background: "rgba(239, 68, 68, 0.06)",
                        border: "1px solid rgba(239, 68, 68, 0.2)",
                        fontSize: "12px",
                      }}
                    >
                      <div style={{ fontWeight: 600, color: "#ef4444" }}>{r.risk_title} ({r.severity})</div>
                      <div style={{ color: "var(--text-primary)", marginTop: "2px" }}>{r.description}</div>
                      {r.mitigation_hint && (
                        <div style={{ color: "#9ca3af", marginTop: "4px", fontSize: "11px" }}>
                          Mitigation: {r.mitigation_hint}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* VIEW 2: EVIDENCE ↔ AUTHORITY MATRIX */}
      {activeSubView === "MATRIX" && (
        <EvidenceAuthorityMatrix
          issues={issues}
          facts={facts}
          caseId={caseId}
          onAskCopilot={onAskCopilot}
        />
      )}

      {/* VIEW 3: KNOWLEDGE GRAPH */}
      {activeSubView === "GRAPH" && (
        <IntelligenceGraph
          caseTitle={caseTitle}
          caseId={caseId}
          participants={participants}
          issues={issues}
          facts={facts}
        />
      )}

      {/* VIEW 4: CHRONOLOGY & CONFLICTS */}
      {activeSubView === "CHRONOLOGY" && (
        <div
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "24px",
          }}
        >
          <h3 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "16px" }}>
            Chronological Sequence & Source Conflicts ({timeline.length})
          </h3>

          {timeline.length === 0 ? (
            <div style={{ padding: "32px 0", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
              No chronological events currently mapped.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {timeline.map((evt) => (
                <div
                  key={evt.id}
                  style={{
                    padding: "14px",
                    borderRadius: "var(--radius-sm)",
                    background: evt.is_conflicting ? "rgba(239, 68, 68, 0.08)" : "var(--surface-subtle)",
                    border: evt.is_conflicting ? "1px solid rgba(239, 68, 68, 0.3)" : "1px solid var(--border-subtle)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: 600, color: evt.is_conflicting ? "#f87171" : "#fff", fontSize: "13px" }}>
                      {evt.event_type} {evt.is_conflicting ? "• [CONFLICT DETECTED]" : ""}
                    </span>
                    <span style={{ fontSize: "12px", color: "var(--accent-secondary)", fontWeight: 600 }}>
                      {evt.date_text || evt.event_date || "Date Unspecified"}
                    </span>
                  </div>
                  <div style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: 1.5 }}>
                    {evt.description}
                  </div>
                  {evt.source_filename && (
                    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      Source Record: {evt.source_filename}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* VIEW 5: INDIAN LEGAL AUTHORITIES SEARCH */}
      {activeSubView === "AUTHORITY_SEARCH" && (
        <div
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
          }}
        >
          <div>
            <h3 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)" }}>
              Authoritative Indian Statutory & Precedent Retrieval
            </h3>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "4px" }}>
              Search across codified enactments (Limitation Act 1963, Commercial Courts Act 2015, NI Act 1881, Arbitration Act 1996) and binding Supreme Court decisions.
            </p>
          </div>

          <form onSubmit={handleSearchAuthorities} style={{ display: "flex", gap: "10px" }}>
            <input
              type="text"
              value={authQuery}
              onChange={(e) => setAuthQuery(e.target.value)}
              placeholder="e.g. section 138 notice statutory limitation or section 34 setting aside award..."
              className="input-field"
              style={{ flex: 1 }}
            />
            <button type="submit" disabled={searchingAuth} className="btn btn-primary">
              {searchingAuth ? "Searching Law..." : "Search Authorities"}
            </button>
          </form>

          {authResults.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {authResults.map((auth, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: "16px",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--surface-subtle)",
                    border: "1px solid var(--border-subtle)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "10px" }}>
                    <div>
                      <h4 style={{ fontSize: "15px", fontWeight: 700, color: "#fff" }}>
                        {auth.name} • Section {auth.section_number}: {auth.title}
                      </h4>
                      <div style={{ fontSize: "12px", color: "var(--accent-secondary)", marginTop: "2px" }}>
                        {auth.canonical_identifier} • Version: {auth.version_label}
                      </div>
                    </div>
                    <TemporalValidityBadge
                      isCurrent={auth.is_current}
                      effectiveFrom={auth.effective_from}
                      effectiveTo={auth.effective_to}
                      authorityLevel={auth.authority_level}
                      jurisdiction={auth.jurisdiction}
                    />
                  </div>

                  <div style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                    {auth.content}
                  </div>

                  {onAskCopilot && (
                    <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "10px", marginTop: "4px" }}>
                      <button
                        onClick={() =>
                          onAskCopilot(
                            `How does Section ${auth.section_number} of ${auth.name} apply to our case evidence?`
                          )
                        }
                        className="btn btn-secondary"
                        style={{ fontSize: "11px", padding: "4px 8px" }}
                      >
                        ✦ Query Applicability in Copilot
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
