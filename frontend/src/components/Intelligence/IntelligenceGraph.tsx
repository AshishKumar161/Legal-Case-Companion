"use client";

import React, { useState } from "react";
import { CaseFactItem, LegalIssueItem, CaseParticipantItem } from "@/types";

interface GraphNode {
  id: string;
  label: string;
  type: "CASE" | "PARTICIPANT" | "ISSUE" | "FACT" | "AUTHORITY";
  subLabel?: string;
  color: string;
  details?: Record<string, unknown>;
}

interface GraphLink {
  source: string;
  target: string;
  label: string;
}

interface IntelligenceGraphProps {
  caseTitle: string;
  caseId: string;
  participants: CaseParticipantItem[];
  issues: LegalIssueItem[];
  facts: CaseFactItem[];
  onSelectNode?: (node: GraphNode) => void;
}

export function IntelligenceGraph({
  caseTitle,
  caseId,
  participants,
  issues,
  facts,
  onSelectNode,
}: IntelligenceGraphProps) {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [filterType, setFilterType] = useState<string>("ALL");

  // Construct real deterministic nodes
  const nodes: GraphNode[] = [
    {
      id: `case-${caseId}`,
      label: caseTitle,
      type: "CASE",
      subLabel: `REF #${caseId.slice(0, 8).toUpperCase()}`,
      color: "#4f5bf7",
    },
  ];

  const links: GraphLink[] = [];

  // Add Participant nodes
  participants.slice(0, 5).forEach((p) => {
    const pId = `part-${p.id}`;
    nodes.push({
      id: pId,
      label: p.user?.full_name || p.user?.email || "Participant",
      type: "PARTICIPANT",
      subLabel: p.participant_role || "Counsel / Party",
      color: "#10b981",
      details: { role: p.participant_role, email: p.user?.email },
    });
    links.push({
      source: `case-${caseId}`,
      target: pId,
      label: "PARTY_TO",
    });
  });

  // Add Issue nodes
  issues.slice(0, 6).forEach((iss) => {
    const issId = `issue-${iss.id}`;
    nodes.push({
      id: issId,
      label: iss.issue_text || iss.issue_title || "Contested Issue",
      type: "ISSUE",
      subLabel: iss.category || "Legal Controversy",
      color: "#f59e0b",
      details: { status: iss.status, description: iss.issue_description },
    });
    links.push({
      source: `case-${caseId}`,
      target: issId,
      label: "DISPUTES",
    });

    // Link Authorities if present
    if (iss.relevant_authority_ids) {
      iss.relevant_authority_ids.slice(0, 2).forEach((authId) => {
        const aId = `auth-${authId}`;
        if (!nodes.find((n) => n.id === aId)) {
          nodes.push({
            id: aId,
            label: authId,
            type: "AUTHORITY",
            subLabel: "Indian Statute / Precedent",
            color: "#8d98ff",
          });
        }
        links.push({
          source: issId,
          target: aId,
          label: "GOVERNED_BY",
        });
      });
    }
  });

  // Add Fact / Evidence nodes
  facts.slice(0, 6).forEach((f) => {
    const fId = `fact-${f.id}`;
    nodes.push({
      id: fId,
      label: f.fact_text ? f.fact_text.slice(0, 50) + "..." : "Extracted Fact",
      type: "FACT",
      subLabel: f.source_filename || "Case Document",
      color: "#60a5fa",
      details: {
        source_filename: f.source_filename,
        verification: f.verification_status,
      },
    });
    links.push({
      source: `case-${caseId}`,
      target: fId,
      label: "SUBSTANTIATED_BY",
    });
  });

  const filteredNodes = nodes.filter((n) => {
    if (filterType === "ALL") return true;
    return n.type === filterType;
  });

  const handleNodeClick = (node: GraphNode) => {
    setSelectedNode(node);
    if (onSelectNode) onSelectNode(node);
  };

  return (
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
      {/* Top Filter & Legend Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          borderBottom: "1px solid var(--border-subtle)",
          paddingBottom: "12px",
        }}
      >
        <div style={{ display: "flex", gap: "6px" }}>
          {["ALL", "ISSUE", "FACT", "PARTICIPANT", "AUTHORITY"].map((t) => (
            <button
              key={t}
              onClick={() => setFilterType(t)}
              style={{
                padding: "4px 10px",
                borderRadius: "4px",
                fontSize: "11px",
                fontWeight: 600,
                background: filterType === t ? "var(--surface-hover)" : "transparent",
                color: filterType === t ? "#fff" : "var(--text-secondary)",
                border: filterType === t ? "1px solid var(--border-hover)" : "1px solid transparent",
                cursor: "pointer",
              }}
            >
              {t === "ALL" ? "All Entities" : t}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "14px", fontSize: "11px", color: "var(--text-muted)" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#4f5bf7" }} /> Case
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#f59e0b" }} /> Issue
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#60a5fa" }} /> Evidence Fact
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#8d98ff" }} /> Statute
          </span>
        </div>
      </div>

      {/* Main Canvas & Details Split */}
      <div style={{ display: "grid", gridTemplateColumns: selectedNode ? "2fr 1fr" : "1fr", gap: "16px" }}>
        {/* Node Grid representation */}
        <div
          style={{
            background: "var(--surface-base)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-sm)",
            padding: "20px",
            minHeight: "360px",
            display: "flex",
            flexWrap: "wrap",
            gap: "12px",
            alignContent: "flex-start",
          }}
        >
          {filteredNodes.map((node) => {
            const isSel = selectedNode?.id === node.id;
            return (
              <div
                key={node.id}
                onClick={() => handleNodeClick(node)}
                style={{
                  padding: "10px 14px",
                  borderRadius: "8px",
                  background: isSel ? "rgba(79, 91, 247, 0.15)" : "var(--surface-card)",
                  border: isSel ? `1.5px solid ${node.color}` : "1px solid var(--border-subtle)",
                  cursor: "pointer",
                  maxWidth: "280px",
                  transition: "all 0.15s ease",
                  display: "flex",
                  flexDirection: "column",
                  gap: "3px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: node.color }} />
                  <span style={{ fontSize: "10px", fontWeight: 700, color: node.color, textTransform: "uppercase" }}>
                    {node.type}
                  </span>
                </div>
                <div style={{ fontSize: "13px", fontWeight: 600, color: "#fff", lineHeight: 1.3 }}>
                  {node.label}
                </div>
                {node.subLabel && (
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                    {node.subLabel}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Selected Entity Drawer */}
        {selectedNode && (
          <div
            style={{
              background: "var(--surface-subtle)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-sm)",
              padding: "16px",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "11px", fontWeight: 700, color: selectedNode.color, textTransform: "uppercase" }}>
                Entity Inspector
              </span>
              <button
                onClick={() => setSelectedNode(null)}
                style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "16px" }}
              >
                ✕
              </button>
            </div>

            <div>
              <h4 style={{ fontSize: "15px", fontWeight: 700, color: "#fff" }}>
                {selectedNode.label}
              </h4>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px" }}>
                Type: {selectedNode.type}
              </div>
            </div>

            {selectedNode.details && (
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", fontSize: "12px" }}>
                {Object.entries(selectedNode.details).map(([k, v]) => (
                  <div key={k} style={{ color: "var(--text-secondary)" }}>
                    <span style={{ color: "var(--text-muted)", textTransform: "capitalize" }}>{k.replace(/_/g, " ")}: </span>
                    <span style={{ color: "var(--text-primary)" }}>{String(v)}</span>
                  </div>
                ))}
              </div>
            )}

            <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "12px", marginTop: "auto" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                Relationships mapped from real evidence records & statutory citations.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
