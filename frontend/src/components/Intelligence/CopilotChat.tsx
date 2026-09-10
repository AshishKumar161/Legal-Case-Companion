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
import Image from "next/image";
import {
  ScalesIcon,
  AssistantIcon,
} from "@/components/ui/Icons";
import styles from "./CopilotChat.module.css";

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
}: CopilotChatProps) {
  const [messages, setMessages] = useState<AIMessageItem[]>(initialMessages);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [includeAuthority, setIncludeAuthority] = useState(true);
  const [searchMode, setSearchMode] = useState<"HYBRID" | "SEMANTIC" | "LEXICAL">("HYBRID");
  const [showAdvancedSearch, setShowAdvancedSearch] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});

  // Human-friendly suggested prompts (Section 12)
  const defaultPrompts = [
    "What happens at my next hearing?",
    "Explain my latest court order",
    "What documents do I need?",
    "What should I ask my lawyer?",
    "What is happening with my case?",
  ];

  const msgIdCounterRef = React.useRef(0);

  const toggleSourceView = (id: string) => {
    setExpandedSources((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleSendQuery = React.useCallback(
    async (queryText?: string) => {
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
        console.error("Assistant query failure:", err);
        msgIdCounterRef.current += 1;
        const errMessage: AIMessageItem = {
          id: `err-${msgIdCounterRef.current}`,
          conversation_id: activeConvId || "default",
          role: "ASSISTANT",
          content:
            "I could not retrieve the details for this query right now. Please ensure your documents are uploaded safely or ask your lawyer for direct guidance.",
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errMessage]);
      } finally {
        setLoading(false);
      }
    },
    [activeConvId, caseId, includeAuthority, loading, query, searchMode]
  );

  return (
    <div className={styles.container}>
      {/* Sidebar: Past conversations */}
      <div className={styles.sidebar}>
        <div className={styles.sidebarTitle}>Past Questions</div>

        <div className={styles.threadList}>
          {conversations.length === 0 ? (
            <div style={{ fontSize: "12px", color: "var(--text-muted)", padding: "8px 0" }}>
              Current case conversation
            </div>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => onSelectConversation(c.id)}
                className={`${styles.threadBtn} ${activeConvId === c.id ? styles.threadBtnActive : ""}`}
              >
                {c.title || "Case Question"}
              </button>
            ))
          )}
        </div>

        {/* Progressive Disclosure for Search Settings */}
        <div className={styles.advancedBox}>
          <button
            type="button"
            onClick={() => setShowAdvancedSearch(!showAdvancedSearch)}
            style={{
              background: "none",
              border: "none",
              color: "var(--text-secondary)",
              fontSize: "11px",
              cursor: "pointer",
              padding: 0,
              fontWeight: 600,
            }}
          >
            {showAdvancedSearch ? "Hide search options ▲" : "Search options ▼"}
          </button>

          {showAdvancedSearch && (
            <div style={{ marginTop: "10px", display: "flex", flexDirection: "column", gap: "8px" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={includeAuthority}
                  onChange={(e) => setIncludeAuthority(e.target.checked)}
                />
                Include legal statutes
              </label>

              <select
                value={searchMode}
                onChange={(e) => setSearchMode(e.target.value as any)}
                style={{
                  padding: "4px 8px",
                  borderRadius: "4px",
                  border: "1px solid var(--border-subtle)",
                  fontSize: "11px",
                  background: "#FFFFFF",
                }}
              >
                <option value="HYBRID">Hybrid Search</option>
                <option value="SEMANTIC">Semantic Embedding</option>
                <option value="LEXICAL">Exact Match</option>
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Main Chat Interface */}
      <div className={styles.mainChat}>
        {/* Header (Section 12) */}
        <div className={styles.chatHeader}>
          <div className={styles.chatTitle}>
            <Image
              src="/logo-icon.png"
              alt="LCC Assistant"
              width={22}
              height={22}
              style={{ objectFit: "contain" }}
            />
            <span>LCC Legal Assistant</span>
          </div>
          <div className={styles.onlineBadge}>
            <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "var(--status-success)" }} />
            <span>Ready to help · Hindi & English</span>
          </div>
        </div>

        {/* Messages Stream */}
        <div className={styles.messagesArea}>
          {messages.length === 0 ? (
            /* Welcome State (Section 12) */
            <div className={styles.welcomeContainer}>
              <div className={styles.welcomeIcon}>
                <AssistantIcon size={26} color="var(--navy-primary)" />
              </div>
              <h2 className={styles.welcomeGreeting}>Hello.</h2>
              <p className={styles.welcomeDesc}>
                I can help you understand your case. What would you like to know?
              </p>

              {/* 5 Prompts from Section 12 */}
              <div className={styles.promptList}>
                {defaultPrompts.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className={styles.promptBtn}
                    onClick={() => handleSendQuery(p)}
                  >
                    <span>{p}</span>
                    <span style={{ color: "var(--navy-primary)", fontWeight: 700 }}>→</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => {
              const isUser = m.role === "USER";
              const hasSources =
                (m.citations && m.citations.length > 0) ||
                (m.authority_citations && m.authority_citations.length > 0) ||
                (m.claims && m.claims.length > 0);
              const sourcesOpen = !!expandedSources[m.id];

              return (
                <div
                  key={m.id}
                  className={`${styles.messageRow} ${isUser ? styles.userRow : styles.assistantRow}`}
                >
                  <div className={styles.messageSender}>
                    {isUser ? (
                      <span>You</span>
                    ) : (
                      <>
                        <ScalesIcon size={14} color="var(--gold-accent)" />
                        <span style={{ color: "var(--navy-primary)" }}>LCC Legal Assistant</span>
                      </>
                    )}
                  </div>

                  <div className={isUser ? styles.userBubble : styles.assistantBubble}>
                    {m.content}
                  </div>

                  {/* Progressive Disclosure for Citations and Proof (Section 13) */}
                  {!isUser && hasSources && (
                    <div>
                      <button
                        type="button"
                        className={styles.disclosureBtn}
                        onClick={() => toggleSourceView(m.id)}
                      >
                        {sourcesOpen ? "Hide referenced documents & legal sources ▲" : "View referenced documents & legal sources ▼"}
                      </button>

                      {sourcesOpen && (
                        <div className={styles.citationsBox}>
                          {m.citations && m.citations.length > 0 && (
                            <div style={{ marginBottom: "10px" }}>
                              <strong style={{ color: "var(--navy-primary)", display: "block", marginBottom: "4px" }}>
                                Case Documents Referenced:
                              </strong>
                              {m.citations.map((c, idx) => (
                                <div key={idx} style={{ color: "var(--text-secondary)", marginBottom: "4px" }}>
                                  📄 <strong>{c.source_filename}</strong> {c.page_start ? `(page ${c.page_start})` : ""}: &quot;{c.text_snippet.slice(0, 140)}...&quot;
                                </div>
                              ))}
                            </div>
                          )}

                          {m.authority_citations && m.authority_citations.length > 0 && (
                            <div style={{ marginBottom: "10px" }}>
                              <strong style={{ color: "var(--navy-primary)", display: "block", marginBottom: "4px" }}>
                                Legal Sources & Statutes:
                              </strong>
                              {m.authority_citations.map((a, idx) => (
                                <div key={idx} style={{ color: "var(--text-secondary)", marginBottom: "4px" }}>
                                  ⚖️ <strong>{a.act_or_judgment_name}</strong> ({a.section_or_para}): &quot;{a.text_snippet.slice(0, 140)}...&quot;
                                </div>
                              ))}
                            </div>
                          )}

                          {m.claims && <ClaimVerificationList claims={m.claims} />}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}

          {loading && (
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--navy-primary)", fontSize: "13px", fontWeight: 600 }}>
              <span className="spinner-border" style={{ width: "16px", height: "16px" }} />
              <span>Reviewing case documents and legal provisions...</span>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className={styles.inputContainer}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void handleSendQuery();
            }}
            className={styles.chatForm}
          >
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a question about your case in plain English or Hindi..."
              className={styles.chatInput}
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className={styles.sendBtn}
            >
              {loading ? "Thinking..." : "Ask LCC →"}
            </button>
          </form>
          <div className={styles.disclaimerText}>
            LCC explains legal documents and court steps in simple terms. This is legal information, not a substitute for advice from your licensed advocate.
          </div>
        </div>
      </div>
    </div>
  );
}
