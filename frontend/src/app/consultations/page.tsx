"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import { ConsultationItem, CaseItem, ConsultationNoteItem } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { EmptyState } from "@/components/EmptyState";
import { PaymentCheckoutModal } from "@/components/Payment/PaymentCheckoutModal";
import { ConsultationActionModal } from "@/components/Consultation/ConsultationActionModal";


type TabType = "UPCOMING" | "TODAY" | "COMPLETED" | "ALL";

export default function ConsultationsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [consultations, setConsultations] = useState<ConsultationItem[]>([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("UPCOMING");

  // Modals state
  const [checkoutConsultation, setCheckoutConsultation] = useState<ConsultationItem | null>(null);

  const [acceptingId, setAcceptingId] = useState<string | null>(null);
  const [actionModal, setActionModal] = useState<{
    type: "RESCHEDULE" | "CANCEL" | "REJECT" | "NO_SHOW" | "COMPLETE" | "SCHEDULE";
    consultation: ConsultationItem;
  } | null>(null);

  // Notes Modal state
  const [viewNotesConsultation, setViewNotesConsultation] = useState<ConsultationItem | null>(null);
  const [notes, setNotes] = useState<ConsultationNoteItem[]>([]);
  const [loadingNotes, setLoadingNotes] = useState(false);
  const [newNoteSummary, setNewNoteSummary] = useState("");
  const [newActionItem, setNewActionItem] = useState("");
  const [newActionItems, setNewActionItems] = useState<string[]>([]);
  const [isClientShared, setIsClientShared] = useState(false);
  const [submittingNote, setSubmittingNote] = useState(false);

  // Case Link/Create Modal state
  const [linkCaseConsultation, setLinkCaseConsultation] = useState<ConsultationItem | null>(null);
  const [existingCases, setExistingCases] = useState<CaseItem[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [creatingCaseFromCon, setCreatingCaseFromCon] = useState(false);
  const [linkingCase, setLinkingCase] = useState(false);
  const [caseActionMsg, setCaseActionMsg] = useState<string | null>(null);
  const [istClock, setIstClock] = useState("");

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
      });
      const dateStr = now.toLocaleDateString("en-IN", {
        timeZone: "Asia/Kolkata",
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      });
      setIstClock(`${dateStr} • ${timeStr} IST`);
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  const fetchConsultations = useCallback(async () => {
    try {
      setFetching(true);
      setError(null);
      const res = await apiClient.get("/api/v1/consultations");
      const items: ConsultationItem[] = Array.isArray(res) ? res : res?.items || [];
      setConsultations(items);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load consultations";
      setError(msg);
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    } else if (user) {
      void fetchConsultations();
    }
  }, [user, loading, router, fetchConsultations]);

  // Tab categorization
  const filteredConsultations = useMemo(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const todayEnd = todayStart + 24 * 60 * 60 * 1000;

    return consultations.filter((con) => {
      const schedTime = con.scheduled_at ? new Date(con.scheduled_at).getTime() : 0;
      if (activeTab === "UPCOMING") {
        return (
          (con.status === "SCHEDULED" || con.status === "PAID" || con.status === "ACCEPTED" || con.status === "REQUESTED") &&
          (schedTime >= todayStart || schedTime === 0)
        );
      }
      if (activeTab === "TODAY") {
        return schedTime >= todayStart && schedTime < todayEnd;
      }
      if (activeTab === "COMPLETED") {
        return con.status === "COMPLETED";
      }
      return true; // ALL
    });
  }, [consultations, activeTab]);

  // Lawyer accepts consultation
  const handleAcceptConsultation = async (conId: string) => {
    if (acceptingId === conId) return;
    setAcceptingId(conId);
    try {
      await apiClient.post(`/api/v1/consultations/${conId}/accept`, {});
      void fetchConsultations();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to accept consultation";
      alert(msg);
    } finally {
      setAcceptingId(null);
    }
  };

  const handleAcceptAndEnter = async (conId: string) => {
    setAcceptingId(conId);
    try {
      await apiClient.post(`/api/v1/consultations/${conId}/accept`, {});
      router.push(`/consultations/${conId}/room?bypass_time=true`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to accept consultation";
      alert(msg);
      setAcceptingId(null);
    }
  };

  const activeConsultation = useMemo(() => {
    return consultations.find(
      (c) =>
        c.status === "IN_PROGRESS" ||
        c.status === "ACCEPTED" ||
        c.status === "SCHEDULED" ||
        c.status === "PAID"
    );
  }, [consultations]);

  // Fetch consultation notes
  const openNotesModal = async (con: ConsultationItem) => {
    setViewNotesConsultation(con);
    setLoadingNotes(true);
    try {
      const res = await apiClient.get(`/api/v1/consultations/${con.id}/notes`);
      setNotes(Array.isArray(res) ? res : res?.items || []);
    } catch (err) {
      console.error("Failed to load notes", err);
      setNotes([]);
    } finally {
      setLoadingNotes(false);
    }
  };

  // Submit new note
  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!viewNotesConsultation || !newNoteSummary.trim() || submittingNote) return;

    setSubmittingNote(true);
    try {
      await apiClient.post(`/api/v1/consultations/${viewNotesConsultation.id}/notes`, {
        summary: newNoteSummary.trim(),
        action_items: newActionItems,
        client_shared: isClientShared,
      });
      setNewNoteSummary("");
      setNewActionItems([]);
      void openNotesModal(viewNotesConsultation);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to add note";
      alert(msg);
    } finally {
      setSubmittingNote(false);
    }
  };

  // Open Case Link / Create modal
  const openCaseModal = async (con: ConsultationItem) => {
    setLinkCaseConsultation(con);
    setCaseActionMsg(null);
    try {
      const res = await apiClient.get("/api/v1/cases");
      setExistingCases(Array.isArray(res) ? res : res?.items || []);
    } catch (err) {
      console.error(err);
      setExistingCases([]);
    }
  };

  // Create Case from Consultation
  const handleCreateCaseFromCon = async () => {
    if (!linkCaseConsultation) return;
    setCreatingCaseFromCon(true);
    setCaseActionMsg(null);
    try {
      const defaultTitle = `Legal Matter - Consultation #${linkCaseConsultation.id.slice(0, 8).toUpperCase()}`;
      const res: Record<string, unknown> = await apiClient.post(`/api/v1/consultations/${linkCaseConsultation.id}/create-case`, {
        title: defaultTitle,
        description: `Legal matter formally established following consultation with Advocate ${linkCaseConsultation.lawyer_name || "counsel"}.`,
      });
      setCaseActionMsg(`Matter created successfully! Redirecting to workspace...`);
      setTimeout(() => {
        router.push(`/cases/${res.id || res.case_id}`);
      }, 1200);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create matter from consultation";
      setCaseActionMsg(`Error: ${msg}`);
      setCreatingCaseFromCon(false);
    }
  };

  // Link Consultation to Existing Case
  const handleLinkCase = async () => {
    if (!linkCaseConsultation || !selectedCaseId) return;
    setLinkingCase(true);
    setCaseActionMsg(null);
    try {
      await apiClient.post(`/api/v1/consultations/${linkCaseConsultation.id}/link-case`, {
        case_id: selectedCaseId,
      });
      setCaseActionMsg("Consultation successfully linked to case!");
      void fetchConsultations();
      setTimeout(() => {
        setLinkCaseConsultation(null);
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to link consultation";
      setCaseActionMsg(`Error: ${msg}`);
    } finally {
      setLinkingCase(false);
    }
  };

  const isEligibleForVideo = (con: ConsultationItem) => {
    // Authorize immediate room entry for any scheduled, paid, accepted, or active session
    return (
      con.status === "SCHEDULED" ||
      con.status === "PAID" ||
      con.status === "IN_PROGRESS" ||
      con.status === "ACCEPTED"
    );
  };

  if (loading || fetching) {
    return (
      <div style={{ padding: "40px 0" }}>
        <div className="container">
          <LoadingSkeleton type="card" count={3} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "32px 0 80px" }}>
      <div className="container">
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: "28px",
            flexWrap: "wrap",
            gap: "20px",
          }}
        >
          <div>
            <span style={{ fontSize: "12px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--navy-primary, #17324D)", display: "block", marginBottom: "4px" }}>
              Lawyer Appointments
            </span>
            <h1 style={{ fontSize: "28px", fontWeight: 800, color: "var(--navy-primary, #17324D)", margin: 0 }}>
              Appointments
            </h1>
            <p style={{ color: "var(--text-secondary, #52606D)", fontSize: "15px", marginTop: "6px" }}>
              Schedule and manage video consultations with your lawyer. {istClock ? `• ${istClock}` : ""}
            </p>
          </div>

          <Link href="/lawyers" className="btn btn-primary">
            Talk to a Lawyer
          </Link>
        </div>

        {/* High-Visibility Active Consultation Banner */}
        {activeConsultation && (
          <div
            id="active-call-quick-banner"
            style={{
              background: "var(--surface-card, #FFFFFF)",
              border: "2px solid var(--status-safe-text, #2F855A)",
              borderRadius: "14px",
              padding: "20px 24px",
              marginBottom: "24px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "16px",
              boxShadow: "var(--shadow-md)",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 700,
                    backgroundColor: "rgba(47, 133, 90, 0.1)",
                    color: "var(--status-safe-text, #2F855A)",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    textTransform: "uppercase",
                  }}
                >
                  Active Session Ready
                </span>
              </div>
              <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--navy-primary, #17324D)" }}>
                {user?.role === "LAWYER"
                  ? `Consultation with: ${activeConsultation.client_name || "Client"}`
                  : `Video Consultation with: ${activeConsultation.lawyer_name || "Advocate"}`}
              </div>
              <div style={{ fontSize: "14px", color: "var(--text-secondary, #52606D)", marginTop: "2px" }}>
                Your video meeting room is open. You can join now to discuss your matter face-to-face.
              </div>
            </div>

            <Link
              id="join-video-room-banner-btn"
              href={`/consultations/${activeConsultation.id}/room?bypass_time=true`}
              className="btn btn-primary"
              style={{
                padding: "12px 24px",
                fontSize: "15px",
                fontWeight: 700,
              }}
            >
              Join Video Meeting Now →
            </Link>
          </div>
        )}

        {/* Tab Selection */}
        <div
          style={{
            display: "flex",
            gap: "12px",
            borderBottom: "1px solid var(--border-subtle)",
            marginBottom: "28px",
            overflowX: "auto",
          }}
        >
          {(
            [
              { id: "UPCOMING", label: "Upcoming Appointments" },
              { id: "TODAY", label: "Today's Sessions" },
              { id: "COMPLETED", label: "Completed Sessions" },
              { id: "ALL", label: "All History" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                background: "none",
                border: "none",
                borderBottom: activeTab === tab.id ? "2px solid var(--accent-secondary)" : "2px solid transparent",
                padding: "12px 16px",
                fontSize: "14px",
                fontWeight: activeTab === tab.id ? 700 : 500,
                color: activeTab === tab.id ? "var(--text-primary)" : "var(--text-secondary)",
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Error Alert */}
        {error && (
          <div
            style={{
              padding: "14px 18px",
              background: "rgba(239, 68, 68, 0.12)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#ef4444",
              borderRadius: "8px",
              marginBottom: "20px",
              fontSize: "14px",
            }}
          >
            {error}
          </div>
        )}

        {/* Consultations List */}
        {filteredConsultations.length === 0 ? (
          <EmptyState
            title="No Consultations In This View"
            description="There are no appointments matching the selected view. Explore verified advocates to schedule a video consultation."
            actionLabel="Browse Verified Advocates →"
            onAction={() => router.push("/lawyers")}
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {filteredConsultations.map((con) => {
              const eligible = isEligibleForVideo(con);
              const isLawyer = user?.role === "LAWYER";
              const isClient = user?.role === "CLIENT";

              return (
                <div
                  key={con.id}
                  style={{
                    background: "var(--surface-card, #FFFFFF)",
                    border: "1px solid var(--border-subtle, #D9E2EC)",
                    borderRadius: "14px",
                    padding: "24px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "20px",
                    boxShadow: "var(--shadow-sm)",
                  }}
                >
                  {/* Left Column: Metadata */}
                  <div style={{ maxWidth: "560px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
                      <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted, #7B8794)", textTransform: "uppercase" }}>
                        Session #{con.id.slice(0, 8).toUpperCase()}
                      </span>
                      <StatusBadge status={con.status} />
                    </div>

                    <h3 style={{ fontSize: "18px", fontWeight: 700, color: "var(--navy-primary, #17324D)", margin: "0 0 6px 0" }}>
                      {isLawyer ? `Client: ${con.client_name || "Client"}` : `Lawyer: ${con.lawyer_name || "Advocate"}`}
                    </h3>

                    <div style={{ display: "flex", gap: "16px", marginTop: "8px", flexWrap: "wrap", fontSize: "13px", color: "var(--text-secondary, #52606D)" }}>
                      <span>
                        Date:{" "}
                        <strong style={{ color: "var(--text-primary, #17212B)" }}>
                          {con.scheduled_at
                            ? new Date(con.scheduled_at).toLocaleString("en-IN", {
                                timeZone: "Asia/Kolkata",
                                dateStyle: "medium",
                                timeStyle: "short",
                              }) + " IST"
                            : "To be scheduled"}
                        </strong>
                      </span>
                      <span>Duration: {con.duration_minutes || 30} mins</span>
                      <span>Fee: ₹{con.fee_amount || 2500}</span>
                      {con.case_id && (
                        <Link href={`/cases/${con.case_id}`} style={{ color: "var(--blue-soft, #3B82B6)", textDecoration: "underline" }}>
                          Linked Case
                        </Link>
                      )}
                    </div>
                  </div>

                  {/* Right Column: Actions */}
                  <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
                    {/* Video Entry */}
                    {eligible && (
                      <Link href={`/consultations/${con.id}/room?bypass_time=true`} className="btn btn-primary" style={{ padding: "8px 16px" }}>
                        Join Video Meeting →
                      </Link>
                    )}

                    {/* Lawyer Actions for Requested */}
                    {isLawyer && con.status === "REQUESTED" && (
                      <>
                        <button
                          onClick={() => handleAcceptAndEnter(con.id)}
                          disabled={acceptingId === con.id}
                          className="btn btn-primary"
                          style={{ padding: "8px 16px", opacity: acceptingId === con.id ? 0.6 : 1 }}
                        >
                          {acceptingId === con.id ? "Entering..." : "Accept & Enter"}
                        </button>
                        <button
                          onClick={() => handleAcceptConsultation(con.id)}
                          disabled={acceptingId === con.id}
                          className="btn btn-secondary"
                          style={{ padding: "8px 14px", opacity: acceptingId === con.id ? 0.6 : 1 }}
                        >
                          {acceptingId === con.id ? "Accepting..." : "Accept"}
                        </button>
                        <button
                          onClick={() => setActionModal({ type: "REJECT", consultation: con })}
                          className="btn btn-secondary"
                          style={{ padding: "8px 14px", color: "var(--status-urgent, #C53030)" }}
                        >
                          Reject
                        </button>
                      </>
                    )}

                    {/* Client Payment Action */}
                    {isClient && (con.status === "REQUESTED" || con.status === "ACCEPTED") && (
                      <button
                        onClick={() => setCheckoutConsultation(con)}
                        className="btn btn-primary"
                        style={{ padding: "8px 16px" }}
                      >
                        Pay ₹{con.fee_amount || 2500} →
                      </button>
                    )}

                    {/* Reschedule / Cancel */}
                    {(con.status === "SCHEDULED" || con.status === "PAID" || con.status === "ACCEPTED") && (
                      <>
                        <button
                          onClick={() => setActionModal({ type: "RESCHEDULE", consultation: con })}
                          className="btn btn-secondary"
                          style={{ padding: "8px 14px", fontSize: "13px" }}
                        >
                          Reschedule
                        </button>
                        <button
                          onClick={() => setActionModal({ type: "CANCEL", consultation: con })}
                          className="btn btn-secondary"
                          style={{ padding: "8px 14px", fontSize: "13px", color: "var(--status-urgent, #C53030)" }}
                        >
                          Cancel
                        </button>
                      </>
                    )}

                    {/* Completed Session Actions */}
                    {con.status === "COMPLETED" && (
                      <>

                        <button
                          onClick={() => openNotesModal(con)}
                          className="btn btn-secondary"
                          style={{ padding: "8px 14px", fontSize: "13px" }}
                        >
                          Meeting Notes
                        </button>
                        {!con.case_id && (
                          <button
                            onClick={() => openCaseModal(con)}
                            className="btn btn-secondary"
                            style={{ padding: "8px 14px", fontSize: "13px" }}
                          >
                            Create / Link Case
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Payment Checkout Modal */}
        {checkoutConsultation && (
          <PaymentCheckoutModal
            consultation={checkoutConsultation}
            onClose={() => setCheckoutConsultation(null)}
            onPaymentSuccess={() => {
              setCheckoutConsultation(null);
              void fetchConsultations();
            }}
          />
        )}

        {/* Reschedule / Cancel / Reject Action Modal */}
        {actionModal && (
          <ConsultationActionModal
            type={actionModal.type}
            consultation={actionModal.consultation}
            onClose={() => setActionModal(null)}
            onSuccess={() => {
              setActionModal(null);
              void fetchConsultations();
            }}
          />
        )}

        {/* Consultation Notes Modal */}
        {viewNotesConsultation && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.75)",
              backdropFilter: "blur(8px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
              padding: "20px",
            }}
            onClick={() => setViewNotesConsultation(null)}
          >
            <div
              style={{
                background: "var(--surface-elevated)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "28px",
                width: "100%",
                maxWidth: "600px",
                maxHeight: "85vh",
                overflowY: "auto",
                boxShadow: "var(--shadow-lg)",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px" }}>
                <div>
                  <h2 style={{ fontSize: "20px", fontWeight: 700, color: "var(--text-primary)" }}>
                    Consultation Record & Notes
                  </h2>
                  <p style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>
                    Session #{viewNotesConsultation.id.slice(0, 8).toUpperCase()}
                  </p>
                </div>
                <button
                  onClick={() => setViewNotesConsultation(null)}
                  style={{ background: "none", border: "none", color: "var(--text-muted)", fontSize: "18px", cursor: "pointer" }}
                >
                  ✕
                </button>
              </div>

              {/* Existing Notes */}
              {loadingNotes ? (
                <div style={{ padding: "20px 0", textAlign: "center", color: "var(--text-secondary)" }}>
                  Loading session notes...
                </div>
              ) : notes.length === 0 ? (
                <div style={{ padding: "16px", background: "var(--surface-card)", borderRadius: "8px", fontSize: "13px", color: "var(--text-secondary)", marginBottom: "20px" }}>
                  No consultation notes recorded yet for this session.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "24px" }}>
                  {notes.map((n) => (
                    <div
                      key={n.id}
                      style={{
                        padding: "16px",
                        background: "var(--surface-card)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "8px",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--text-muted)", marginBottom: "8px" }}>
                        <span>Recorded by {n.author_role}</span>
                        <span style={{ color: n.client_shared ? "#10b981" : "#f59e0b" }}>
                          {n.client_shared ? "● Shared with Client" : "🔒 Counsel Work Product"}
                        </span>
                      </div>
                      <p style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: 1.5 }}>
                        {n.summary}
                      </p>
                      {n.action_items && n.action_items.length > 0 && (
                        <div style={{ marginTop: "10px" }}>
                          <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                            Action Items:
                          </span>
                          <ul style={{ margin: "4px 0 0 16px", fontSize: "12px", color: "var(--text-secondary)" }}>
                            {n.action_items.map((item, idx) => (
                              <li key={idx}>{item}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Add Note Form (for Lawyer or Client) */}
              <form onSubmit={handleAddNote} style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "18px" }}>
                <h4 style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "10px" }}>
                  Add Session Summary / Action Notes
                </h4>

                <div className="input-group">
                  <textarea
                    className="input-field"
                    rows={3}
                    placeholder="Enter factual summary, key takeaways, or next steps..."
                    value={newNoteSummary}
                    onChange={(e) => setNewNoteSummary(e.target.value)}
                    required
                  />
                </div>

                <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="Add action item (e.g. Gather lease agreement)"
                    value={newActionItem}
                    onChange={(e) => setNewActionItem(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (newActionItem.trim()) {
                        setNewActionItems([...newActionItems, newActionItem.trim()]);
                        setNewActionItem("");
                      }
                    }}
                    className="btn btn-secondary"
                    style={{ whiteSpace: "nowrap" }}
                  >
                    + Add Item
                  </button>
                </div>

                {newActionItems.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "14px" }}>
                    {newActionItems.map((item, idx) => (
                      <span
                        key={idx}
                        style={{
                          background: "var(--surface-card)",
                          border: "1px solid var(--border-subtle)",
                          padding: "2px 8px",
                          borderRadius: "4px",
                          fontSize: "12px",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                        }}
                      >
                        {item}
                        <button
                          type="button"
                          onClick={() => setNewActionItems(newActionItems.filter((_, i) => i !== idx))}
                          style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer" }}
                        >
                          ✕
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                {user?.role === "LAWYER" && (
                  <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--text-secondary)", marginBottom: "16px", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={isClientShared}
                      onChange={(e) => setIsClientShared(e.target.checked)}
                    />
                    Share this record with the client (uncheck for private counsel work product)
                  </label>
                )}

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                  <button
                    type="button"
                    onClick={() => setViewNotesConsultation(null)}
                    className="btn btn-secondary"
                  >
                    Close
                  </button>
                  <button
                    type="submit"
                    className={`btn btn-primary ${submittingNote ? "btn-disabled" : ""}`}
                    disabled={submittingNote || !newNoteSummary.trim()}
                  >
                    {submittingNote ? "Saving Note..." : "Save Session Note →"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Create / Link Case Modal */}
        {linkCaseConsultation && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.75)",
              backdropFilter: "blur(8px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
              padding: "20px",
            }}
            onClick={() => setLinkCaseConsultation(null)}
          >
            <div
              style={{
                background: "var(--surface-elevated)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "28px",
                width: "100%",
                maxWidth: "500px",
                boxShadow: "var(--shadow-lg)",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <h2 style={{ fontSize: "20px", fontWeight: 700, color: "var(--text-primary)" }}>
                  Link or Create Case
                </h2>
                <button
                  onClick={() => setLinkCaseConsultation(null)}
                  style={{ background: "none", border: "none", color: "var(--text-muted)", fontSize: "18px", cursor: "pointer" }}
                >
                  ✕
                </button>
              </div>

              {caseActionMsg && (
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "6px",
                    background: caseActionMsg.startsWith("Error") ? "rgba(239, 68, 68, 0.12)" : "rgba(16, 185, 129, 0.12)",
                    color: caseActionMsg.startsWith("Error") ? "#ef4444" : "#10b981",
                    fontSize: "13px",
                    marginBottom: "16px",
                  }}
                >
                  {caseActionMsg}
                </div>
              )}

              {/* Action 1: Create New Case */}
              <div style={{ padding: "16px", background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "8px", marginBottom: "16px" }}>
                <h4 style={{ fontSize: "15px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "6px" }}>
                  Option A: Create New Legal Case
                </h4>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "12px" }}>
                  Automatically establish a new collaborative matter linking client and counsel with full evidence repository.
                </p>
                <button
                  onClick={handleCreateCaseFromCon}
                  disabled={creatingCaseFromCon}
                  className={`btn btn-primary ${creatingCaseFromCon ? "btn-disabled" : ""}`}
                  style={{ width: "100%", justifyContent: "center" }}
                >
                  {creatingCaseFromCon ? "Generating Case..." : "Generate New Case from Session →"}
                </button>
              </div>

              {/* Action 2: Link to Existing Case */}
              <div style={{ padding: "16px", background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "8px" }}>
                <h4 style={{ fontSize: "15px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "6px" }}>
                  Option B: Link to Existing Matter
                </h4>
                <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "12px" }}>
                  Attach this consultation session to an ongoing active legal matter in your portfolio.
                </p>

                <div className="input-group">
                  <select
                    className="input-field"
                    value={selectedCaseId}
                    onChange={(e) => setSelectedCaseId(e.target.value)}
                  >
                    <option value="">-- Select an Existing Matter --</option>
                    {existingCases.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.title} (#{c.id.slice(0, 6)})
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  onClick={handleLinkCase}
                  disabled={linkingCase || !selectedCaseId}
                  className={`btn btn-secondary ${linkingCase || !selectedCaseId ? "btn-disabled" : ""}`}
                  style={{ width: "100%", justifyContent: "center" }}
                >
                  {linkingCase ? "Linking Matter..." : "Link to Selected Matter →"}
                </button>
              </div>
            </div>
          </div>
        )}


      </div>
    </div>
  );
}
