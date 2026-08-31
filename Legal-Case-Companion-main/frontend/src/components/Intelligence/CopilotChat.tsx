"use client";

import React, { useState } from "react";
import {
  AIMessageItem,
  AIConversationItem,
  CaseAssistantQueryResponse,
  LegalIssueItem,
  EvidenceGapItem,
} from "@/types";
import { apiClient } from "@/api/client";
import { ClaimVerificationList } from "./ClaimVerificationList";
import { TemporalValidityBadge } from "./TemporalValidityBadge";

interface CopilotChatProps {
  caseId: string;
  conversations: AIConversationItem[];
  activeConvId: string | null;
  messages: AIMessageItem[];
  onSelectConversation: (convId: string) => Promise<void>;
  issues?: LegalIssueItem[];
  gaps?: EvidenceGapItem[];
}

export function CopilotChat({
  caseId,
  conversations,
  activeConvId,
  messages: initialMessages,
  onSelectConversation,
  issues = [],
  gaps = [],
}: CopilotChatProps) {
  const [messages, setMessages] = useState<AIMessageItem[]>(initialMessages);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [includeAuthority, setIncludeAuthority] = useState(true);
  const [searchMode, setSearchMode] = useState<"HYBRID" | "SEMANTIC" | "LEXICAL">("HYBRID");

  // Dynamic context-aware suggested prompts
  const suggestedPrompts: string[] = [];
  if (issues.length > 0) {
    suggestedPrompts.push(`What evidence in the record supports the issue: "${issues[0].issue_text || issues[0].issue_title}"?`);
  }
  if (gaps.length > 0) {
    suggestedPrompts.push(`How does the missing element "${gaps[0].description}" affect our legal standing?`);
  }
  suggestedPrompts.push("Summarize the strongest documentary evidence supporting our claims.");
  suggestedPrompts.push("What statutory limitation deadlines apply under Indian law?");

  const msgIdCounterRef = React.useRef(0);

  const handleSendQuery = React.useCallback(async (queryText?: string) => {
    const textToSend = queryText || query;
    if (!textToSend.trim() || loading) return;

    msgIdCounterRef.current += 1;
    const userMsgId = `temp-${msgIdCounterRef.current}`;
    const userMessage: AIMessageItem = {
      id: userMsgId,
      conversation_id: activeConvId || "default",
      role: "USER",
      content: textToSend.trim(),
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuery("");
    setLoading(true);

    try {
      // Direct call to case assistant query endpoint
      const res: CaseAssistantQueryResponse = await apiClient.post(
        `/api/v1/cases/${caseId}/assistant/query`,
        {
          question: textToSend.trim(),
          top_k: 8,
          search_mode: searchMode,
          include_legal_authority: includeAuthority,
          verify_claims: true,
        }
      );

      msgIdCounterRef.current += 1;
      const aiMessage: AIMessageItem = {
        id: `ai-${msgIdCounterRef.current}`,
        conversation_id: activeConvId || "default",
        role: "ASSISTANT",
        content: res.answer,
        grounding_status: res.grounding_status,
        citations: res.citations,
        authority_citations: res.authority_citations,
        claims: res.claims,
        uncertainties: res.uncertainties,
        warnings: res.warnings,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (err: unknown) {
      console.error("Copilot query failure:", err);
      msgIdCounterRef.current += 1;
      const errMessage: AIMessageItem = {
        id: `err-${msgIdCounterRef.current}`,
        conversation_id: activeConvId || "default",
        role: "ASSISTANT",
        content: "We encountered an issue processing your query against active case materials. Please ensure safe documents are indexed.",
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMessage]);
    } finally {
      setLoading(false);
    }
  }, [activeConvId, caseId, includeAuthority, loading, query, searchMode]);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "240px 1fr",
        gap: "20px",
        height: "720px",
        background: "var(--surface-card)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-md)",
        overflow: "hidden",
      }}
    >
      {/* Sidebar: Conversation Threads */}
      <div
        style={{
          background: "var(--surface-base)",
          borderRight: "1px solid var(--border-subtle)",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          Research Sessions
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "6px", overflowY: "auto", flex: 1 }}>
          {conversations.length === 0 ? (
            <div style={{ fontSize: "12px", color: "var(--text-muted)", padding: "10px 0" }}>
              Active case thread
            </div>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => onSelectConversation(c.id)}
                style={{
                  padding: "8px 10px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  textAlign: "left",
                  background: activeConvId === c.id ? "rgba(79, 91, 247, 0.15)" : "transparent",
                  color: activeConvId === c.id ? "#fff" : "var(--text-secondary)",
                  border: activeConvId === c.id ? "1px solid var(--accent-primary)" : "1px solid transparent",
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                💬 {c.title || "Legal Inquiry"}
              </button>
            ))
          )}
        </div>

        {/* Retrieval Controls */}
        <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
          <label style={{ fontSize: "11px", color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={includeAuthority}
              onChange={(e) => setIncludeAuthority(e.target.checked)}
            />
            Include Indian Statutes
          </label>

          <select
            value={searchMode}
            onChange={(e) => setSearchMode(e.target.value as any)}
            style={{
              padding: "4px 8px",
              borderRadius: "4px",
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-primary)",
              fontSize: "11px",
            }}
          >
            <option value="HYBRID">Hybrid Search</option>
            <option value="SEMANTIC">Semantic Embedding</option>
            <option value="LEXICAL">Lexical BM25</option>
          </select>
        </div>
      </div>

      {/* Main Chat Interface */}
      <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
        {/* Messages Stream */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: "18px" }}>
          {messages.length === 0 ? (
            <div style={{ margin: "auto", textAlign: "center", maxWidth: "480px", color: "var(--text-secondary)" }}>
              <div style={{ fontSize: "32px", marginBottom: "12px" }}>✦</div>
              <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", marginBottom: "6px" }}>
                Grounded Legal Copilot 2.0
              </h3>
              <p style={{ fontSize: "13px", lineHeight: 1.5, marginBottom: "20px" }}>
                Answers are grounded in active case documents and cross-referenced with Indian statutory provisions.
              </p>

              {/* Suggested Prompts */}
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {suggestedPrompts.map((p, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendQuery(p)}
                    style={{
                      padding: "8px 12px",
                      borderRadius: "6px",
                      background: "var(--surface-subtle)",
                      border: "1px solid var(--border-subtle)",
                      color: "var(--text-primary)",
                      fontSize: "12px",
                      textAlign: "left",
                      cursor: "pointer",
                    }}
                  >
                    ✦ {p}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => (
              <div
                key={m.id}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignSelf: m.role === "USER" ? "flex-end" : "flex-start",
                  maxWidth: m.role === "USER" ? "75%" : "95%",
                }}
              >
                {/* Role Header */}
                <div
                  style={{
                    fontSize: "11px",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    color: m.role === "USER" ? "var(--accent-secondary)" : "#10b981",
                    marginBottom: "4px",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <span>{m.role === "USER" ? "Counsel / Client" : "✦ Grounded Legal Copilot"}</span>
                  {m.grounding_status && (
                    <span
                      style={{
                        padding: "1px 6px",
                        borderRadius: "4px",
                        fontSize: "9px",
                        background: m.grounding_status === "SUPPORTED" ? "rgba(16, 185, 129, 0.2)" : "rgba(245, 158, 11, 0.2)",
                        color: m.grounding_status === "SUPPORTED" ? "#10b981" : "#f59e0b",
                      }}
                    >
                      {m.grounding_status}
                    </span>
                  )}
                </div>

                {/* Message Body */}
                <div
                  style={{
                    padding: "14px 18px",
                    borderRadius: "8px",
                    background: m.role === "USER" ? "rgba(79, 91, 247, 0.15)" : "var(--surface-subtle)",
                    border: m.role === "USER" ? "1px solid var(--accent-primary)" : "1px solid var(--border-subtle)",
                    color: "var(--text-primary)",
                    fontSize: "13px",
                    lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {m.content}
                </div>

                {/* SECTION 2: CASE EVIDENCE CITATIONS */}
                {m.citations && m.citations.length > 0 && (
                  <div style={{ marginTop: "10px", padding: "10px 14px", borderRadius: "6px", background: "rgba(59, 130, 246, 0.05)", border: "1px solid rgba(59, 130, 246, 0.2)" }}>
                    <div style={{ fontSize: "11px", fontWeight: 700, color: "#60a5fa", textTransform: "uppercase", marginBottom: "6px" }}>
                      📁 Grounded Case Evidence Citations ({m.citations.length})
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      {m.citations.map((c, idx) => (
                        <div key={idx} style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                          <span style={{ fontWeight: 600, color: "#93c5fd" }}>{c.source_filename}</span>
                          {c.page_start && ` (p. ${c.page_start})`}
                          : &quot;{c.text_snippet.slice(0, 160)}...&quot;
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* SECTION 3: LEGAL AUTHORITIES CITATIONS */}
                {m.authority_citations && m.authority_citations.length > 0 && (
                  <div style={{ marginTop: "10px", padding: "10px 14px", borderRadius: "6px", background: "rgba(109, 124, 255, 0.05)", border: "1px solid rgba(109, 124, 255, 0.2)" }}>
                    <div style={{ fontSize: "11px", fontWeight: 700, color: "#8d98ff", textTransform: "uppercase", marginBottom: "6px" }}>
                      ⚖ Governing Indian Legal Authorities ({m.authority_citations.length})
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {m.authority_citations.map((a, idx) => (
                        <div key={idx} style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2px" }}>
                            <span style={{ fontWeight: 600, color: "#c4b5fd" }}>
                              {a.act_or_judgment_name} • {a.section_or_para}
                            </span>
                            <TemporalValidityBadge
                              effectiveFrom={a.effective_from}
                              effectiveTo={a.effective_to}
                              authorityLevel={a.authority_level}
                              jurisdiction={a.jurisdiction}
                            />
                          </div>
                          <div>&quot;{a.text_snippet.slice(0, 180)}...&quot;</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* SECTION 4: CLAIM VERIFICATION */}
                {m.claims && <ClaimVerificationList claims={m.claims} />}

                {/* SECTION 5: UNCERTAINTIES */}
                {m.uncertainties && m.uncertainties.length > 0 && (
                  <div style={{ marginTop: "8px", padding: "8px 12px", borderRadius: "6px", background: "rgba(245, 158, 11, 0.06)", border: "1px solid rgba(245, 158, 11, 0.2)", fontSize: "11px", color: "#fcd34d" }}>
                    <span style={{ fontWeight: 700 }}>Uncertainty Notice: </span>
                    {m.uncertainties.join(" • ")}
                  </div>
                )}
              </div>
            ))
          )}
          {loading && (
            <div style={{ color: "#8d98ff", fontSize: "12px", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}>
              <span>●</span> Synthesizing answer against case documents and Indian statutes...
            </div>
          )}
        </div>

        {/* Query Input Bar */}
        <div style={{ padding: "16px 20px", borderTop: "1px solid var(--border-subtle)", background: "var(--surface-base)" }}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendQuery();
            }}
            style={{ display: "flex", gap: "10px" }}
          >
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask Copilot about case documents, legal obligations, or governing Indian statutes..."
              className="input-field"
              style={{ flex: 1 }}
            />
            <button type="submit" disabled={loading || !query.trim()} className="btn btn-primary">
              {loading ? "Consulting..." : "Ask Copilot ↗"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
