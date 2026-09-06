"use client";

import React, { useState } from "react";
import { useAuth } from "@/providers/AuthProvider";
import { Card, Button, Input, Avatar, Badge, EmptyState } from "@/components/ui";

interface Thread {
  id: string;
  senderName: string;
  senderRole: "client" | "lawyer" | "admin";
  lastMessage: string;
  timestamp: string;
  unreadCount: number;
  caseRef: string;
}

export default function MessagesPage() {
  const { user } = useAuth();
  const isLawyer = user?.role === "LAWYER";

  const [threads] = useState<Thread[]>([
    {
      id: "th-1",
      senderName: isLawyer ? "Vikram Sharma" : "Advocate Ananya Roy",
      senderRole: isLawyer ? "client" : "lawyer",
      lastMessage: "I have uploaded the certified copy of the sale deed. Please review before filing.",
      timestamp: "10:45 AM",
      unreadCount: 1,
      caseRef: "CIV-2026-0941",
    },
    {
      id: "th-2",
      senderName: isLawyer ? "Rajesh Verma" : "Advocate Rahul Mehta",
      senderRole: isLawyer ? "client" : "lawyer",
      lastMessage: "The registry confirmed the next hearing is scheduled for 15 September.",
      timestamp: "Yesterday",
      unreadCount: 0,
      caseRef: "COM-2026-1102",
    },
  ]);

  const [activeThreadId, setActiveThreadId] = useState<string>("th-1");
  const [messageInput, setMessageInput] = useState("");
  const activeThread = threads.find((t) => t.id === activeThreadId) || threads[0];

  return (
    <div style={{ maxWidth: "1280px", margin: "0 auto", padding: "24px 20px" }}>
      {/* Header */}
      <div style={{ marginBottom: "20px" }}>
        <h1
          style={{
            fontSize: "var(--font-size-2xl, 24px)",
            fontWeight: 700,
            color: "var(--text-primary, #f8fafc)",
            fontFamily: "var(--font-display, sans-serif)",
            margin: "0 0 6px 0",
          }}
        >
          Matter Messages & Legal Communications
        </h1>
        <p style={{ fontSize: "var(--font-size-sm, 14px)", color: "var(--text-secondary, #94a3b8)", margin: 0 }}>
          Direct, encrypted communication channel between counsel and client regarding matter filings and hearings.
        </p>
      </div>

      {/* Main 2-Column Split */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(280px, 340px) 1fr",
          gap: "16px",
          minHeight: "560px",
        }}
      >
        {/* Left Column: Thread List */}
        <Card variant="default" padding="sm" style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ padding: "8px 8px 12px 8px" }}>
            <Input placeholder="Search messages..." />
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "6px", overflowY: "auto", flex: 1 }}>
            {threads.map((t) => {
              const isActive = t.id === activeThreadId;
              return (
                <div
                  key={t.id}
                  onClick={() => setActiveThreadId(t.id)}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "12px",
                    padding: "12px",
                    borderRadius: "var(--radius-md, 8px)",
                    background: isActive ? "var(--surface-elevated, #151A24)" : "transparent",
                    border: `1px solid ${
                      isActive ? "var(--brand-primary, #6366f1)" : "transparent"
                    }`,
                    cursor: "pointer",
                    transition: "var(--transition-fast, 0.15s ease)",
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
                          fontSize: "var(--font-size-sm, 14px)",
                          fontWeight: 600,
                          color: "var(--text-primary, #f8fafc)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {t.senderName}
                      </span>
                      <span style={{ fontSize: "11px", color: "var(--text-muted, #64748b)" }}>
                        {t.timestamp}
                      </span>
                    </div>

                    <div style={{ fontSize: "11px", color: "var(--brand-primary, #6366f1)", marginBottom: "4px" }}>
                      Ref: #{t.caseRef}
                    </div>

                    <p
                      style={{
                        margin: 0,
                        fontSize: "var(--font-size-xs, 12px)",
                        color: "var(--text-secondary, #94a3b8)",
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
                        background: "var(--brand-primary, #6366f1)",
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
            })}
          </div>
        </Card>

        {/* Right Column: Chat Conversation View */}
        <Card variant="elevated" padding="md" style={{ display: "flex", flexDirection: "column" }}>
          {activeThread ? (
            <>
              {/* Thread Header */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  paddingBottom: "14px",
                  borderBottom: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                  marginBottom: "16px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <Avatar name={activeThread.senderName} roleBadge={activeThread.senderRole} size="md" />
                  <div>
                    <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 600, color: "var(--text-primary, #f8fafc)" }}>
                      {activeThread.senderName}
                    </h3>
                    <div style={{ fontSize: "12px", color: "var(--text-secondary, #94a3b8)" }}>
                      Associated Matter: <strong>#{activeThread.caseRef}</strong>
                    </div>
                  </div>
                </div>

                <Badge variant="success" dot>
                  Encrypted & Logged
                </Badge>
              </div>

              {/* Chat Log */}
              <div
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  gap: "14px",
                  padding: "8px 0",
                  overflowY: "auto",
                }}
              >
                <div
                  style={{
                    alignSelf: "flex-start",
                    maxWidth: "75%",
                    background: "var(--surface-subtle, #141824)",
                    border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                    borderRadius: "12px 12px 12px 2px",
                    padding: "12px 16px",
                    fontSize: "var(--font-size-sm, 14px)",
                    lineHeight: 1.5,
                  }}
                >
                  <div style={{ fontSize: "11px", color: "var(--brand-primary, #6366f1)", marginBottom: "4px", fontWeight: 600 }}>
                    {activeThread.senderName}
                  </div>
                  <div>{activeThread.lastMessage}</div>
                  <div style={{ fontSize: "10px", color: "var(--text-muted, #64748b)", marginTop: "4px", textAlign: "right" }}>
                    {activeThread.timestamp}
                  </div>
                </div>
              </div>

              {/* Input Row */}
              <div
                style={{
                  display: "flex",
                  gap: "10px",
                  paddingTop: "14px",
                  borderTop: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                }}
              >
                <input
                  type="text"
                  placeholder="Type a message or document question to counsel..."
                  value={messageInput}
                  onChange={(e) => setMessageInput(e.target.value)}
                  style={{
                    flex: 1,
                    minHeight: "44px",
                    background: "var(--surface-base, #07090E)",
                    border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.1))",
                    borderRadius: "var(--radius-md, 8px)",
                    padding: "10px 14px",
                    color: "var(--text-primary, #f8fafc)",
                    fontSize: "var(--font-size-sm, 14px)",
                    outline: "none",
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && messageInput.trim()) {
                      setMessageInput("");
                      alert("Message sent to counsel.");
                    }
                  }}
                />
                <Button
                  variant="primary"
                  onClick={() => {
                    if (messageInput.trim()) {
                      setMessageInput("");
                      alert("Message sent to counsel.");
                    }
                  }}
                >
                  Send
                </Button>
              </div>
            </>
          ) : (
            <EmptyState
              icon="💬"
              title="Select a matter conversation"
              description="Choose a conversation from the left to read or send messages regarding case proceedings."
            />
          )}
        </Card>
      </div>
    </div>
  );
}
