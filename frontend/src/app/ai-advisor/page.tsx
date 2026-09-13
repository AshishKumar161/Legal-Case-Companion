"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import { AssistantIcon, PlusIcon, ArrowRightIcon, TrashIcon } from "@/components/ui/Icons";
import styles from "./ai-advisor.module.css";

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

interface AdvisorMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  model_version?: string;
  latency_ms?: number;
  created_at: string;
}

interface AdvisorSession {
  id: string;
  title: string | null;
  status: string;
  created_at: string;
}

interface ChatResponse {
  session_id: string;
  session_title: string | null;
  user_message: AdvisorMessage;
  assistant_message: AdvisorMessage;
}

// --------------------------------------------------------------------------
// Constants
// --------------------------------------------------------------------------

const SUGGESTIONS = [
  { emoji: "⚖️", text: "What are my rights if my landlord refuses to return the security deposit?" },
  { emoji: "📜", text: "How can I file a consumer complaint under the Consumer Protection Act?" },
  { emoji: "👨‍👩‍👦", text: "What is the process for filing for divorce under Hindu Marriage Act?" },
  { emoji: "🏢", text: "What legal notice should I send for breach of contract in a business deal?" },
];

// --------------------------------------------------------------------------
// Helper
// --------------------------------------------------------------------------

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

// Simple markdown-ish rendering: bold (**text**), line breaks
function renderContent(text: string) {
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : <React.Fragment key={i}>{part.split("\n").map((line, j, arr) =>
          j < arr.length - 1 ? <React.Fragment key={j}>{line}<br /></React.Fragment> : line
        )}</React.Fragment>
  );
}

// --------------------------------------------------------------------------
// Component
// --------------------------------------------------------------------------

