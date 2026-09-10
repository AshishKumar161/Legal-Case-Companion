"use client";

import React, { useState } from "react";
import {
  CaseTaskItem,
  CaseDeadlineItem,
  CaseHearingItem,
  CaseNoteItem,
  DecisionRecordItem,
  EvidenceGapItem,
  CaseRiskIndicatorItem,
  LegalIssueItem,
  CaseFactItem,
} from "@/types";
import { HearingCommandCard } from "./HearingCommandCard";
import { CasePlanView } from "./CasePlanView";
import { TaskComposerModal } from "./TaskComposerModal";
import { DecisionRecordModal } from "./DecisionRecordModal";
import { apiClient } from "@/api/client";

interface ActionCenterProps {
  caseId: string;
  tasks: CaseTaskItem[];
  deadlines: CaseDeadlineItem[];
  hearings: CaseHearingItem[];
  notes: CaseNoteItem[];
  gaps: EvidenceGapItem[];
  risks: CaseRiskIndicatorItem[];
  issues: LegalIssueItem[];
  facts: CaseFactItem[];
  onRefreshWorkflow: () => Promise<void>;
  onRefreshNotes: () => Promise<void>;
  onNavigateToTab: (tab: string) => void;
}

type ActionSubView = "QUEUE" | "HEARINGS" | "PLAN" | "DECISIONS";

