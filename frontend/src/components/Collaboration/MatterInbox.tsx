"use client";

import React, { useState, useEffect, useRef } from "react";
import { CaseMessageItem, DocumentItem, CaseTaskItem } from "@/types";
import { apiClient } from "@/api/client";

interface MatterInboxProps {
  caseId: string;
  messages: CaseMessageItem[];
  documents: DocumentItem[];
  tasks: CaseTaskItem[];
  userRole: string;
  onRefresh: () => void;
}

export function MatterInbox({
  caseId,
  messages,
  documents,
  tasks,
  userRole,
  onRefresh,
}: MatterInboxProps) {
  const [content, setContent] = useState("");
  const [msgType, setMsgType] = useState<"GENERAL" | "FORMAL_NOTICE" | "STATUS_UPDATE">("GENERAL");
  const [linkedDocId, setLinkedDocId] = useState("");
  const [linkedTaskId, setLinkedTaskId] = useState("");
  const [isCounselOnly, setIsCounselOnly] = useState(false);
  const [sending, setSending] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim() || sending) return;

    setSending(true);
    try {
      await apiClient.post(`/api/v1/cases/${caseId}/collaboration/messages`, {
        content: content.trim(),
        message_type: msgType,
        linked_document_id: linkedDocId || null,
        linked_task_id: linkedTaskId || null,
        is_counsel_only: isCounselOnly,
      });
      setContent("");
      setLinkedDocId("");
      setLinkedTaskId("");
      setIsCounselOnly(false);
      onRefresh();
    } catch (err) {
      console.error("Failed to send matter communication:", err);
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr",
        gap: "18px",
        background: "var(--surface-card, #FFFFFF)",
        border: "1px solid var(--border-subtle, #D9E2EC)",
        borderRadius: "var(--radius-xl, 14px)",
        padding: "24px",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ fontSize: "16px", fontWeight: 700, color: "var(--navy-primary, #17324D)", margin: 0 }}>
            Case Messages & Notices ({messages.length})
          </h3>
          <p style={{ fontSize: "13px", color: "var(--text-secondary, #52606D)", marginTop: "4px" }}>
            Formal case notices, document updates, and communications between you and your counsel.
          </p>
        </div>
      </div>

      {/* Messages Stream */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "12px",
          maxHeight: "480px",
          overflowY: "auto",
          paddingRight: "6px",
        }}
      >
        {messages.length === 0 ? (
          <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted, #7B8794)", fontSize: "14px" }}>
            No messages recorded on this case yet. Use the composer below to send a message.
          </div>
        ) : (
          messages.map((m) => {
            const isClient = m.sender_role?.toUpperCase() === "CLIENT" || m.sender_role?.toUpperCase() === "OWNER";
            const isFormal = m.message_type === "FORMAL_NOTICE";
            const isUpdate = m.message_type === "STATUS_UPDATE";
            const isDocSub = m.message_type === "DOCUMENT_SUBMISSION";
            const isReq = m.message_type === "ACTION_REQUEST";

            let typeBadgeBg = "rgba(82, 96, 109, 0.1)";
            let typeBadgeColor = "var(--text-secondary, #52606D)";

            if (isFormal) {
              typeBadgeBg = "rgba(197, 48, 48, 0.1)";
              typeBadgeColor = "var(--status-urgent, #C53030)";
            } else if (isUpdate) {
              typeBadgeBg = "rgba(47, 133, 90, 0.1)";
              typeBadgeColor = "var(--status-safe-text, #2F855A)";
            } else if (isDocSub) {
              typeBadgeBg = "var(--blue-very-light, #EAF4FB)";
              typeBadgeColor = "var(--blue-soft, #3B82B6)";
            } else if (isReq) {
              typeBadgeBg = "rgba(194, 120, 3, 0.1)";
              typeBadgeColor = "var(--accent-gold, #C27803)";
            }

            return (
              <div
                key={m.id}
                style={{
                  padding: "14px 16px",
                  borderRadius: "10px",
                  background: isClient ? "var(--blue-very-light, #EAF4FB)" : "var(--surface-base, #F7F9FC)",
                  border: isClient ? "1px solid rgba(59, 130, 182, 0.3)" : "1px solid var(--border-subtle, #D9E2EC)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                  alignSelf: isClient ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <strong style={{ fontSize: "13px", color: isClient ? "var(--blue-soft, #3B82B6)" : "var(--navy-primary, #17324D)" }}>
                      {m.sender_name}
                    </strong>
                    <span
                      style={{
                        fontSize: "11px",
                        padding: "2px 6px",
                        borderRadius: "4px",
                        background: "var(--surface-card, #FFFFFF)",
                        border: "1px solid var(--border-subtle, #D9E2EC)",
                        color: "var(--text-secondary, #52606D)",
                        fontWeight: 600,
                      }}
                    >
                      {m.sender_role}
                    </span>
                    <span
                      style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        padding: "2px 6px",
                        borderRadius: "4px",
                        background: typeBadgeBg,
                        color: typeBadgeColor,
                      }}
                    >
                      {m.message_type.replace(/_/g, " ")}
                    </span>
                    {m.is_counsel_only && (
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: "4px",
                          background: "rgba(168, 85, 247, 0.15)",
                          color: "#7e22ce",
                        }}
                      >
                        Privileged (Counsel Only)
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: "11px", color: "var(--text-muted, #7B8794)" }}>
                    {new Date(m.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })},{" "}
                    {new Date(m.created_at).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
                  </span>
                </div>

                <div style={{ fontSize: "14px", color: "var(--text-primary, #17212B)", lineHeight: "1.55", whiteSpace: "pre-wrap" }}>
                  {m.content}
                </div>

                {(m.linked_document_title || m.linked_task_title) && (
                  <div style={{ display: "flex", gap: "8px", marginTop: "4px", flexWrap: "wrap" }}>
                    {m.linked_document_title && (
                      <span
                        style={{
                          fontSize: "12px",
                          color: "var(--blue-soft, #3B82B6)",
                          background: "var(--surface-card, #FFFFFF)",
                          padding: "3px 10px",
                          borderRadius: "6px",
                          border: "1px solid var(--border-subtle, #D9E2EC)",
                        }}
                      >
                        Document: {m.linked_document_title}
                      </span>
                    )}
                    {m.linked_task_title && (
                      <span
                        style={{
                          fontSize: "12px",
                          color: "var(--status-safe-text, #2F855A)",
                          background: "var(--surface-card, #FFFFFF)",
                          padding: "3px 10px",
                          borderRadius: "6px",
                          border: "1px solid var(--border-subtle, #D9E2EC)",
                        }}
                      >
                        Task: {m.linked_task_title}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Message Composer */}
      {userRole !== "VIEWER" && (
        <form
          onSubmit={handleSendMessage}
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "12px",
            background: "var(--surface-base, #F7F9FC)",
            border: "1px solid var(--border-subtle, #D9E2EC)",
            borderRadius: "10px",
            padding: "16px",
          }}
        >
          <textarea
            rows={3}
            placeholder="Type your message or question to case participants..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            style={{
              width: "100%",
              background: "var(--surface-card, #FFFFFF)",
              border: "1px solid var(--border-subtle, #D9E2EC)",
              borderRadius: "8px",
              padding: "10px 14px",
              outline: "none",
              color: "var(--text-primary, #17212B)",
              fontSize: "14px",
              lineHeight: 1.5,
              resize: "vertical",
            }}
            required
          />

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <select
                value={msgType}
                onChange={(e) => setMsgType(e.target.value as never)}
                style={{
                  padding: "6px 10px",
                  background: "var(--surface-card, #FFFFFF)",
                  border: "1px solid var(--border-subtle, #D9E2EC)",
                  borderRadius: "6px",
                  color: "var(--text-primary, #17212B)",
                  fontSize: "12px",
                }}
              >
                <option value="GENERAL">General Message</option>
                <option value="FORMAL_NOTICE">Formal Legal Notice</option>
                <option value="STATUS_UPDATE">Status Update</option>
              </select>

              {documents.length > 0 && (
                <select
                  value={linkedDocId}
                  onChange={(e) => setLinkedDocId(e.target.value)}
                  style={{
                    padding: "6px 10px",
                    background: "var(--surface-card, #FFFFFF)",
                    border: "1px solid var(--border-subtle, #D9E2EC)",
                    borderRadius: "6px",
                    color: "var(--text-primary, #17212B)",
                    fontSize: "12px",
                    maxWidth: "200px",
                  }}
                >
                  <option value="">Attach document...</option>
                  {documents.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.filename}
                    </option>
                  ))}
                </select>
              )}

              {tasks.length > 0 && (
                <select
                  value={linkedTaskId}
                  onChange={(e) => setLinkedTaskId(e.target.value)}
                  style={{
                    padding: "6px 10px",
                    background: "var(--surface-card, #FFFFFF)",
                    border: "1px solid var(--border-subtle, #D9E2EC)",
                    borderRadius: "6px",
                    color: "var(--text-primary, #17212B)",
                    fontSize: "12px",
                    maxWidth: "200px",
                  }}
                >
                  <option value="">Reference task...</option>
                  {tasks.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title}
                    </option>
                  ))}
                </select>
              )}

              {userRole !== "CLIENT" && (
                <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "var(--text-secondary, #52606D)", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={isCounselOnly}
                    onChange={(e) => setIsCounselOnly(e.target.checked)}
                  />
                  Counsel Only (Privileged)
                </label>
              )}
            </div>

            <button
              type="submit"
              disabled={sending || !content.trim()}
              className="btn btn-primary"
              style={{
                fontSize: "13px",
                padding: "8px 18px",
              }}
            >
              {sending ? "Sending..." : "Send Message"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
