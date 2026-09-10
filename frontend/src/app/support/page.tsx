"use client";

import React, { useState, useEffect, useCallback } from "react";
import { apiClient } from "@/api/client";
import { AppShell } from "@/components/AppShell/AppShell";
import { StatusBadge } from "@/components/StatusBadge";
import styles from "./support.module.css";

interface SupportCase {
  id: string;
  support_case_id: string;
  category: string;
  severity: "SEV1_CRITICAL" | "SEV2_HIGH" | "SEV3_MEDIUM" | "SEV4_LOW";
  subject: string;
  description: string;
  opened_at: string;
  resolved_at: string | null;
  status: "OPEN" | "PENDING_USER" | "IN_PROGRESS" | "RESOLVED" | "CLOSED";
  resolution_code: string | null;
  resolution_notes: string | null;
}

const CATEGORY_OPTIONS = [
  { value: "PAYMENT_PROBLEM", label: "Payment or Billing Problem" },
  { value: "LAWYER_PROBLEM", label: "Lawyer or Consultation Problem" },
  { value: "CASE_PROBLEM", label: "Case Workspace Problem" },
  { value: "DOCUMENT_PROBLEM", label: "Evidence or Document Upload Problem" },
  { value: "COURT_TRACKING_PROBLEM", label: "Court Docket or Sync Problem" },
  { value: "ACCOUNT_PROBLEM", label: "Account Access or Security Problem" },
  { value: "TECHNICAL_PROBLEM", label: "Technical Error or Bug" },
  { value: "OTHER", label: "Other Operational Query" },
];

const SEVERITY_OPTIONS = [
  { value: "SEV3_MEDIUM", label: "Normal (General Workflow Issue)" },
  { value: "SEV2_HIGH", label: "High (Consultation or Access Failure)" },
  { value: "SEV1_CRITICAL", label: "Critical (Upcoming Court Hearing or Failed Charge)" },
  { value: "SEV4_LOW", label: "Low (General Question or Feedback)" },
];

interface SupportMessage {
  id: string;
  sender_role: string;
  sender_name: string;
  message_text: string;
  is_internal_note: boolean;
  created_at: string;
}