export default function AIAdvisorPage() {
  const { user } = useAuth();

  const [sessions, setSessions] = useState<AdvisorSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<AdvisorMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Scroll to bottom on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, loading]);

  // Load sessions list
  const loadSessions = useCallback(async () => {
    try {
      const data = await apiClient.get<AdvisorSession[]>("/api/v1/advisor/sessions");
      setSessions(data);
    } catch {
      // Non-critical, fail silently
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Load messages for a session
  const loadMessages = useCallback(async (sessionId: string) => {
    setLoadingHistory(true);
    setError(null);
    try {
      const data = await apiClient.get<AdvisorMessage[]>(
        `/api/v1/advisor/sessions/${sessionId}/messages`
      );
      setMessages(data);
    } catch {
      setError("Failed to load conversation history.");
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const selectSession = useCallback(
    (sessionId: string) => {
      setActiveSessionId(sessionId);
      loadMessages(sessionId);
    },
    [loadMessages]
  );

  const [deletingId, setDeletingId] = useState<string | null>(null);

  const startNewChat = useCallback(() => {
    setActiveSessionId(null);
    setMessages([]);
    setInput("");
    setError(null);
    textareaRef.current?.focus();
  }, []);

  const handleDeleteSession = useCallback(
    async (e: React.MouseEvent, sessionId: string) => {
      e.stopPropagation();
      if (!window.confirm("Are you sure you want to delete this chat conversation?")) {
        return;
      }
      setDeletingId(sessionId);
      try {
        await apiClient.delete(`/api/v1/advisor/sessions/${sessionId}`);
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        if (activeSessionId === sessionId) {
          startNewChat();
        }
      } catch (err) {
        console.error("Failed to delete session:", err);
        setError("Failed to delete conversation. Please try again.");
      } finally {
        setDeletingId(null);
      }
    },
    [activeSessionId, startNewChat]
  );


  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      setInput("");
      setError(null);
      setLoading(true);
      if (textareaRef.current) textareaRef.current.style.height = "auto";

      // Optimistic user bubble
      const optimisticUser: AdvisorMessage = {
        id: `opt-${Date.now()}`,
        session_id: activeSessionId ?? "",
        role: "user",
        content: trimmed,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, optimisticUser]);

      try {
        const res = await apiClient.post<ChatResponse>("/api/v1/advisor/chat", {
          message: trimmed,
          session_id: activeSessionId,
        });

        // Replace optimistic + add assistant
        setMessages((prev) => [
          ...prev.filter((m) => m.id !== optimisticUser.id),
          res.user_message,
          res.assistant_message,
        ]);

        // Update session context
        if (!activeSessionId) {
          setActiveSessionId(res.session_id);
          setSessions((prev) => [
            { id: res.session_id, title: res.session_title, status: "ACTIVE", created_at: new Date().toISOString() },
            ...prev.filter((s) => s.id !== res.session_id),
          ]);
        }
      } catch (err: unknown) {
        const msg =
          err instanceof Error ? err.message : "Something went wrong. Please try again.";
        setError(msg);
        // Remove optimistic bubble on error
        setMessages((prev) => prev.filter((m) => m.id !== optimisticUser.id));
      } finally {
        setLoading(false);
      }
    },
    [loading, activeSessionId]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const initials = user?.full_name?.charAt(0)?.toUpperCase() ?? user?.email?.charAt(0)?.toUpperCase() ?? "U";
  const showWelcome = messages.length === 0 && !loadingHistory;

  return (
    <div className={styles.pageRoot}>
      {/* Session History Sidebar */}
      <aside className={styles.historyPanel}>
        <div className={styles.historyHeader}>
          <p className={styles.historyTitle}>Recent Chats</p>
          <button className={styles.newChatBtn} onClick={startNewChat}>
            <PlusIcon size={14} />
            New conversation
          </button>
        </div>
        <div className={styles.sessionList}>
          {sessions.length === 0 && (
            <p style={{ fontSize: 12, color: "var(--text-subtle)", padding: "12px 10px" }}>
              Your conversations will appear here
            </p>
          )}
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`${styles.sessionItemRow} ${s.id === activeSessionId ? styles.sessionItemRowActive : ""}`}
            >
              <button
                className={styles.sessionItem}
                onClick={() => selectSession(s.id)}
                title={s.title ?? "Legal Inquiry"}
              >
                <span className={styles.sessionDot} />
                <span className={styles.sessionTitle}>{s.title ?? "Legal Inquiry"}</span>
              </button>
              <button
                className={styles.sessionDeleteBtn}
                onClick={(e) => handleDeleteSession(e, s.id)}
                disabled={deletingId === s.id}
                title="Delete chat"
                aria-label={`Delete chat ${s.title ?? "Legal Inquiry"}`}
              >
                <TrashIcon size={14} />
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className={styles.chatMain}>
        {/* Header */}
        <header className={styles.chatHeader}>
          <div className={styles.chatHeaderIcon}>
            <AssistantIcon size={22} />
          </div>
          <div className={styles.chatHeaderInfo}>
            <h1 className={styles.chatHeaderTitle}>Lex — Legal AI Advisor</h1>
            <p className={styles.chatHeaderSub}>
              Powered by Legal Case Companion · Indian Law · General Information Only
            </p>
          </div>
          <div className={styles.headerActions}>
            {activeSessionId && (
              <button
                className={styles.deleteChatBtn}
                onClick={(e) => handleDeleteSession(e, activeSessionId)}
                title="Delete this conversation"
                disabled={deletingId === activeSessionId}
              >
                <TrashIcon size={14} />
                <span>Delete chat</span>
              </button>
            )}
            <div className={styles.modelBadge}>
              <span className={styles.modelDot} />
              <span>AI Model</span>
            </div>
          </div>
        </header>

        {/* Messages */}
        <div className={styles.messageList} role="log" aria-live="polite">
          {showWelcome ? (
            <div className={styles.welcomeState}>
              <div className={styles.welcomeIcon}>
                <AssistantIcon size={34} />
              </div>
              <div>
                <h2 className={styles.welcomeTitle}>Ask Lex anything about Indian law</h2>
                <p className={styles.welcomeSub}>
                  Get clear, plain-language answers on legal procedures, rights, and remedies.
                  Always powered by verified Indian legal sources.
                </p>
              </div>
              <div className={styles.suggestions}>
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    className={styles.suggestionCard}
                    onClick={() => sendMessage(s.text)}
                  >
                    <span className={styles.suggestionEmoji}>{s.emoji}</span>
                    {s.text}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {loadingHistory && (
                <div style={{ textAlign: "center", color: "var(--text-subtle)", fontSize: 13 }}>
                  Loading history…
                </div>
              )}
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`${styles.messageRow} ${msg.role === "user" ? styles.messageRowUser : ""}`}
                >
                  <div
                    className={`${styles.avatar} ${msg.role === "user" ? styles.avatarUser : styles.avatarAI}`}
                  >
                    {msg.role === "user" ? initials : <AssistantIcon size={16} />}
                  </div>
                  <div
                    className={`${styles.bubble} ${msg.role === "user" ? styles.bubbleUser : styles.bubbleAI}`}
                  >
                    {renderContent(msg.content)}
                    <span
                      className={`${styles.bubbleTime} ${msg.role !== "user" ? styles.bubbleTimeAI : ""}`}
                    >
                      {formatTime(msg.created_at)}
                      {msg.model_version && msg.model_version !== "stub" && (
                        <> · {msg.model_version}</>
                      )}
                    </span>
                  </div>
                </div>
              ))}

              {/* Typing indicator */}
              {loading && (
                <div className={styles.typingRow}>
                  <div className={`${styles.avatar} ${styles.avatarAI}`}>
                    <AssistantIcon size={16} />
                  </div>
                  <div className={styles.typingBubble}>
                    <div className={styles.typingDot} />
                    <div className={styles.typingDot} />
                    <div className={styles.typingDot} />
                  </div>
                </div>
              )}
            </>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input Area */}
        <div className={styles.inputArea}>
          {error && <div className={styles.errorBanner}>{error}</div>}
          <p className={styles.inputDisclaimer}>
            ⚠️ Lex provides general legal information, not formal legal advice. For your specific case, consult a verified advocate.
          </p>
          <div className={styles.inputRow}>
            <textarea
              ref={textareaRef}
              className={styles.inputTextarea}
              id="ai-advisor-input"
              placeholder="Ask about your legal rights, procedures, or any Indian law topic… (Enter to send, Shift+Enter for new line)"
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={loading}
              aria-label="Message to Lex"
            />
            <button
              id="ai-advisor-send-btn"
              className={styles.sendBtn}
              onClick={() => sendMessage(input)}
              disabled={loading || !input.trim()}
              aria-label="Send message"
            >
              <ArrowRightIcon size={16} />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
