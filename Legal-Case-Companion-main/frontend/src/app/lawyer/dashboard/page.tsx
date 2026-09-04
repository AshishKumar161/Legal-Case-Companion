"use client";

import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { apiClient } from "@/api/client";
import Link from "next/link";
import { CaseItem, LawyerProfileItem, ConsultationItem } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { ConsultationActionModal } from "@/components/Consultation/ConsultationActionModal";

export default function LawyerDashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<LawyerProfileItem | null>(null);
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [consultations, setConsultations] = useState<ConsultationItem[]>([]);
  const [fetching, setFetching] = useState(true);
  const [actionModal, setActionModal] = useState<{
    type: "RESCHEDULE" | "CANCEL" | "REJECT" | "NO_SHOW" | "COMPLETE" | "SCHEDULE";
    consultation: ConsultationItem;
  } | null>(null);

  const [incomingCall, setIncomingCall] = useState<any | null>(null);
  const [dismissedCallId, setDismissedCallId] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState(false);

  // Periodic presence heartbeat so the lawyer is marked ONLINE while tab is open
  useEffect(() => {
    if (!user || (user.role !== "LAWYER" && user.role !== "ADMIN")) return;
    const sendHeartbeat = async () => {
      try {
        await apiClient.post("/api/v1/lawyers/heartbeat", {});
        setIsOnline(true);
      } catch {
        // ignore
      }
    };
    void sendHeartbeat();
    const hbInterval = setInterval(sendHeartbeat, 15000);
    return () => clearInterval(hbInterval);
  }, [user]);

  // Real-time WebSocket incoming call alerts + reconnection resynchronization
  useEffect(() => {
    if (!user || (user.role !== "LAWYER" && user.role !== "ADMIN")) return;

    let ws: WebSocket | null = null;
    let pingInterval: NodeJS.Timeout | null = null;
    let reconnectTimeout: NodeJS.Timeout | null = null;
    let isSubscribed = true;

    const reconcileActiveCalls = async () => {
      try {
        const calls: any = await apiClient.get("/api/v1/consultations/incoming-calls");
        if (Array.isArray(calls) && calls.length > 0) {
          const latest = calls[0];
          if (latest.id !== dismissedCallId) {
            setIncomingCall(latest);
          }
        } else {
          setIncomingCall(null);
        }
      } catch {
        // ignore
      }
    };

    const connectWebSocket = async () => {
      if (!isSubscribed) return;

      // Reconcile active state on connect/reconnect
      await reconcileActiveCalls();

      try {
        const ticketRes: any = await apiClient.post("/api/v1/consultations/ws-ticket", {});
        if (!ticketRes?.ticket || !isSubscribed) return;

        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        const wsProto = apiUrl.startsWith("https") ? "wss" : "ws";
        const host = apiUrl.replace(/^https?:\/\//, "");
        const wsUrl = `${wsProto}://${host}/api/v1/consultations/ws/incoming-calls?ticket=${ticketRes.ticket}`;

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          setIsOnline(true);
          pingInterval = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send("ping");
            }
          }, 15000);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "incoming_consultation") {
              if (data.consultation_id !== dismissedCallId) {
                setIncomingCall({
                  id: data.consultation_id,
                  client_name: data.client_name,
                  fee: data.fee,
                  case_id: data.case_id,
                  created_at: data.created_at,
                  ring_timeout_seconds: data.ring_timeout_seconds,
                });
              }
            } else if (
              data.type === "consultation_accepted" ||
              data.type === "consultation_cancelled" ||
              data.type === "consultation_expired"
            ) {
              setIncomingCall((prev: any) =>
                prev && prev.id === data.consultation_id ? null : prev
              );
            }
          } catch {
            // raw message e.g. pong
          }
        };

        ws.onclose = () => {
          if (pingInterval) clearInterval(pingInterval);
          if (isSubscribed) {
            reconnectTimeout = setTimeout(() => {
              void connectWebSocket();
            }, 3000);
          }
        };

        ws.onerror = () => {
          if (ws) ws.close();
        };
      } catch {
        if (isSubscribed) {
          reconnectTimeout = setTimeout(() => {
            void connectWebSocket();
          }, 5000);
        }
      }
    };

    void connectWebSocket();

    // Secondary safety poll (15s interval)
    const backupInterval = setInterval(reconcileActiveCalls, 15000);

    return () => {
      isSubscribed = false;
      if (pingInterval) clearInterval(pingInterval);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      clearInterval(backupInterval);
      if (ws) ws.close();
    };
  }, [user, dismissedCallId]);

  const handleAcceptIncomingCall = async (callId: string) => {
    try {
      await apiClient.post(`/api/v1/consultations/${callId}/accept`, {}).catch(() => {});
      router.push(`/consultations/${callId}/room`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to enter room";
      alert(msg);
    }
  };

  const fetchLawyerData = useCallback(async () => {
    try {
      setFetching(true);
      const [profileRes, casesRes, consultRes] = await Promise.all([
        apiClient.get("/api/v1/profiles/me").catch(() => null),
        apiClient.get("/api/v1/cases").catch(() => []),
        apiClient.get("/api/v1/consultations").catch(() => []),
      ]);
      setProfile(profileRes);
      setCases(casesRes?.items || (Array.isArray(casesRes) ? casesRes : []));
      setConsultations(consultRes?.items || (Array.isArray(consultRes) ? consultRes : []));
    } catch (err) {
      console.error(err);
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    } else if (user && user.role !== "LAWYER" && user.role !== "ADMIN") {
      router.push("/dashboard");
    } else if (user) {
      void fetchLawyerData();
    }
  }, [user, loading, router, fetchLawyerData]);

  if (loading || fetching || !user) {
    return (
      <div style={{ padding: "40px 0" }}>
        <div className="container">
          <LoadingSkeleton type="card" count={3} />
        </div>
      </div>
    );
  }

  const isVerified = profile?.verification_status === "VERIFIED";

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
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "11px",
                fontWeight: 700,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "var(--accent-secondary)",
                marginBottom: "8px",
              }}
            >
              <span>●</span> Advocate Practice Operating Suite
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
              <h1 style={{ fontSize: "28px", fontWeight: 700, color: "var(--text-primary)" }}>
                Advocate Chambers: {profile?.full_name || user.email.split("@")[0]}
              </h1>
              <StatusBadge
                status={isVerified ? "VERIFIED" : "PENDING"}
                label={isVerified ? "Verified Bar Counsel" : "Verification Pending"}
              />
              {isOnline && (
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "4px 10px",
                    borderRadius: "20px",
                    fontSize: "12px",
                    fontWeight: 600,
                    backgroundColor: "rgba(16, 185, 129, 0.15)",
                    color: "#10b981",
                    border: "1px solid rgba(16, 185, 129, 0.3)",
                  }}
                >
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "#10b981" }}></span>
                  🟢 Online & Visible to Clients
                </span>
              )}
            </div>
            <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginTop: "6px", maxWidth: "680px" }}>
              Oversee retained client matters, inspect statutory limitation vulnerabilities, examine AI-grounded legal briefs, and conduct scheduled video conferences.
            </p>
          </div>

          <div style={{ display: "flex", gap: "12px" }}>
            <Link href="/lawyer/profile" className="btn btn-secondary">
              ⚙ Availability & Bar Profile
            </Link>
          </div>
        </div>

        {/* Incoming Consultation Call Alert */}
        {incomingCall && (
          <div
            style={{
              padding: "20px 24px",
              marginBottom: "28px",
              borderRadius: "var(--radius-md)",
              background: "linear-gradient(135deg, rgba(79, 91, 247, 0.18), rgba(16, 185, 129, 0.18))",
              border: "2px solid #4f5bf7",
              boxShadow: "0 8px 30px rgba(79, 91, 247, 0.25)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "16px",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                <span style={{ fontSize: "22px" }}>🚨</span>
                <span style={{ fontSize: "17px", fontWeight: 700, color: "#fff" }}>
                  Incoming Video Consultation Request!
                </span>
                <span
                  style={{
                    fontSize: "11px",
                    padding: "3px 8px",
                    borderRadius: "4px",
                    background: "#10b981",
                    color: "#fff",
                    fontWeight: 700,
                  }}
                >
                  ₹{incomingCall.fee_amount} PAID
                </span>
              </div>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", margin: 0 }}>
                Client <strong>{incomingCall.client_name}</strong> has paid and authorized an immediate video consultation. Both permissions granted.
              </p>
            </div>
            <div style={{ display: "flex", gap: "10px" }}>
              <button
                onClick={() => handleAcceptIncomingCall(incomingCall.id)}
                className="btn btn-primary"
                style={{
                  padding: "10px 22px",
                  fontSize: "14px",
                  fontWeight: 700,
                  background: "linear-gradient(135deg, #10b981, #059669)",
                  border: "none",
                  boxShadow: "0 4px 14px rgba(16, 185, 129, 0.4)",
                  cursor: "pointer",
                }}
              >
                ✅ Accept & Enter Video Room 🎥
              </button>
              <button
                onClick={() => {
                  setDismissedCallId(incomingCall.id);
                  setIncomingCall(null);
                }}
                className="btn btn-secondary"
                style={{ padding: "10px 16px", fontSize: "13px" }}
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Bar Verification Banner if Pending */}
        {!isVerified && (
          <div
            style={{
              padding: "16px 20px",
              marginBottom: "28px",
              borderRadius: "var(--radius-md)",
              background: "rgba(245, 158, 11, 0.08)",
              border: "1px solid rgba(245, 158, 11, 0.3)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <div style={{ fontSize: "13px", color: "#f59e0b" }}>
              <strong>State Bar Council Notice:</strong> Your enrollment credentials are currently pending review by platform administrators. You retain full access to active matter workspaces.
            </div>
            <Link
              href="/lawyer/profile"
              style={{
                fontSize: "12px",
                color: "#fff",
                background: "rgba(245, 158, 11, 0.3)",
                padding: "6px 12px",
                borderRadius: "6px",
                fontWeight: 600,
              }}
            >
              Inspect Enrollment Info →
            </Link>
          </div>
        )}

        {/* Operational Metrics Row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "16px",
            marginBottom: "32px",
          }}
        >
          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "20px",
            }}
          >
            <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Active Retained Matters
            </div>
            <div style={{ fontSize: "32px", fontWeight: 700, color: "var(--accent-secondary)", marginTop: "6px" }}>
              {cases.length}
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
              {cases.filter((c) => c.status === "OPEN" || c.status === "IN_PROGRESS").length} matters currently active
            </div>
          </div>

          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "20px",
            }}
          >
            <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Scheduled Consultations
            </div>
            <div style={{ fontSize: "32px", fontWeight: 700, color: "#10b981", marginTop: "6px" }}>
              {consultations.length}
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
              Booked client video & chamber sessions
            </div>
          </div>

          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "20px",
            }}
          >
            <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Standing & Experience
            </div>
            <div style={{ fontSize: "20px", fontWeight: 700, color: "#8b5cf6", marginTop: "10px" }}>
              {profile?.experience_years ? `${profile.experience_years} Years at the Bar` : "Senior Counsel"}
            </div>
            <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
              {profile?.location || "India"}
            </div>
          </div>
        </div>

        {/* Main Grid: Cases & Consultations */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "24px", alignItems: "flex-start" }}>
          {/* Matters Section */}
          <section>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text-primary)" }}>
                Retained Matters ({cases.length})
              </h2>
            </div>

            {cases.length === 0 ? (
              <EmptyState
                icon="⚖"
                title="No Assigned Matters"
                description="When clients retain you or add your verified account as counsel, active matter workspaces will appear here."
              />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                {cases.map((c) => (
                  <Link
                    key={c.id}
                    href={`/cases/${c.id}`}
                    style={{
                      background: "var(--surface-card)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "var(--radius-md)",
                      padding: "18px 20px",
                      display: "block",
                      transition: "all 0.15s ease",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                        <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#fff" }}>
                          {c.title}
                        </h3>
                        <span style={{ fontFamily: "monospace", fontSize: "11px", color: "var(--text-muted)" }}>
                          #{c.id.slice(0, 8).toUpperCase()}
                        </span>
                      </div>
                      <StatusBadge status={c.status} />
                    </div>

                    <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: "12px" }}>
                      {c.description || "No formal matter summary recorded."}
                    </p>

                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        borderTop: "1px solid var(--border-subtle)",
                        paddingTop: "10px",
                        fontSize: "12px",
                        color: "var(--text-muted)",
                      }}
                    >
                      <span>Created {new Date(c.created_at).toLocaleDateString("en-IN")}</span>
                      <span style={{ color: "var(--accent-secondary)", fontWeight: 600 }}>
                        Open Case Workspace →
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>

          {/* Consultations Sidebar */}
          <aside>
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <h3 style={{ fontSize: "14px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-secondary)" }}>
                  📅 Scheduled Sessions
                </h3>
              </div>

              {consultations.length === 0 ? (
                <p style={{ fontSize: "13px", color: "var(--text-muted)", textAlign: "center", padding: "20px 0" }}>
                  No consultations booked in this calendar window.
                </p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {consultations.map((con) => (
                    <div
                      key={con.id}
                      style={{
                        background: "var(--surface-subtle)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "8px",
                        padding: "12px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "6px",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <StatusBadge status={con.status} />
                        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                          {new Date(con.scheduled_start).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                        </span>
                      </div>
                      <div style={{ fontSize: "13px", color: "#fff", fontWeight: 500 }}>
                        {new Date(con.scheduled_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        {" - "}
                        {new Date(con.scheduled_end).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--text-muted)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span>Fee: ₹{(con.fee_amount ?? 2500).toLocaleString("en-IN")}</span>
                        {con.status === "PAID" && (
                          <span style={{ color: "#10b981", fontWeight: 600 }}>✓ Paid</span>
                        )}
                      </div>
                      {con.meeting_url && (
                        <a
                          href={con.meeting_url}
                          target="_blank"
                          rel="noreferrer"
                          style={{ fontSize: "12px", color: "var(--accent-secondary)", fontWeight: 600, marginTop: "4px" }}
                        >
                          Join Video Session ↗
                        </a>
                      )}

                      {/* Advocate Consultation Lifecycle Actions */}
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "8px" }}>
                        {con.status === "REQUESTED" && (
                          <>
                            <button
                              onClick={async () => {
                                try {
                                  await apiClient.post(`/api/v1/consultations/${con.id}/accept`, {});
                                  void fetchLawyerData();
                                } catch (err: unknown) {
                                  alert(err instanceof Error ? err.message : "Failed to accept");
                                }
                              }}
                              style={{
                                padding: "4px 8px",
                                borderRadius: "4px",
                                background: "linear-gradient(135deg, #10b981, #059669)",
                                color: "#fff",
                                border: "none",
                                fontSize: "11px",
                                fontWeight: 600,
                                cursor: "pointer",
                              }}
                            >
                              Accept
                            </button>
                            <button
                              onClick={() => setActionModal({ type: "REJECT", consultation: con })}
                              style={{
                                padding: "4px 8px",
                                borderRadius: "4px",
                                background: "rgba(239, 68, 68, 0.12)",
                                border: "1px solid rgba(239, 68, 68, 0.3)",
                                color: "#ef4444",
                                fontSize: "11px",
                                fontWeight: 500,
                                cursor: "pointer",
                              }}
                            >
                              Decline
                            </button>
                          </>
                        )}

                        {(con.status === "PAID" || con.status === "ACCEPTED") && (
                          <button
                            onClick={() => setActionModal({ type: "SCHEDULE", consultation: con })}
                            style={{
                              padding: "4px 8px",
                              borderRadius: "4px",
                              background: "linear-gradient(135deg, #3b82f6, #2563eb)",
                              color: "#fff",
                              border: "none",
                              fontSize: "11px",
                              fontWeight: 600,
                              cursor: "pointer",
                            }}
                          >
                            📅 Schedule Slot
                          </button>
                        )}

                        {(con.status === "SCHEDULED" || con.status === "IN_PROGRESS") && (
                          <>
                            <a
                              href={`/consultations/${con.id}/room`}
                              style={{
                                padding: "4px 10px",
                                borderRadius: "4px",
                                background: "#2563eb",
                                color: "#fff",
                                fontSize: "11px",
                                fontWeight: 600,
                                textDecoration: "none",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "4px",
                              }}
                            >
                              🎥 Join Video Room
                            </a>
                            <button
                              onClick={() => setActionModal({ type: "COMPLETE", consultation: con })}
                              style={{
                                padding: "4px 8px",
                                borderRadius: "4px",
                                background: "rgba(16, 185, 129, 0.15)",
                                border: "1px solid rgba(16, 185, 129, 0.3)",
                                color: "#10b981",
                                fontSize: "11px",
                                fontWeight: 600,
                                cursor: "pointer",
                              }}
                            >
                              ✓ Complete
                            </button>
                            <button
                              onClick={() => setActionModal({ type: "NO_SHOW", consultation: con })}
                              style={{
                                padding: "4px 8px",
                                borderRadius: "4px",
                                background: "rgba(245, 158, 11, 0.15)",
                                border: "1px solid rgba(245, 158, 11, 0.3)",
                                color: "#f59e0b",
                                fontSize: "11px",
                                fontWeight: 500,
                                cursor: "pointer",
                              }}
                            >
                              No-Show
                            </button>
                          </>
                        )}

                        {["REQUESTED", "ACCEPTED", "PAID", "SCHEDULED"].includes(con.status) && (
                          <>
                            <button
                              onClick={() => setActionModal({ type: "RESCHEDULE", consultation: con })}
                              style={{
                                padding: "4px 8px",
                                borderRadius: "4px",
                                background: "rgba(96, 165, 250, 0.12)",
                                border: "1px solid rgba(96, 165, 250, 0.3)",
                                color: "#60a5fa",
                                fontSize: "11px",
                                fontWeight: 500,
                                cursor: "pointer",
                              }}
                            >
                              ↻ Reschedule
                            </button>
                            <button
                              onClick={() => setActionModal({ type: "CANCEL", consultation: con })}
                              style={{
                                padding: "4px 8px",
                                borderRadius: "4px",
                                background: "rgba(239, 68, 68, 0.12)",
                                border: "1px solid rgba(239, 68, 68, 0.3)",
                                color: "#ef4444",
                                fontSize: "11px",
                                fontWeight: 500,
                                cursor: "pointer",
                              }}
                            >
                              Cancel
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </aside>
        </div>
      </div>

      {actionModal && (
        <ConsultationActionModal
          type={actionModal.type}
          consultation={actionModal.consultation}
          onClose={() => setActionModal(null)}
          onSuccess={() => {
            setActionModal(null);
            void fetchLawyerData();
          }}
        />
      )}
    </div>
  );
}