export function ActionCenter({
  caseId,
  tasks,
  deadlines,
  hearings,
  notes,
  gaps,
  issues,
  facts,
  onRefreshWorkflow,
  onRefreshNotes,
  onNavigateToTab,
}: ActionCenterProps) {
  const [subView, setSubView] = useState<ActionSubView>("QUEUE");
  const [generatingSuggestions, setGeneratingSuggestions] = useState(false);

  // Modal controls
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [taskModalInitialTitle, setTaskModalInitialTitle] = useState("");
  const [taskModalInitialDesc, setTaskModalInitialDesc] = useState("");
  const [taskModalInitialPriority, setTaskModalInitialPriority] = useState<"LOW" | "MEDIUM" | "HIGH" | "URGENT">("MEDIUM");
  const [taskModalSourceType, setTaskModalSourceType] = useState("MANUAL");
  const [taskModalSourceRef, setTaskModalSourceRef] = useState<string | undefined>();

  const [decisionModalOpen, setDecisionModalOpen] = useState(false);
  const [decisionModalInitialTitle, setDecisionModalInitialTitle] = useState("");

  // Extract human decisions from CaseNotes with [DECISION] tag
  const decisions: DecisionRecordItem[] = notes
    .filter((n) => n.title && n.title.includes("[DECISION]"))
    .map((n) => ({
      id: n.id,
      case_id: n.case_id,
      title: n.title ? n.title.replace("[DECISION]", "").trim() : "Untitled Decision",
      context: "Recorded Case Strategy",
      rationale: n.content,
      decision_owner: n.author_id ? `User #${n.author_id.slice(0, 8)}` : "Authorized Counsel",
      status: "RECORDED",
      created_at: n.created_at,
    }));

  // Trigger backend AI suggestion generator
  const handleGenerateSuggestions = async () => {
    setGeneratingSuggestions(true);
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/workflow/suggestions/generate`, {});
      await onRefreshWorkflow();
    } catch (err) {
      console.error("Suggestion generation error:", err);
    } finally {
      setGeneratingSuggestions(false);
    }
  };

  // Toggle task completion
  const handleToggleTask = async (taskId: string, currentStatus: string) => {
    const newStatus = currentStatus === "COMPLETED" ? "IN_PROGRESS" : "COMPLETED";
    try {
      await apiClient.patch(`/api/v1/cases/${caseId}/tasks/${taskId}`, { status: newStatus });
      await onRefreshWorkflow();
    } catch (err) {
      console.error("Task update error:", err);
    }
  };

  // Confirm unconfirmed task
  const handleConfirmTask = async (taskId: string) => {
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/tasks/${taskId}/confirm`, {});
      await onRefreshWorkflow();
    } catch (err) {
      console.error("Task confirmation error:", err);
    }
  };

  // Confirm unconfirmed deadline
  const handleConfirmDeadline = async (deadlineId: string) => {
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/deadlines/${deadlineId}/confirm`, {});
      await onRefreshWorkflow();
    } catch (err) {
      console.error("Deadline confirmation error:", err);
    }
  };

  // Open Task Composer from Evidence Gap
  const handleCreateTaskFromGap = (gap: EvidenceGapItem) => {
    setTaskModalInitialTitle(`Procure Evidence: ${gap.description.slice(0, 60)}`);
    setTaskModalInitialDesc(gap.description);
    setTaskModalInitialPriority(gap.severity === "HIGH" || gap.severity === "CRITICAL" ? "HIGH" : "MEDIUM");
    setTaskModalSourceType("EVIDENCE_GAP");
    setTaskModalSourceRef(gap.id);
    setTaskModalOpen(true);
  };

  // Open Task Composer from Hearing
  const handleCreatePrepTaskFromHearing = (hearing: CaseHearingItem) => {
    setTaskModalInitialTitle(`Hearing Prep: ${hearing.court_name} (${hearing.purpose.slice(0, 40)})`);
    setTaskModalInitialDesc(`Preparation for listed hearing at ${hearing.court_name} on ${new Date(hearing.hearing_at).toLocaleString("en-IN")}. Coram: ${hearing.bench_or_coram || "TBD"}`);
    setTaskModalInitialPriority("URGENT");
    setTaskModalSourceType("HEARING");
    setTaskModalSourceRef(hearing.id);
    setTaskModalOpen(true);
  };

  // Classify priority action items
  const criticalItems: Array<{ id: string; title: string; subtitle: string; tag: string; action: () => void; actionLabel: string }> = [];
  const attentionItems: Array<{ id: string; title: string; subtitle: string; tag: string; action: () => void; actionLabel: string }> = [];
  const routineItems: Array<{ id: string; title: string; subtitle: string; tag: string; action: () => void; actionLabel: string }> = [];

  // Critical: Imminent hearings (<7 days)
  hearings.forEach((h) => {
    const hearingTime = new Date(h.hearing_at).getTime();
    const nowTime = new Date().setHours(0, 0, 0, 0);
    const diff = (hearingTime - nowTime) / (1000 * 60 * 60 * 24);
    if (diff >= 0 && diff <= 7 && h.status === "SCHEDULED") {
      criticalItems.push({
        id: `h-${h.id}`,
        title: `Court Hearing at ${h.court_name}`,
        subtitle: `Listed in ${Math.ceil(diff)} days • ${h.purpose}`,
        tag: "CRITICAL LISTING",
        action: () => handleCreatePrepTaskFromHearing(h),
        actionLabel: "+ Prepare Task",
      });
    }
  });

  // Critical: Statutory limitation deadlines
  deadlines.forEach((d) => {
    if (d.deadline_type === "STATUTORY_LIMITATION" && d.status !== "COMPLETED") {
      criticalItems.push({
        id: `dl-${d.id}`,
        title: `Statutory Limitation Deadline: ${d.title}`,
        subtitle: `Target: ${new Date(d.deadline_at).toLocaleDateString("en-IN")} • Limitation Act / Commercial Courts Act`,
        tag: "STATUTORY DEADLINE",
        action: () => onNavigateToTab("workflow"),
        actionLabel: "Inspect Limitation",
      });
    }
  });

  // Critical / Attention: Unresolved Evidence Gaps
  gaps.forEach((g) => {
    if (g.severity === "CRITICAL" || g.severity === "HIGH") {
      criticalItems.push({
        id: `g-${g.id}`,
        title: `Evidence Gap: ${g.gap_type}`,
        subtitle: g.description,
        tag: "UNSUPPORTED RECORD",
        action: () => handleCreateTaskFromGap(g),
        actionLabel: "+ Procure Proof",
      });
    } else {
      attentionItems.push({
        id: `g-${g.id}`,
        title: `Evidence Gap: ${g.gap_type}`,
        subtitle: g.description,
        tag: "EVIDENCE GAP",
        action: () => handleCreateTaskFromGap(g),
        actionLabel: "+ Create Task",
      });
    }
  });

  // Attention: Unconfirmed AI Suggestions
  tasks.filter((t) => !t.is_confirmed).forEach((t) => {
    attentionItems.push({
      id: `t-unconf-${t.id}`,
      title: `Suggested Task: ${t.title}`,
      subtitle: `Source: ${t.source_type || "Intelligence"} • Priority: ${t.priority}`,
      tag: "CONFIRMATION NEEDED",
      action: () => handleConfirmTask(t.id),
      actionLabel: "✓ Confirm Task",
    });
  });

  deadlines.filter((d) => !d.is_confirmed).forEach((d) => {
    attentionItems.push({
      id: `d-unconf-${d.id}`,
      title: `Suggested Deadline: ${d.title}`,
      subtitle: `Target: ${new Date(d.deadline_at).toLocaleDateString("en-IN")} • Source: ${d.source_type || "Intelligence"}`,
      tag: "CONFIRMATION NEEDED",
      action: () => handleConfirmDeadline(d.id),
      actionLabel: "✓ Confirm Deadline",
    });
  });

  // Routine: Standard Open Tasks
  tasks.filter((t) => t.is_confirmed && t.status !== "COMPLETED").forEach((t) => {
    routineItems.push({
      id: `t-${t.id}`,
      title: t.title,
      subtitle: t.due_date ? `Due: ${new Date(t.due_date).toLocaleDateString("en-IN")}` : "Ongoing case obligation",
      tag: t.priority,
      action: () => handleToggleTask(t.id, t.status),
      actionLabel: "✓ Complete",
    });
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      {/* Action Center Sub-navigation & Header */}
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
              color: "#10b981",
              marginBottom: "4px",
            }}
          >
            <span>⚡</span> Operational Nerve Center
          </div>
          <h2 style={{ fontSize: "22px", fontWeight: 700, color: "var(--text-primary)" }}>
            Case Action & Decision Center
          </h2>
        </div>

        {/* View Switcher */}
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
          <button
            onClick={() => setSubView("QUEUE")}
            className={`btn ${subView === "QUEUE" ? "btn-primary" : "btn-secondary"}`}
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            ⚡ Priority Action Queue ({criticalItems.length + attentionItems.length})
          </button>
          <button
            onClick={() => setSubView("HEARINGS")}
            className={`btn ${subView === "HEARINGS" ? "btn-primary" : "btn-secondary"}`}
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            ⚖ Hearing Command ({hearings.length})
          </button>
          <button
            onClick={() => setSubView("PLAN")}
            className={`btn ${subView === "PLAN" ? "btn-primary" : "btn-secondary"}`}
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            🗺 5-Stage Case Plan
          </button>
          <button
            onClick={() => setSubView("DECISIONS")}
            className={`btn ${subView === "DECISIONS" ? "btn-primary" : "btn-secondary"}`}
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            🛡 Human Decision Register ({decisions.length})
          </button>
          <button
            onClick={handleGenerateSuggestions}
            disabled={generatingSuggestions}
            className="btn btn-secondary"
            style={{ fontSize: "12px", padding: "6px 12px" }}
            title="Derives unconfirmed procedural suggestions from active evidence gaps and timeline findings"
          >
            {generatingSuggestions ? "Synthesizing..." : "⚡ Suggest Actions from Intel"}
          </button>
        </div>
      </div>

      {/* VIEW 1: PRIORITY ACTION QUEUE */}
      {subView === "QUEUE" && (
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "20px", alignItems: "start" }}>
          {/* Main Action Streams */}
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {/* Critical Stream */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
                <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#ef4444" }} />
                <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff" }}>
                  Critical Action Items ({criticalItems.length})
                </h3>
              </div>

              {criticalItems.length === 0 ? (
                <div style={{ padding: "16px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                  No imminent court listings or critical limitation hazards detected.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {criticalItems.map((item) => (
                    <div
                      key={item.id}
                      style={{
                        padding: "14px 16px",
                        borderRadius: "var(--radius-sm)",
                        background: "rgba(239, 68, 68, 0.05)",
                        border: "1px solid rgba(239, 68, 68, 0.25)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "12px",
                      }}
                    >
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontSize: "10px", fontWeight: 700, color: "#ef4444", textTransform: "uppercase" }}>
                            {item.tag}
                          </span>
                          <h4 style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>
                            {item.title}
                          </h4>
                        </div>
                        <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "3px" }}>
                          {item.subtitle}
                        </p>
                      </div>
                      <button
                        onClick={item.action}
                        className="btn btn-primary"
                        style={{ fontSize: "11px", padding: "6px 12px", whiteSpace: "nowrap" }}
                      >
                        {item.actionLabel}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Attention Required Stream */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
                <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#f59e0b" }} />
                <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff" }}>
                  Attention Required ({attentionItems.length})
                </h3>
              </div>

              {attentionItems.length === 0 ? (
                <div style={{ padding: "16px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                  No pending procedural suggestions or secondary evidence gaps.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {attentionItems.map((item) => (
                    <div
                      key={item.id}
                      style={{
                        padding: "12px 14px",
                        borderRadius: "var(--radius-sm)",
                        background: "rgba(245, 158, 11, 0.05)",
                        border: "1px solid rgba(245, 158, 11, 0.2)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: "12px",
                      }}
                    >
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontSize: "10px", fontWeight: 700, color: "#f59e0b", textTransform: "uppercase" }}>
                            {item.tag}
                          </span>
                          <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#fff" }}>
                            {item.title}
                          </h4>
                        </div>
                        <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                          {item.subtitle}
                        </p>
                      </div>
                      <button
                        onClick={item.action}
                        className="btn btn-secondary"
                        style={{ fontSize: "11px", padding: "4px 10px", whiteSpace: "nowrap" }}
                      >
                        {item.actionLabel}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Routine Tasks */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#60a5fa" }} />
                  <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff" }}>
                    Routine Case Tasks ({routineItems.length})
                  </h3>
                </div>
                <button
                  onClick={() => {
                    setTaskModalInitialTitle("");
                    setTaskModalInitialDesc("");
                    setTaskModalInitialPriority("MEDIUM");
                    setTaskModalSourceType("MANUAL");
                    setTaskModalSourceRef(undefined);
                    setTaskModalOpen(true);
                  }}
                  className="btn btn-secondary"
                  style={{ fontSize: "11px", padding: "4px 8px" }}
                >
                  + New Task
                </button>
              </div>

              {routineItems.length === 0 ? (
                <div style={{ padding: "16px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                  All confirmed routine tasks completed.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {routineItems.map((item) => (
                    <div
                      key={item.id}
                      style={{
                        padding: "10px 14px",
                        borderRadius: "var(--radius-sm)",
                        background: "var(--surface-subtle)",
                        border: "1px solid var(--border-subtle)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)" }}>
                          {item.title}
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                          {item.subtitle}
                        </div>
                      </div>
                      <button
                        onClick={item.action}
                        className="btn btn-secondary"
                        style={{ fontSize: "11px", padding: "3px 8px" }}
                      >
                        {item.actionLabel}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Sidebar: Governance & Next Best Action */}
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {/* Quick Action Trigger */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px",
                display: "flex",
                flexDirection: "column",
                gap: "12px",
              }}
            >
              <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--accent-secondary)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                Operational Short-Cuts
              </div>

              <button
                onClick={() => {
                  setDecisionModalInitialTitle("");
                  setDecisionModalOpen(true);
                }}
                className="btn btn-primary"
                style={{ width: "100%", justifyContent: "center" }}
              >
                🛡 Log Strategic Decision
              </button>

              <button
                onClick={() => {
                  setTaskModalInitialTitle("");
                  setTaskModalInitialDesc("");
                  setTaskModalInitialPriority("HIGH");
                  setTaskModalSourceType("MANUAL");
                  setTaskModalSourceRef(undefined);
                  setTaskModalOpen(true);
                }}
                className="btn btn-secondary"
                style={{ width: "100%", justifyContent: "center" }}
              >
                + New Matter Obligation
              </button>
            </div>

            {/* Recent Decisions Card */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <h4 style={{ fontSize: "14px", fontWeight: 700, color: "#fff" }}>
                  Human Decision Register ({decisions.length})
                </h4>
                <button
                  onClick={() => setSubView("DECISIONS")}
                  style={{ background: "none", border: "none", color: "var(--accent-secondary)", fontSize: "11px", cursor: "pointer" }}
                >
                  View All →
                </button>
              </div>

              {decisions.length === 0 ? (
                <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                  No strategic legal decisions formally preserved yet.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {decisions.slice(0, 3).map((dec) => (
                    <div
                      key={dec.id}
                      style={{
                        padding: "10px 12px",
                        borderRadius: "var(--radius-sm)",
                        background: "var(--surface-subtle)",
                        border: "1px solid var(--border-subtle)",
                        fontSize: "12px",
                      }}
                    >
                      <div style={{ fontWeight: 600, color: "#fff" }}>{dec.title}</div>
                      <div style={{ color: "var(--text-muted)", fontSize: "11px", marginTop: "2px" }}>
                        Recorded by {dec.decision_owner} • {new Date(dec.created_at).toLocaleDateString("en-IN")}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* VIEW 2: HEARING COMMAND CENTER */}
      {subView === "HEARINGS" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)" }}>
                Court Hearings Command Center ({hearings.length})
              </h3>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "2px" }}>
                Listing dates, court benches, preparation obligations, and confirmation statuses.
              </p>
            </div>
            <button
              onClick={() => onNavigateToTab("workflow")}
              className="btn btn-secondary"
              style={{ fontSize: "12px" }}
            >
              + Schedule Listing in Workflow
            </button>
          </div>

          {hearings.length === 0 ? (
            <div
              style={{
                padding: "40px 24px",
                textAlign: "center",
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                color: "var(--text-muted)",
              }}
            >
              <div style={{ fontSize: "28px", marginBottom: "8px" }}>⚖</div>
              <h4 style={{ color: "#fff", fontSize: "15px", marginBottom: "4px" }}>No Hearings Scheduled</h4>
              <p style={{ fontSize: "13px" }}>
                Schedule court hearings manually or click &quot;Suggest Actions from Intel&quot; to detect listing notices.
              </p>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: "16px" }}>
              {hearings.map((h) => (
                <HearingCommandCard
                  key={h.id}
                  hearing={h}
                  caseId={caseId}
                  onRefresh={onRefreshWorkflow}
                  onCreatePrepTask={handleCreatePrepTaskFromHearing}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* VIEW 3: 5-STAGE CASE PLAN */}
      {subView === "PLAN" && (
        <CasePlanView
          tasks={tasks}
          deadlines={deadlines}
          hearings={hearings}
          issues={issues}
          facts={facts}
          gaps={gaps}
          onOpenTaskModal={() => {
            setTaskModalInitialTitle("");
            setTaskModalInitialDesc("");
            setTaskModalInitialPriority("HIGH");
            setTaskModalSourceType("MANUAL");
            setTaskModalSourceRef(undefined);
            setTaskModalOpen(true);
          }}
        />
      )}

      {/* VIEW 4: HUMAN DECISION REGISTER */}
      {subView === "DECISIONS" && (
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
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)" }}>
                Human Legal Decision Register ({decisions.length})
              </h3>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "2px" }}>
                Preserves deliberate counsel decisions, strategic concessions, and client instructions.
              </p>
            </div>
            <button
              onClick={() => {
                setDecisionModalInitialTitle("");
                setDecisionModalOpen(true);
              }}
              className="btn btn-primary"
              style={{ fontSize: "12px" }}
            >
              + Log New Decision Record
            </button>
          </div>

          {decisions.length === 0 ? (
            <div style={{ padding: "40px 0", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
              No strategic legal decisions formally preserved yet.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              {decisions.map((dec) => (
                <div
                  key={dec.id}
                  style={{
                    padding: "16px 20px",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--surface-subtle)",
                    border: "1px solid var(--border-subtle)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <h4 style={{ fontSize: "15px", fontWeight: 700, color: "#fff" }}>
                      {dec.title}
                    </h4>
                    <span
                      style={{
                        fontSize: "10px",
                        fontWeight: 700,
                        padding: "2px 6px",
                        borderRadius: "4px",
                        background: "rgba(16, 185, 129, 0.15)",
                        color: "#10b981",
                        border: "1px solid rgba(16, 185, 129, 0.3)",
                      }}
                    >
                      ● FORMAL HUMAN DECISION
                    </span>
                  </div>

                  <div style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                    {dec.rationale}
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--border-subtle)", paddingTop: "8px", marginTop: "4px", fontSize: "11px", color: "var(--text-muted)" }}>
                    <span>Recorded by: {dec.decision_owner}</span>
                    <span>Preserved on {new Date(dec.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Task Composer Modal */}
      <TaskComposerModal
        caseId={caseId}
        isOpen={taskModalOpen}
        onClose={() => setTaskModalOpen(false)}
        onTaskCreated={async () => {
          await onRefreshWorkflow();
        }}
        initialTitle={taskModalInitialTitle}
        initialDescription={taskModalInitialDesc}
        initialPriority={taskModalInitialPriority}
        sourceType={taskModalSourceType}
        sourceReference={taskModalSourceRef}
      />

      {/* Decision Record Modal */}
      <DecisionRecordModal
        caseId={caseId}
        isOpen={decisionModalOpen}
        onClose={() => setDecisionModalOpen(false)}
        onDecisionLogged={async () => {
          await onRefreshNotes();
        }}
        suggestedTitle={decisionModalInitialTitle}
      />
    </div>
  );
}
