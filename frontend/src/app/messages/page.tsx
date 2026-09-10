"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/AuthProvider";
import { Card, Button, Avatar, Badge, EmptyState } from "@/components/ui";
import { apiClient } from "@/api/client";

interface Thread {
  id: string;
  partnerId: string;
  senderName: string;
  senderRole: "client" | "lawyer" | "admin";
  lastMessage: string;
  timestamp: string;
  unreadCount: number;
  caseRef: string;
  caseId?: string | null;
  caseTitle?: string | null;
}

interface MessageItem {
  id: string;
  senderId: string;
  recipientId: string;
  senderName: string;
  senderRole: "client" | "lawyer" | "admin";
  content: string;
  isRead: boolean;
  isOutgoing: boolean;
  timestamp: string;
  createdAt: string;
}

interface ThreadDetailsResponse {
  partner: {
    id: string;
    name: string;
    role: "client" | "lawyer" | "admin";
    caseRef: string;
    caseId?: string | null;
    caseTitle?: string | null;
    cases?: Array<{ id: string; title: string; caseRef: string }>;
  };
  messages: MessageItem[];
}

export default function MessagesPage() {
  const { user } = useAuth();
  const isLawyer = user?.role === "LAWYER";

  const [threads, setThreads] = useState<Thread[]>([]);
  const [loadingThreads, setLoadingThreads] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [activePartnerId, setActivePartnerId] = useState<string | null>(null);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const [partnerCases, setPartnerCases] = useState<Array<{ id: string; title: string; caseRef: string }>>([]);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [loadingMessages, setLoadingMessages] = useState<boolean>(false);
  const [messageInput, setMessageInput] = useState<string>("");
  const [isSending, setIsSending] = useState<boolean>(false);

  const chatScrollRef = useRef<HTMLDivElement>(null);
  const activePartnerIdRef = useRef<string | null>(null);

  useEffect(() => {
    activePartnerIdRef.current = activePartnerId;
  }, [activePartnerId]);

  // Auto-scroll chat container to bottom
  const scrollToBottom = useCallback((smooth = true) => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTo({
        top: chatScrollRef.current.scrollHeight,
        behavior: smooth ? "smooth" : "auto",
      });
    }
  }, []);

  // Fetch threads list
  const fetchThreads = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoadingThreads(true);
      const data = (await apiClient.get("/api/v1/messages/threads")) as Thread[];
      if (Array.isArray(data)) {
        setThreads(data);
        // Default to first thread if none active yet
        if (!activePartnerIdRef.current && data.length > 0) {
          setActivePartnerId(data[0].partnerId || data[0].id);
        }
      }
    } catch (err) {
      console.error("Failed to load message threads:", err);
    } finally {
      if (!silent) setLoadingThreads(false);
    }
  }, []);

  const router = useRouter();

  // Fetch messages for active thread
  const fetchActiveMessages = useCallback(async (partnerId: string, silent = false) => {
    try {
      if (!silent) setLoadingMessages(true);
      const res = (await apiClient.get(
        `/api/v1/messages/threads/${partnerId}`
      )) as ThreadDetailsResponse;
      if (res && res.partner) {
        if (res.partner.cases && res.partner.cases.length > 0) {
          setPartnerCases(res.partner.cases);
          setActiveCaseId((prev) => prev || res.partner.caseId || res.partner.cases![0].id);
        } else if (res.partner.caseId) {
          setActiveCaseId((prev) => prev || res.partner.caseId || null);
          setPartnerCases([{
            id: res.partner.caseId,
            title: res.partner.caseTitle || "Active Matter",
            caseRef: res.partner.caseRef || "Matter",
          }]);
        }
      }
      if (res && Array.isArray(res.messages)) {
        setMessages(res.messages);
        setTimeout(() => scrollToBottom(!silent), 50);
      }
    } catch (err) {
      console.error(`Failed to fetch messages with ${partnerId}:`, err);
    } finally {
      if (!silent) setLoadingMessages(false);
    }
  }, [scrollToBottom]);

  // Initial load
  useEffect(() => {
    fetchThreads();
  }, [fetchThreads]);

  // Load messages when active partner changes
  useEffect(() => {
    if (activePartnerId) {
      fetchActiveMessages(activePartnerId);
    } else {
      setMessages([]);
    }
  }, [activePartnerId, fetchActiveMessages]);

  // Background polling every 3.5s for real-time responsiveness
  useEffect(() => {
    const interval = setInterval(() => {
      fetchThreads(true);
      if (activePartnerIdRef.current) {
        fetchActiveMessages(activePartnerIdRef.current, true);
      }
    }, 3500);

    return () => clearInterval(interval);
  }, [fetchThreads, fetchActiveMessages]);

  // Send message
  const handleSendMessage = async () => {
    const trimmed = messageInput.trim();
    if (!trimmed || !activePartnerId || isSending) return;

    setIsSending(true);
    try {
      const newMsg = (await apiClient.post(
        `/api/v1/messages/threads/${activePartnerId}`,
        { content: trimmed, case_id: activeCaseId || undefined }
      )) as MessageItem;

      setMessageInput("");
      setMessages((prev) => [...prev, newMsg]);

      // Update the thread list snippet immediately
      setThreads((prev) =>
        prev.map((t) =>
          t.partnerId === activePartnerId || t.id === activePartnerId
            ? { ...t, lastMessage: trimmed, timestamp: "Just now" }
            : t
        )
      );

      setTimeout(() => scrollToBottom(true), 50);
    } catch (err) {
      console.error("Failed to send message:", err);
      alert("Failed to send message. Please check your connection and try again.");
    } finally {
      setIsSending(false);
    }
  };

  const activeThread = threads.find(
    (t) => t.partnerId === activePartnerId || t.id === activePartnerId
  ) || threads[0];

  const filteredThreads = threads.filter((t) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      t.senderName.toLowerCase().includes(q) ||
      t.lastMessage.toLowerCase().includes(q) ||
      (t.caseRef && t.caseRef.toLowerCase().includes(q)) ||
      (t.caseTitle && t.caseTitle.toLowerCase().includes(q))
    );
  });

  return (
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "32px 20px 80px" }}>
      {/* Header */}
      <div style={{ marginBottom: "24px" }}>
        <h1
          style={{
            fontSize: "26px",
            fontWeight: 800,
            color: "var(--navy-primary)",
            margin: "0 0 6px 0",
          }}
        >
          {isLawyer ? "Client Messages" : "Messages with Your Lawyer"}
        </h1>
        <p style={{ fontSize: "14px", color: "var(--text-secondary)", margin: 0 }}>
          {isLawyer
            ? "Direct communications with your clients regarding case filings, court dates, and legal advice."
            : "Talk directly with your lawyer about your case, upcoming hearings, and requested documents."}
        </p>
      </div>

      {/* Main 2-Column Split */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(300px, 360px) 1fr",
          gap: "20px",
          height: "calc(100vh - 230px)",
          minHeight: "600px",
        }}
      >
        {/* Left Column: Thread List */}
        <Card
          variant="default"
          padding="sm"
          style={{
            display: "flex",
            flexDirection: "column",
            background: "#FFFFFF",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-xl)",
            overflow: "hidden",
          }}
        >
          {/* Search */}
          <div style={{ padding: "8px 8px 12px 8px", borderBottom: "1px solid var(--border-subtle)" }}>
            <input
              type="text"
              placeholder="Search messages..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: "100%",
                boxSizing: "border-box",
                padding: "9px 14px",
                fontSize: "13px",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-subtle)",
                background: "#F8FAFC",
                color: "var(--text-primary)",
                outline: "none",
              }}
            />
          </div>

          {/* Threads list */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "6px",
              overflowY: "auto",
              flex: 1,
              padding: "10px 4px",
            }}
          >
            {loadingThreads && threads.length === 0 ? (
              <div style={{ padding: "24px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                Loading conversations...
              </div>
            ) : filteredThreads.length === 0 ? (
              <div style={{ padding: "24px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                {searchQuery ? "No matching conversations found." : "No conversations yet."}
              </div>
            ) : (
              filteredThreads.map((t) => {
                const threadPartnerId = t.partnerId || t.id;
                const isActive = threadPartnerId === activePartnerId;
                return (
                  <div
                    key={t.id}
                    onClick={() => setActivePartnerId(threadPartnerId)}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "12px",
                      padding: "12px 14px",
                      borderRadius: "var(--radius-md)",
                      background: isActive ? "#F1F5F9" : "transparent",
                      border: `1px solid ${
                        isActive ? "var(--border-subtle)" : "transparent"
                      }`,
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <Avatar name={t.senderName} roleBadge={t.senderRole} size="md" />

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "baseline",
                          marginBottom: "3px",
                        }}
                      >
                        <span
                          style={{
                            fontSize: "14px",
                            fontWeight: 700,
                            color: "var(--navy-primary)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {t.senderName}
                        </span>
                        <span style={{ fontSize: "11px", color: "var(--text-muted)", flexShrink: 0, marginLeft: "6px" }}>
                          {t.timestamp}
                        </span>
                      </div>

                      <div
                        style={{
                          fontSize: "11px",
                          color: "var(--brand-secondary)",
                          fontWeight: 600,
                          marginBottom: "4px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        ⚖ {t.caseTitle || t.caseRef || "Active Matter"}
                      </div>

                      <p
                        style={{
                          margin: 0,
                          fontSize: "12px",
                          color: "var(--text-secondary)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {t.lastMessage}
                      </p>
                    </div>

                    {t.unreadCount > 0 && (
                      <span
                        style={{
                          background: "var(--navy-primary)",
                          color: "#ffffff",
                          borderRadius: "50%",
                          width: "18px",
                          height: "18px",
                          fontSize: "11px",
                          fontWeight: 700,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                        }}
                      >
                        {t.unreadCount}
                      </span>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </Card>

        {/* Right Column: Chat Conversation View */}
        <Card
          variant="elevated"
          padding="md"
          style={{
            display: "flex",
            flexDirection: "column",
            background: "#FFFFFF",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-xl)",
            overflow: "hidden",
            height: "100%",
          }}
        >
          {activeThread ? (
            <>
              {/* Thread Header */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  paddingBottom: "14px",
                  borderBottom: "1px solid var(--border-subtle)",
                  marginBottom: "12px",
                  flexShrink: 0,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <Avatar name={activeThread.senderName} roleBadge={activeThread.senderRole} size="md" />
                  <div>
                    <h3
                      style={{
                        margin: 0,
                        fontSize: "16px",
                        fontWeight: 700,
                        color: "var(--navy-primary)",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}
                    >
                      {activeThread.senderName}
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          padding: "2px 7px",
                          borderRadius: "4px",
                          background: activeThread.senderRole === "lawyer" ? "rgba(30, 58, 138, 0.08)" : "rgba(15, 30, 54, 0.06)",
                          color: activeThread.senderRole === "lawyer" ? "var(--brand-secondary)" : "var(--navy-primary)",
                          textTransform: "uppercase",
                        }}
                      >
                        {activeThread.senderRole}
                      </span>
                    </h3>
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "3px", display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                      <span>Active Matter:</span>
                      {partnerCases.length > 1 ? (
                        <select
                          value={activeCaseId || ""}
                          onChange={(e) => setActiveCaseId(e.target.value)}
                          style={{
                            fontSize: "12px",
                            fontWeight: 600,
                            color: "var(--navy-primary)",
                            background: "#F1F5F9",
                            border: "1px solid var(--border-subtle)",
                            borderRadius: "6px",
                            padding: "2px 8px",
                            cursor: "pointer",
                          }}
                        >
                          {partnerCases.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.title} ({c.caseRef})
                            </option>
                          ))}
                        </select>
                      ) : (
                        <strong style={{ color: "var(--navy-primary)" }}>
                          {partnerCases[0]?.title || activeThread.caseTitle || activeThread.caseRef || "General Advisory"}
                        </strong>
                      )}
                      {(activeCaseId || activeThread.caseId) && (
                        <Link
                          href={`/cases/${activeCaseId || activeThread.caseId}`}
                          style={{
                            fontSize: "11px",
                            fontWeight: 700,
                            color: "var(--brand-secondary)",
                            textDecoration: "none",
                            padding: "2px 8px",
                            borderRadius: "4px",
                            background: "rgba(30, 58, 138, 0.08)",
                            border: "1px solid rgba(30, 58, 138, 0.2)",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                          }}
                        >
                          Open Case Workspace →
                        </Link>
                      )}
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            const res = await apiClient.post<{ room_url: string }>("/api/v1/consultations/instant-call", {
                              lawyer_id: isLawyer ? user?.id : activePartnerId,
                              case_id: activeCaseId || activeThread.caseId || undefined,
                              duration_minutes: 30,
                            });
                            if (res?.room_url) router.push(res.room_url);
                          } catch (e: unknown) {
                            const msg = e instanceof Error ? e.message : "Failed to start call";
                            alert(msg);
                          }
                        }}
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "#059669",
                          background: "rgba(5, 150, 105, 0.1)",
                          border: "1px solid rgba(5, 150, 105, 0.25)",
                          padding: "3px 10px",
                          borderRadius: "6px",
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px",
                        }}
                      >
                        📹 Video Call
                      </button>
                    </div>
                  </div>
                </div>

                <Badge variant="success" dot>
                  Protected & Confidential
                </Badge>
              </div>

              {/* Chat Messages Log */}
              <div
                ref={chatScrollRef}
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  gap: "14px",
                  padding: "12px 6px",
                  overflowY: "auto",
                }}
              >
                {loadingMessages && messages.length === 0 ? (
                  <div style={{ textAlign: "center", color: "var(--text-muted)", margin: "auto", fontSize: "13px" }}>
                    Loading conversation...
                  </div>
                ) : messages.length === 0 ? (
                  <div style={{ textAlign: "center", color: "var(--text-muted)", margin: "auto", fontSize: "13px" }}>
                    No messages yet. Send a message to start this discussion.
                  </div>
                ) : (
                  messages.map((m) => {
                    const isOut = m.isOutgoing;
                    const isMeetingMsg = m.content.includes("/consultations/") && (m.content.includes("/room") || m.content.includes("Video Call"));
                    return (
                      <div
                        key={m.id}
                        style={{
                          alignSelf: isOut ? "flex-end" : "flex-start",
                          maxWidth: "75%",
                          display: "flex",
                          flexDirection: "column",
                          alignItems: isOut ? "flex-end" : "flex-start",
                        }}
                      >
                        {/* Bubble */}
                        <div
                          style={{
                            background: isMeetingMsg
                              ? "linear-gradient(135deg, #064e3b 0%, #0f172a 100%)"
                              : isOut
                              ? "linear-gradient(135deg, #0F1E36 0%, #1E3A8A 100%)"
                              : "#F8FAFC",
                            color: isOut || isMeetingMsg ? "#FFFFFF" : "var(--text-primary)",
                            border: `1px solid ${isMeetingMsg ? "#059669" : isOut ? "#1E3A8A" : "var(--border-subtle)"}`,
                            borderRadius: isOut
                              ? "16px 16px 2px 16px"
                              : "16px 16px 16px 2px",
                            padding: "12px 18px",
                            fontSize: "14px",
                            lineHeight: 1.55,
                            boxShadow: isOut || isMeetingMsg
                              ? "0 2px 8px rgba(15, 30, 54, 0.15)"
                              : "0 1px 3px rgba(0, 0, 0, 0.04)",
                            wordBreak: "break-word",
                          }}
                        >
                          {!isOut && (
                            <div
                              style={{
                                fontSize: "11px",
                                color: isMeetingMsg ? "#34d399" : "var(--brand-secondary)",
                                marginBottom: "4px",
                                fontWeight: 700,
                              }}
                            >
                              {m.senderName}
                            </div>
                          )}
                          {isMeetingMsg ? (
                            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: 700, color: "#34d399", fontSize: "13px" }}>
                                <span style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#10b981", boxShadow: "0 0 8px #10b981" }} />
                                📹 Live Video Meeting Invitation
                              </div>
                              <p style={{ margin: 0, fontSize: "13px", color: "#e2e8f0" }}>
                                {m.content.split("Click to join")[0]}
                              </p>
                              {(() => {
                                const match = m.content.match(/\/consultations\/[a-zA-Z0-9-]+\/room/);
                                const targetRoomUrl = match ? match[0] : null;
                                return targetRoomUrl ? (
                                  <Link
                                    href={`${targetRoomUrl}?bypass_time=true`}
                                    style={{
                                      background: "linear-gradient(135deg, #059669 0%, #047857 100%)",
                                      color: "#ffffff",
                                      padding: "8px 16px",
                                      borderRadius: "8px",
                                      fontWeight: 700,
                                      fontSize: "12px",
                                      textDecoration: "none",
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: "6px",
                                      width: "fit-content",
                                      marginTop: "4px",
                                      boxShadow: "0 2px 6px rgba(5, 150, 105, 0.3)",
                                    }}
                                  >
                                    📹 Join Video Meeting Now →
                                  </Link>
                                ) : null;
                              })()}
                            </div>
                          ) : (
                            <div>{m.content}</div>
                          )}
                        </div>

                        {/* Timestamp & Status */}
                        <div
                          style={{
                            fontSize: "11px",
                            color: "var(--text-muted)",
                            marginTop: "4px",
                            padding: "0 4px",
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                          }}
                        >
                          <span>{m.timestamp}</span>
                          {isOut && (
                            <span
                              title={m.isRead ? "Read by recipient" : "Delivered"}
                              style={{
                                color: m.isRead ? "#22C55E" : "var(--text-muted)",
                                fontWeight: 700,
                              }}
                            >
                              {m.isRead ? "✓✓" : "✓"}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Input Row */}
              <div
                style={{
                  display: "flex",
                  gap: "10px",
                  paddingTop: "14px",
                  borderTop: "1px solid var(--border-subtle)",
                  flexShrink: 0,
                }}
              >
                <input
                  type="text"
                  placeholder={
                    isLawyer
                      ? "Type a reply to your client..."
                      : "Type a message or question for your lawyer..."
                  }
                  value={messageInput}
                  onChange={(e) => setMessageInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && messageInput.trim() && !isSending) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  disabled={isSending}
                  style={{
                    flex: 1,
                    minHeight: "44px",
                    background: "#F8FAFC",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                    padding: "10px 16px",
                    color: "var(--text-primary)",
                    fontSize: "14px",
                    outline: "none",
                  }}
                />
                <Button
                  variant="primary"
                  onClick={handleSendMessage}
                  disabled={isSending || !messageInput.trim()}
                >
                  {isSending ? "Sending..." : "Send Message"}
                </Button>
              </div>
            </>
          ) : (
            <EmptyState
              icon="💬"
              title="Select a conversation"
              description="Choose a conversation from the left to read or send direct messages."
            />
          )}
        </Card>
      </div>
    </div>
  );
}
