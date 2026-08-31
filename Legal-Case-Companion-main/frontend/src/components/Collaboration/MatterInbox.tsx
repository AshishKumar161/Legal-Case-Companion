"use client";

import React, { useState } from "react";
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
        background: "var(--surface-card)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-md)",
        padding: "20px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: 0 }}>
            Matter Communication Record ({messages.length})
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
            Formal case notices, documentary submissions, and shared status reports.
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
          <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)", fontSize: "13px" }}>
            No formal matter communications recorded yet. Use the composer below to dispatch a notice.
          </div>
        ) : (
          messages.map((m) => {
            const isFormal = m.message_type === "FORMAL_NOTICE";
            const isUpdate = m.message_type === "STATUS_UPDATE";
            const isDocSub = m.message_type === "DOCUMENT_SUBMISSION";
            const isReq = m.message_type === "ACTION_REQUEST";

            let typeBadgeBg = "rgba(100, 116, 139, 0.15)";
            let typeBadgeColor = "#94a3b8";

            if (isFormal) {
              typeBadgeBg = "rgba(239, 68, 68, 0.15)";
              typeBadgeColor = "#f87171";
            } else if (isUpdate) {
              typeBadgeBg = "rgba(16, 185, 129, 0.15)";
              typeBadgeColor = "#34d399";
            } else if (isDocSub) {
              typeBadgeBg = "rgba(59, 130, 246, 0.15)";
              typeBadgeColor = "#60a5fa";
            } else if (isReq) {
              typeBadgeBg = "rgba(245, 158, 11, 0.15)";
              typeBadgeColor = "#fbbf24";
            }

            return (
              <div
                key={m.id}
                style={{
                  padding: "14px 16px",
                  borderRadius: "8px",
                  background: m.is_counsel_only ? "#18141f" : "#131722",
                  border: m.is_counsel_only ? "1px solid rgba(168, 85, 247, 0.3)" : "1px solid #202738",
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <strong style={{ fontSize: "13px", color: "#fff" }}>{m.sender_name}</strong>
                    <span
                      style={{
                        fontSize: "10px",
                        padding: "1px 6px",
                        borderRadius: "3px",
                        background: "rgba(255, 255, 255, 0.08)",
                        color: "var(--text-secondary)",
                      }}
                    >
                      {m.sender_role}
                    </span>
                    <span
                      style={{
                        fontSize: "10px",
                        fontWeight: 600,
                        padding: "1px 6px",
                        borderRadius: "3px",
                        background: typeBadgeBg,
                        color: typeBadgeColor,
                      }}
                    >
                      {m.message_type}
                    </span>
                    {m.is_counsel_only && (
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: 700,
                          padding: "1px 6px",
                          borderRadius: "3px",
                          background: "rgba(168, 85, 247, 0.2)",
                          color: "#c084fc",
                        }}
                      >
                        🔒 COUNSEL ONLY
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                    {new Date(m.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })},{" "}
                    {new Date(m.created_at).toLocaleDateString("en-IN", { month: "short", day: "numeric" })}
                  </span>
                </div>

                <div style={{ fontSize: "13px", color: "#e2e8f0", lineHeight: "1.5", whiteSpace: "pre-wrap" }}>
                  {m.content}
                </div>

                {(m.linked_document_title || m.linked_task_title) && (
                  <div style={{ display: "flex", gap: "10px", marginTop: "4px", flexWrap: "wrap" }}>
                    {m.linked_document_title && (
                      <span
                        style={{
                          fontSize: "11px",
                          color: "#60a5fa",
                          background: "rgba(59, 130, 246, 0.1)",
                          padding: "3px 8px",
                          borderRadius: "4px",
                          border: "1px solid rgba(59, 130, 246, 0.2)",
                        }}
                      >
                        📄 Linked Evidence: {m.linked_document_title}
                      </span>
                    )}
                    {m.linked_task_title && (
                      <span
                        style={{
                          fontSize: "11px",
                          color: "#34d399",
                          background: "rgba(16, 185, 129, 0.1)",
                          padding: "3px 8px",
                          borderRadius: "4px",
                          border: "1px solid rgba(16, 185, 129, 0.2)",
                        }}
                      >
                        ⚡ Linked Task: {m.linked_task_title}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Message Composer */}
      {userRole !== "VIEWER" && (
        <form
          onSubmit={handleSendMessage}
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "10px",
            background: "#0f131c",
            border: "1px solid #232a3d",
            borderRadius: "8px",
            padding: "14px",
          }}
        >
          <textarea
            rows={3}
            placeholder="Compose formal notice, evidence transmittal, or status update to matter participants..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            style={{
              width: "100%",
              background: "transparent",
              border: "none",
              outline: "none",
              color: "#fff",
              fontSize: "13px",
              resize: "vertical",
            }}
            required
          />

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
              <select
                value={msgType}
                onChange={(e) => setMsgType(e.target.value as any)}
                style={{
                  padding: "4px 8px",
                  background: "var(--surface-base)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "4px",
                  color: "#fff",
                  fontSize: "11px",
                }}
              >
                <option value="GENERAL">General Notice</option>
                <option value="FORMAL_NOTICE">Formal Legal Notice</option>
                <option value="STATUS_UPDATE">Status Update</option>
              </select>

              <select
                value={linkedDocId}
                onChange={(e) => setLinkedDocId(e.target.value)}
                style={{
                  padding: "4px 8px",
                  background: "var(--surface-base)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "4px",
                  color: "#fff",
                  fontSize: "11px",
                  maxWidth: "180px",
                }}
              >
                <option value="">Attach Document...</option>
                {documents.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.filename}
                  </option>
                ))}
              </select>

              <select
                value={linkedTaskId}
                onChange={(e) => setLinkedTaskId(e.target.value)}
                style={{
                  padding: "4px 8px",
                  background: "var(--surface-base)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "4px",
                  color: "#fff",
                  fontSize: "11px",
                  maxWidth: "180px",
                }}
              >
                <option value="">Reference Task...</option>
                {tasks.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
              </select>

              {userRole !== "CLIENT" && (
                <label style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "11px", color: "#c084fc", cursor: "pointer" }}>
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
              style={{
                padding: "6px 16px",
                background: "#3b82f6",
                color: "#fff",
                border: "none",
                borderRadius: "4px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {sending ? "Transmitting..." : "Send to Matter Record →"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
