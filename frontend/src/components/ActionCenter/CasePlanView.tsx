"use client";

import React from "react";
import {
  CaseTaskItem,
  CaseDeadlineItem,
  CaseHearingItem,
  LegalIssueItem,
  CaseFactItem,
  EvidenceGapItem,
} from "@/types";
import { StatusBadge } from "@/components/StatusBadge";

interface CasePlanViewProps {
  tasks: CaseTaskItem[];
  deadlines: CaseDeadlineItem[];
  hearings: CaseHearingItem[];
  issues: LegalIssueItem[];
  facts: CaseFactItem[];
  gaps: EvidenceGapItem[];
  onOpenTaskModal: () => void;
}

export function CasePlanView({
  tasks,
  deadlines,
  hearings,
  issues,
  facts,
  gaps,
  onOpenTaskModal,
}: CasePlanViewProps) {
  const openTasks = tasks.filter((t) => t.status !== "COMPLETED" && t.status !== "CANCELLED");
  const completedTasks = tasks.filter((t) => t.status === "COMPLETED");
  const upcomingHearings = hearings.filter((h) => h.status === "SCHEDULED");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Plan Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)" }}>
            5-Stage Living Case Operational Plan
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "2px" }}>
            Synthesizes current legal standing, active litigation milestones, immediate obligations, and completed phases.
          </p>
        </div>
        <button onClick={onOpenTaskModal} className="btn btn-primary" style={{ fontSize: "12px" }}>
          + Add Operational Milestone
        </button>
      </div>

      {/* 5-Phase Roadmap Grid */}
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {/* Phase 1: Established Legal Facts */}
        <div
          style={{
            padding: "18px 20px",
            borderRadius: "var(--radius-md)",
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ width: "22px", height: "22px", borderRadius: "50%", background: "#10b981", color: "#000", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: "12px" }}>
                1
              </span>
              <h4 style={{ fontSize: "15px", fontWeight: 700, color: "#fff" }}>
                Current Established Position ({facts.length} Facts on Record)
              </h4>
            </div>
            <span style={{ fontSize: "12px", color: "#10b981", fontWeight: 600 }}>Grounded</span>
          </div>

          <div style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5 }}>
            {facts.length === 0 ? (
              <div>No substantiated facts established yet. Upload primary contracts or pleadings.</div>
            ) : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                {facts.slice(0, 4).map((f) => (
                  <span
                    key={f.id}
                    style={{
                      padding: "4px 8px",
                      borderRadius: "4px",
                      background: "var(--surface-subtle)",
                      border: "1px solid var(--border-subtle)",
                      fontSize: "12px",
                      color: "var(--text-primary)",
                    }}
                  >
                    ● {f.fact_text ? f.fact_text.slice(0, 60) + "..." : "Fact statement"}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Phase 2: Open Legal Controversies */}
        <div
          style={{
            padding: "18px 20px",
            borderRadius: "var(--radius-md)",
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ width: "22px", height: "22px", borderRadius: "50%", background: "#f59e0b", color: "#000", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: "12px" }}>
                2
              </span>
              <h4 style={{ fontSize: "15px", fontWeight: 700, color: "#fff" }}>
                Contested Legal Issues & Evidence Gaps ({issues.length} Issues · {gaps.length} Gaps)
              </h4>
            </div>
            <span style={{ fontSize: "12px", color: "#f59e0b", fontWeight: 600 }}>Active Dispute</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {issues.map((iss) => (
              <div key={iss.id} style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                ⚖ <b>{iss.issue_text || iss.issue_title}</b>: {iss.issue_description || "Controversy pending trial / determination"}
              </div>
            ))}
          </div>
        </div>

        {/* Phase 3: Immediate Operational Actions */}
        <div
          style={{
            padding: "18px 20px",
            borderRadius: "var(--radius-md)",
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ width: "22px", height: "22px", borderRadius: "50%", background: "#4f5bf7", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: "12px" }}>
                3
              </span>
              <h4 style={{ fontSize: "15px", fontWeight: 700, color: "#fff" }}>
                Immediate Operational Actions ({openTasks.length} Active Tasks)
              </h4>
            </div>
            <span style={{ fontSize: "12px", color: "#8d98ff", fontWeight: 600 }}>In Progress</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {openTasks.length === 0 ? (
              <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>All active tasks satisfied.</div>
            ) : (
              openTasks.map((t) => (
                <div key={t.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "13px" }}>
                  <span style={{ color: "var(--text-primary)" }}>• {t.title}</span>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <StatusBadge status={t.priority} />
                    {t.due_date && <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>Due: {new Date(t.due_date).toLocaleDateString("en-IN")}</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Phase 4: Upcoming Milestones */}
        <div
          style={{
            padding: "18px 20px",
            borderRadius: "var(--radius-md)",
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ width: "22px", height: "22px", borderRadius: "50%", background: "#8b5cf6", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: "12px" }}>
                4
              </span>
              <h4 style={{ fontSize: "15px", fontWeight: 700, color: "#fff" }}>
                Upcoming Milestones & Court Listings ({upcomingHearings.length} Hearings · {deadlines.length} Deadlines)
              </h4>
            </div>
            <span style={{ fontSize: "12px", color: "#c4b5fd", fontWeight: 600 }}>Scheduled</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {upcomingHearings.map((h) => (
              <div key={h.id} style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                📅 <b>{h.court_name}</b> on {new Date(h.hearing_at).toLocaleDateString("en-IN")}: {h.purpose}
              </div>
            ))}
            {deadlines.map((d) => (
              <div key={d.id} style={{ fontSize: "13px", color: "var(--text-primary)" }}>
                ⏱ <b>{d.title}</b> ({d.deadline_type}) due on {new Date(d.deadline_at).toLocaleDateString("en-IN")}
              </div>
            ))}
          </div>
        </div>

        {/* Phase 5: Completed Phases */}
        <div
          style={{
            padding: "18px 20px",
            borderRadius: "var(--radius-md)",
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ width: "22px", height: "22px", borderRadius: "50%", background: "rgba(255, 255, 255, 0.2)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: "12px" }}>
                ✓
              </span>
              <h4 style={{ fontSize: "15px", fontWeight: 700, color: "#fff" }}>
                Satisfied & Completed Milestones ({completedTasks.length})
              </h4>
            </div>
            <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>Archived</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            {completedTasks.length === 0 ? (
              <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>No completed tasks recorded yet.</div>
            ) : (
              completedTasks.map((t) => (
                <div key={t.id} style={{ fontSize: "13px", color: "var(--text-secondary)", textDecoration: "line-through" }}>
                  ✓ {t.title}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