export default function SupportCenterPage() {
  const [tickets, setTickets] = useState<SupportCase[]>([]);
  const [loadingTickets, setLoadingTickets] = useState(true);

  // Active ticket conversation
  const [activeTicket, setActiveTicket] = useState<SupportCase | null>(null);
  const [messages, setMessages] = useState<SupportMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [sendingReply, setSendingReply] = useState(false);

  // Form states
  const [category, setCategory] = useState("PAYMENT_PROBLEM");
  const [severity, setSeverity] = useState("SEV3_MEDIUM");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const fetchTickets = useCallback(async () => {
    try {
      setLoadingTickets(true);
      const res = await apiClient.get("/api/v1/support/cases");
      setTickets(Array.isArray(res) ? (res as SupportCase[]) : []);
    } catch {
      setTickets([]);
    } finally {
      setLoadingTickets(false);
    }
  }, []);

  const openTicketThread = async (ticket: SupportCase) => {
    setActiveTicket(ticket);
    setLoadingMessages(true);
    setReplyText("");
    try {
      const res = await apiClient.get(`/api/v1/support/cases/${ticket.id}/messages`);
      setMessages(Array.isArray(res) ? (res as SupportMessage[]) : []);
    } catch {
      setMessages([]);
    } finally {
      setLoadingMessages(false);
    }
  };

  const handleSendReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyText.trim() || !activeTicket) return;

    setSendingReply(true);
    try {
      await apiClient.post(
        `/api/v1/support/cases/${activeTicket.id}/messages?message_text=${encodeURIComponent(
          replyText.trim()
        )}`,
        {}
      );
      setReplyText("");
      // Refresh messages
      const res = await apiClient.get(`/api/v1/support/cases/${activeTicket.id}/messages`);
      setMessages(Array.isArray(res) ? (res as SupportMessage[]) : []);
      fetchTickets();
    } catch (err: unknown) {
      alert("Failed to send message: " + (err instanceof Error ? err.message : "Error"));
    } finally {
      setSendingReply(false);
    }
  };

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  const handleSubmitTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim() || !description.trim()) {
      setErrorMessage("Please complete all required fields.");
      return;
    }

    setSubmitting(true);
    setErrorMessage("");
    setSubmitSuccess(false);

    try {
      await apiClient.post("/api/v1/support/cases", {
        category,
        severity,
        subject: subject.trim(),
        description: description.trim(),
        workflow: "SUPPORT_PORTAL",
      });

      // Emit privacy-preserving telemetry
      await apiClient.post(
        "/api/v1/pilot/telemetry/event",
        {
          event_type: "SUPPORT_TICKET_CREATED",
          metadata: { category, severity },
        },
        { requireAuth: false }
      ).catch(() => null);

      setSubmitSuccess(true);
      setSubject("");
      setDescription("");
      fetchTickets();
      setTimeout(() => setSubmitSuccess(false), 4000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to submit ticket. Please try again.";
      setErrorMessage(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <div className={styles.container}>
        <div className={styles.header}>
          <div className={styles.badge}>Pilot Operations • Customer Care</div>
          <h1 className={styles.title}>Legal Case Companion Support</h1>
          <p className={styles.subtitle}>
            Direct assistance for consultation payments, court docket tracking, document storage, and account issues.
          </p>
        </div>

        {/* SLA and Business Hours Transparency Banner */}
        <div className={styles.slaBanner}>
          <div className={styles.slaIcon}>⏱️</div>
          <div>
            <div className={styles.slaTitle}>Operational Hours & Support SLA</div>
            <p className={styles.slaText}>
              Our legal operations desk is active <strong>Monday to Saturday, 9:00 AM – 7:00 PM IST</strong>. Standard ticket response target is within <strong>4 business hours</strong>. Critical court hearing issues (P1) receive immediate escalation. Round-the-clock 24/7 hotline support is currently not active during the pilot phase.
            </p>
          </div>
        </div>

        <div className={styles.grid}>
          {/* Submission Form */}
          <div className={styles.formCard}>
            <h2 className={styles.sectionTitle}>
              <span>📩</span> Open New Request
            </h2>

            {submitSuccess && (
              <div style={{ padding: "12px", background: "rgba(16, 185, 129, 0.1)", border: "1px solid #10b981", borderRadius: "8px", color: "#6ee7b7", fontSize: "13px", marginBottom: "16px" }}>
                ✓ Support ticket submitted successfully. Our team will review your inquiry shortly.
              </div>
            )}

            {errorMessage && (
              <div style={{ padding: "12px", background: "rgba(239, 68, 68, 0.1)", border: "1px solid #ef4444", borderRadius: "8px", color: "#fca5a5", fontSize: "13px", marginBottom: "16px" }}>
                {errorMessage}
              </div>
            )}

            <form onSubmit={handleSubmitTicket} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              <div className={styles.fieldGroup}>
                <label className={styles.label}>Issue Category</label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className={styles.select}
                >
                  {CATEGORY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.label}>Urgency & Priority</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  className={styles.select}
                >
                  {SEVERITY_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.label}>Subject</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  required
                  placeholder="e.g. Failed consultation payment on Saket matter"
                  className={styles.input}
                />
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.label}>Details & Error Description</label>
                <textarea
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  required
                  placeholder="Please describe what happened, including any relevant transaction ID, court case number, or error messages..."
                  className={styles.textarea}
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className={styles.submitBtn}
              >
                {submitting ? "Submitting Request..." : "Submit Support Ticket →"}
              </button>
            </form>
          </div>

          {/* Ticket History */}
          <div className={styles.ticketsCard}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2 className={styles.sectionTitle} style={{ margin: 0 }}>
                <span>📁</span> My Support Tickets
              </h2>
              <button
                onClick={fetchTickets}
                style={{
                  background: "transparent",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "6px",
                  color: "var(--text-secondary)",
                  fontSize: "12px",
                  padding: "4px 8px",
                  cursor: "pointer",
                }}
              >
                ↻ Refresh
              </button>
            </div>

            {loadingTickets ? (
              <div style={{ padding: "24px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                Loading your support tickets...
              </div>
            ) : tickets.length === 0 ? (
              <div style={{ padding: "32px", textAlign: "center", color: "var(--text-secondary)" }}>
                <div style={{ fontSize: "32px", marginBottom: "8px" }}>✓</div>
                <div style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>No Open Support Cases</div>
                <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
                  When you submit a request, you can track investigation notes and resolution progress here.
                </div>
              </div>
            ) : (
              <div className={styles.ticketList}>
                {tickets.map((t) => (
                  <div
                    key={t.id}
                    className={styles.ticketItem}
                    onClick={() => openTicketThread(t)}
                    style={{ cursor: "pointer" }}
                    title="Click to view conversation thread and reply"
                  >
                    <div className={styles.ticketHeader}>
                      <div>
                        <span className={styles.ticketId}>{t.support_case_id}</span>
                        <h3 className={styles.ticketSubject}>{t.subject}</h3>
                      </div>
                      <StatusBadge status={t.status} />
                    </div>

                    <p style={{ fontSize: "13px", color: "#cbd5e1", margin: 0, lineHeight: "1.4" }}>
                      {t.description}
                    </p>

                    <div className={styles.ticketMeta}>
                      <span>Category: <strong>{t.category.replace(/_/g, " ")}</strong></span>
                      <span>Severity: <strong>{t.severity.replace("SEV", "P")}</strong></span>
                      <span>Opened: <strong>{new Date(t.opened_at).toLocaleDateString("en-IN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</strong></span>
                      <span style={{ color: "#60a5fa", textDecoration: "underline" }}>View Conversation →</span>
                    </div>

                    {t.resolution_notes && (
                      <div className={styles.resolutionBox}>
                        <strong>Resolution ({t.resolution_code || "Resolved"}):</strong> {t.resolution_notes}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Conversation Drawer Modal */}
        {activeTicket && (
          <div className={styles.modalOverlay} onClick={() => setActiveTicket(null)}>
            <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <div>
                  <span className={styles.ticketId}>{activeTicket.support_case_id}</span>
                  <h3 style={{ margin: "4px 0 0 0", color: "#fff", fontSize: "15px" }}>{activeTicket.subject}</h3>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <StatusBadge status={activeTicket.status} />
                  <button className={styles.closeBtn} onClick={() => setActiveTicket(null)}>
                    ✕
                  </button>
                </div>
              </div>

              <div className={styles.threadBody}>
                {/* Initial Ticket Description */}
                <div className={`${styles.messageBubble} ${styles.userBubble}`}>
                  <div className={styles.messageHeader}>
                    <span>You (Initial Request)</span>
                    <span>{new Date(activeTicket.opened_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                  <div>{activeTicket.description}</div>
                </div>

                {loadingMessages ? (
                  <div style={{ textAlign: "center", color: "#94a3b8", fontSize: "12px", padding: "16px" }}>
                    Loading conversation messages...
                  </div>
                ) : messages.length === 0 ? (
                  <div style={{ textAlign: "center", color: "#64748b", fontSize: "12px", padding: "16px" }}>
                    An operator will respond shortly during business hours (9 AM - 7 PM IST). You may add additional notes below.
                  </div>
                ) : (
                  messages.map((m) => {
                    const isOp = m.sender_role === "OPERATOR";
                    return (
                      <div
                        key={m.id}
                        className={`${styles.messageBubble} ${isOp ? styles.operatorBubble : styles.userBubble}`}
                      >
                        <div className={styles.messageHeader}>
                          <span>{isOp ? `🛡️ ${m.sender_name} (Support Operator)` : `👤 ${m.sender_name}`}</span>
                          <span>{new Date(m.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</span>
                        </div>
                        <div>{m.message_text}</div>
                      </div>
                    );
                  })
                )}
              </div>

              <form className={styles.modalFooter} onSubmit={handleSendReply}>
                <input
                  type="text"
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Type a response or provide additional details..."
                  className={styles.replyInput}
                />
                <button type="submit" disabled={sendingReply || !replyText.trim()} className={styles.replyBtn}>
                  {sendingReply ? "Sending..." : "Reply →"}
                </button>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
