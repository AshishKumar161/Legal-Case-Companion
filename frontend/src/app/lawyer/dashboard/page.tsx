"use client";

import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { apiClient } from "@/api/client";
import Link from "next/link";
import {
  CaseItem,
  LawyerProfileItem,
  ConsultationItem,
  LawyerDashboardResponse,
} from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { ConsultationActionModal } from "@/components/Consultation/ConsultationActionModal";
import { WhatChangedBanner } from "@/components/WhatChangedBanner";
import { PageHeader } from "@/components/ui";

export default function LawyerDashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<LawyerProfileItem | null>(null);
  const [, setCases] = useState<CaseItem[]>([]);
  const [consultations, setConsultations] = useState<ConsultationItem[]>([]);
  const [dashboardData, setDashboardData] = useState<LawyerDashboardResponse | null>(null);
  const [rangeDays, setRangeDays] = useState<number>(14);
  const [fetching, setFetching] = useState(true);
  const [mattersFilter, setMattersFilter] = useState<"ALL" | "ATTENTION" | "ACTIVE">("ALL");
  const [mattersSearch, setMattersSearch] = useState<string>("");

  const [actionModal, setActionModal] = useState<{
    type: "RESCHEDULE" | "CANCEL" | "REJECT" | "NO_SHOW" | "COMPLETE" | "SCHEDULE";
    consultation: ConsultationItem;
  } | null>(null);

  interface IncomingCallPayload {
    id: string;
    client_name: string;
    fee_amount: number;
    case_id?: string;
    created_at?: string;
    ring_timeout_seconds?: number;
  }

  const [incomingCall, setIncomingCall] = useState<IncomingCallPayload | null>(null);
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
        const calls = await apiClient.get<IncomingCallPayload[]>("/api/v1/consultations/incoming-calls");
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

      await reconcileActiveCalls();

      try {
        const ticketRes = await apiClient.post<{ ticket?: string }>("/api/v1/consultations/ws-ticket", {});
        if (!ticketRes?.ticket || !isSubscribed) return;

        let wsProto = "ws";
        let host = "127.0.0.1:8000";
        if (typeof window !== "undefined") {
          wsProto = window.location.protocol === "https:" ? "wss" : "ws";
          host = window.location.host;
        }
        if (process.env.NEXT_PUBLIC_API_URL) {
          const customUrl = process.env.NEXT_PUBLIC_API_URL;
          wsProto = customUrl.startsWith("https") ? "wss" : "ws";
          host = customUrl.replace(/^https?:\/\//, "");
        }
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
                  fee_amount: data.fee,
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
              setIncomingCall((prev) =>
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
      const [profileRes, casesRes, consultRes, dashRes] = await Promise.all([
        apiClient.get<LawyerProfileItem>("/api/v1/profiles/me").catch(() => null),
        apiClient.get<{ items: CaseItem[] } | CaseItem[]>("/api/v1/cases").catch(() => []),
        apiClient.get<{ items: ConsultationItem[] } | ConsultationItem[]>("/api/v1/consultations").catch(() => []),
        apiClient.get<LawyerDashboardResponse>(`/api/v1/lawyers/dashboard?days_ahead=${rangeDays}`).catch(() => null),
      ]);
      setProfile(profileRes);
      if (casesRes) {
        setCases("items" in casesRes ? casesRes.items : (Array.isArray(casesRes) ? casesRes : []));
      }
      if (consultRes) {
        setConsultations("items" in consultRes ? consultRes.items : (Array.isArray(consultRes) ? consultRes : []));
      }
      setDashboardData(dashRes);
    } catch (err) {
      console.error("Error loading lawyer operational dashboard:", err);
    } finally {
      setFetching(false);
    }
  }, [rangeDays]);

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
          <LoadingSkeleton type="card" count={4} />
        </div>
      </div>
    );
  }

  const isVerified = profile?.verification_status === "VERIFIED";
  const metrics = dashboardData?.metrics || {
    active_cases_count: 0,
    upcoming_hearings_count: 0,
    overdue_tasks_count: 0,
    upcoming_deadlines_count: 0,
    pending_consultations_count: 0,
    unread_notifications_count: 0,
  };

  const todayAgenda = dashboardData?.today_agenda || [];
  const needsAttention = dashboardData?.needs_attention || [];
  const upcomingHearings = dashboardData?.upcoming_hearings || [];
  const upcomingDeadlines = dashboardData?.upcoming_deadlines || [];
  const highPriorityTasks = dashboardData?.high_priority_tasks || [];
  const assignedMatters = dashboardData?.assigned_matters || [];

  // Filter assigned matters
  const filteredMatters = assignedMatters.filter((m) => {
    if (mattersFilter === "ATTENTION" && m.overdue_tasks_count === 0 && !m.next_hearing_at) {
      return false;
    }
    if (mattersFilter === "ACTIVE" && m.status !== "OPEN" && m.status !== "IN_PROGRESS") {
      return false;
    }
    if (mattersSearch.trim()) {
      const q = mattersSearch.toLowerCase();
      const matchTitle = m.title.toLowerCase().includes(q);
      const matchCourt = m.court_name ? m.court_name.toLowerCase().includes(q) : false;
      const matchNum = m.case_number ? m.case_number.toLowerCase().includes(q) : false;
      return matchTitle || matchCourt || matchNum;
    }
    return true;
  });

  return (
    <div style={{ padding: "28px 0 80px" }}>
      <div className="container">
        {/* Chambers Hero Header using PageHeader */}
        <PageHeader
          eyebrow="Advocate Operational Control Center"
          eyebrowColor="var(--accent-secondary)"
          title={`Advocate Chambers: ${profile?.full_name || user.email.split("@")[0]}`}
          badge={
            <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
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
                    padding: "3px 10px",
                    borderRadius: "20px",
                    fontSize: "12px",
                    fontWeight: 600,
                    backgroundColor: "rgba(16, 185, 129, 0.15)",
                    color: "#10b981",
                    border: "1px solid rgba(16, 185, 129, 0.3)",
                  }}
                >
                  <span style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "#10b981" }}></span>
                  🟢 Online
                </span>
              )}
            </div>
          }
          description="Zero-AI deterministic operations. Track today's hearing agenda, court bundle readiness, statutory limitation cutoffs, and client action items."
          actions={
            <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
              {/* Date Range Selector */}
              <div style={{ display: "flex", alignItems: "center", gap: "6px", background: "var(--surface-card)", padding: "4px 8px", borderRadius: "6px", border: "1px solid var(--border-subtle)" }}>
                <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 600 }}>Window:</span>
                <select
                  value={rangeDays}
                  onChange={(e) => setRangeDays(Number(e.target.value))}
                  style={{
                    background: "transparent",
                    color: "#fff",
                    border: "none",
                    fontSize: "12px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  <option value={7} style={{ background: "#1a1f2c" }}>Next 7 Days</option>
                  <option value={14} style={{ background: "#1a1f2c" }}>Next 14 Days</option>
                  <option value={30} style={{ background: "#1a1f2c" }}>Next 30 Days</option>
                </select>
              </div>

              <button
                onClick={() => void fetchLawyerData()}
                className="btn btn-secondary"
                style={{ padding: "6px 12px", fontSize: "12px" }}
                title="Refresh real-time operational data"
              >
                🔄 Refresh
              </button>

              <Link href="/calendar" className="btn btn-secondary" style={{ padding: "6px 12px", fontSize: "12px" }}>
                📅 Calendar
              </Link>

              <Link href="/lawyer/profile" className="btn btn-secondary" style={{ padding: "6px 12px", fontSize: "12px" }}>
                ⚙ Settings
              </Link>
            </div>
          }
        />

        {/* Incoming Consultation Call Alert */}
        {incomingCall && (
          <div
            style={{
              padding: "18px 22px",
              marginBottom: "24px",
              borderRadius: "var(--radius-md)",
              background: "linear-gradient(135deg, rgba(79, 91, 247, 0.2), rgba(16, 185, 129, 0.2))",
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
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
                <span style={{ fontSize: "20px" }}>🚨</span>
                <span style={{ fontSize: "16px", fontWeight: 700, color: "#fff" }}>
                  Incoming Video Consultation Request!
                </span>
                <span
                  style={{
                    fontSize: "11px",
                    padding: "2px 8px",
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
                Client <strong>{incomingCall.client_name}</strong> is waiting in the secure video room.
              </p>
            </div>
            <div style={{ display: "flex", gap: "10px" }}>
              <button
                onClick={() => handleAcceptIncomingCall(incomingCall.id)}
                className="btn btn-primary"
                style={{
                  padding: "8px 18px",
                  fontSize: "13px",
                  fontWeight: 700,
                  background: "linear-gradient(135deg, #10b981, #059669)",
                  border: "none",
                  boxShadow: "0 4px 14px rgba(16, 185, 129, 0.4)",
                  cursor: "pointer",
                }}
              >
                ✅ Accept & Enter Room 🎥
              </button>
              <button
                onClick={() => {
                  setDismissedCallId(incomingCall.id);
                  setIncomingCall(null);
                }}
                className="btn btn-secondary"
                style={{ padding: "8px 14px", fontSize: "12px" }}
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
              padding: "12px 18px",
              marginBottom: "20px",
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
              <strong>State Bar Council Notice:</strong> Your enrollment credentials are under administrative review. You retain full access to active matter workspaces.
            </div>
            <Link
              href="/lawyer/profile"
              style={{
                fontSize: "12px",
                color: "#fff",
                background: "rgba(245, 158, 11, 0.3)",
                padding: "4px 10px",
                borderRadius: "6px",
                fontWeight: 600,
              }}
            >
              Inspect Enrollment →
            </Link>
          </div>
        )}

        {/* What Changed Since Your Last Visit Banner */}
        <WhatChangedBanner />

        {/* 1. OPERATIONAL KPI METRICS STRIP */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "14px",
            marginBottom: "24px",
          }}
        >
          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "16px",
            }}
          >
            <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Active Matters
            </div>
            <div style={{ fontSize: "28px", fontWeight: 800, color: "var(--accent-secondary)", marginTop: "4px" }}>
              {metrics.active_cases_count}
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
              Retained client cases
            </div>
          </div>

          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "16px",
            }}
          >
            <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Upcoming Hearings
            </div>
            <div style={{ fontSize: "28px", fontWeight: 800, color: "#38bdf8", marginTop: "4px" }}>
              {metrics.upcoming_hearings_count}
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
              Listed in next {rangeDays} days
            </div>
          </div>

          <div
            style={{
              background: "var(--surface-card)",
              border: metrics.overdue_tasks_count > 0 ? "1px solid rgba(239, 68, 68, 0.4)" : "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "16px",
            }}
          >
            <div style={{ fontSize: "11px", color: metrics.overdue_tasks_count > 0 ? "#f87171" : "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Overdue Tasks
            </div>
            <div style={{ fontSize: "28px", fontWeight: 800, color: metrics.overdue_tasks_count > 0 ? "#ef4444" : "#10b981", marginTop: "4px" }}>
              {metrics.overdue_tasks_count}
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
              {metrics.overdue_tasks_count > 0 ? "Requires prompt action" : "All tasks up to date"}
            </div>
          </div>

          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "16px",
            }}
          >
            <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Upcoming Deadlines
            </div>
            <div style={{ fontSize: "28px", fontWeight: 800, color: "#fbbf24", marginTop: "4px" }}>
              {metrics.upcoming_deadlines_count}
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
              Statutory cutoffs & filings
            </div>
          </div>

          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "16px",
            }}
          >
            <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Consultations
            </div>
            <div style={{ fontSize: "28px", fontWeight: 800, color: "#10b981", marginTop: "4px" }}>
              {metrics.pending_consultations_count}
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
              Pending client bookings
            </div>
          </div>

          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "16px",
            }}
          >
            <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Notifications
            </div>
            <div style={{ fontSize: "28px", fontWeight: 800, color: "#a855f7", marginTop: "4px" }}>
              {metrics.unread_notifications_count}
            </div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
              Unread system alerts
            </div>
          </div>
        </div>

        {/* 2. OPERATIONAL NEEDS ATTENTION RADAR (ZERO AI) */}
        {needsAttention.length > 0 && (
          <div
            style={{
              background: "linear-gradient(135deg, rgba(26, 18, 20, 0.95), rgba(35, 20, 24, 0.95))",
              border: "1px solid rgba(239, 68, 68, 0.35)",
              borderRadius: "var(--radius-md)",
              padding: "18px 20px",
              marginBottom: "28px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "16px" }}>⚡</span>
                <span style={{ fontSize: "14px", fontWeight: 700, color: "#f87171", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                  Operational Radar: Items Requiring Immediate Attention ({needsAttention.length})
                </span>
              </div>
              <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                Deterministic operational flags · Zero AI inference
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "10px" }}>
              {needsAttention.slice(0, 6).map((item) => (
                <div
                  key={item.item_id}
                  style={{
                    background: "rgba(0, 0, 0, 0.35)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: "6px",
                    padding: "12px 14px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    gap: "12px",
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px" }}>
                      <span
                        style={{
                          fontSize: "10px",
                          fontWeight: 700,
                          padding: "2px 6px",
                          borderRadius: "4px",
                          background: item.severity === "URGENT" ? "rgba(239, 68, 68, 0.2)" : item.severity === "WARNING" ? "rgba(245, 158, 11, 0.2)" : "rgba(56, 189, 248, 0.2)",
                          color: item.severity === "URGENT" ? "#f87171" : item.severity === "WARNING" ? "#fbbf24" : "#38bdf8",
                        }}
                      >
                        {item.severity}
                      </span>
                      <strong style={{ fontSize: "13px", color: "#fff", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {item.title}
                      </strong>
                    </div>
                    <div style={{ fontSize: "11px", color: "#cbd5e1", lineHeight: 1.4, marginBottom: "4px" }}>
                      {item.reason}
                    </div>
                    <div style={{ fontSize: "10px", color: "var(--text-muted)" }}>
                      Matter: <strong>{item.case_title}</strong>
                    </div>
                  </div>

                  <Link
                    href={item.action_href}
                    className="btn btn-secondary"
                    style={{ padding: "5px 10px", fontSize: "11px", whiteSpace: "nowrap", alignSelf: "center" }}
                  >
                    {item.action_label} →
                  </Link>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 3. MAIN WORKSPACE GRID: AGENDA & HEARINGS ON LEFT, SIDEBAR ON RIGHT */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "24px", alignItems: "flex-start", marginBottom: "32px" }}>
          {/* LEFT COLUMN: Operations Command */}
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            {/* Today's Operational Agenda */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px 22px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <div>
                  <h2 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                    📅 Today&apos;s Operational Agenda
                  </h2>
                  <p style={{ fontSize: "12px", color: "var(--text-muted)", margin: "2px 0 0 0" }}>
                    Chronological schedule of listed hearings, due tasks, deadlines, and consultations.
                  </p>
                </div>
                <span style={{ fontSize: "12px", color: "var(--accent-secondary)", fontWeight: 600 }}>
                  {todayAgenda.length} item(s) today
                </span>
              </div>

              {todayAgenda.length === 0 ? (
                <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px", background: "rgba(255,255,255,0.02)", borderRadius: "6px" }}>
                  ✅ No court hearings or items due today. Review upcoming hearings and preparation readiness below.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {todayAgenda.map((item) => (
                    <div
                      key={item.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "12px 14px",
                        borderRadius: "6px",
                        background: item.is_urgent ? "rgba(239, 68, 68, 0.06)" : "rgba(255, 255, 255, 0.03)",
                        border: item.is_urgent ? "1px solid rgba(239, 68, 68, 0.25)" : "1px solid rgba(255, 255, 255, 0.05)",
                        gap: "12px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "12px", minWidth: 0 }}>
                        <div
                          style={{
                            fontSize: "12px",
                            fontWeight: 700,
                            padding: "4px 8px",
                            borderRadius: "4px",
                            whiteSpace: "nowrap",
                            background: item.event_type === "HEARING" ? "rgba(56, 189, 248, 0.15)" : item.event_type === "DEADLINE" ? "rgba(251, 191, 36, 0.15)" : item.event_type === "CONSULTATION" ? "rgba(16, 185, 129, 0.15)" : "rgba(168, 85, 247, 0.15)",
                            color: item.event_type === "HEARING" ? "#38bdf8" : item.event_type === "DEADLINE" ? "#fbbf24" : item.event_type === "CONSULTATION" ? "#10b981" : "#a855f7",
                          }}
                        >
                          {item.time_display}
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: "13px", fontWeight: 600, color: "#fff", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                            {item.title}
                          </div>
                          <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                            Matter: <strong>{item.case_title}</strong> {item.court_info ? `· ${item.court_info}` : ""}
                          </div>
                        </div>
                      </div>

                      <Link
                        href={item.action_href}
                        className="btn btn-secondary"
                        style={{ padding: "4px 10px", fontSize: "11px", whiteSpace: "nowrap" }}
                      >
                        {item.action_label} →
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Upcoming Court Hearings with Preparation Readiness */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px 22px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <div>
                  <h2 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                    🏛 Upcoming Court Hearings & Bundle Readiness
                  </h2>
                  <p style={{ fontSize: "12px", color: "var(--text-muted)", margin: "2px 0 0 0" }}>
                    Track preparation tasks completion, exhibit markers, and Bates-stamped court bundles.
                  </p>
                </div>
                <Link href="/court-tracking" style={{ fontSize: "12px", color: "var(--accent-secondary)", fontWeight: 600 }}>
                  Track Cause List →
                </Link>
              </div>

              {upcomingHearings.length === 0 ? (
                <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px", background: "rgba(255,255,255,0.02)", borderRadius: "6px" }}>
                  No upcoming court hearings listed in the next {rangeDays} days.
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "12px" }}>
                  {upcomingHearings.map((h) => {
                    const taskPct = h.preparation_tasks_total > 0 ? Math.round((h.preparation_tasks_completed / h.preparation_tasks_total) * 100) : 100;
                    return (
                      <div
                        key={h.hearing_id}
                        style={{
                          background: "rgba(255, 255, 255, 0.02)",
                          border: "1px solid rgba(255, 255, 255, 0.07)",
                          borderRadius: "8px",
                          padding: "16px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "10px",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                          <div>
                            <span style={{ fontSize: "11px", fontWeight: 700, color: "#38bdf8", textTransform: "uppercase" }}>
                              {h.court_name} {h.courtroom ? `· ${h.courtroom}` : ""}
                            </span>
                            <h3 style={{ fontSize: "14px", fontWeight: 700, color: "#fff", margin: "2px 0 0 0" }}>
                              {h.purpose || "Court Proceedings"}
                            </h3>
                            <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                              Matter: <strong>{h.case_title}</strong>
                            </div>
                          </div>
                          <span style={{ fontSize: "12px", fontWeight: 700, color: "#fff", background: "rgba(56, 189, 248, 0.15)", padding: "2px 8px", borderRadius: "4px" }}>
                            {h.time_display}
                          </span>
                        </div>

                        {/* Readiness indicators */}
                        <div style={{ borderTop: "1px solid rgba(255, 255, 255, 0.06)", paddingTop: "10px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "#cbd5e1", marginBottom: "4px" }}>
                            <span>Prep Tasks ({h.preparation_tasks_completed}/{h.preparation_tasks_total})</span>
                            <span style={{ fontWeight: 700 }}>{taskPct}% Ready</span>
                          </div>
                          <div style={{ width: "100%", height: "4px", background: "rgba(255,255,255,0.1)", borderRadius: "2px", overflow: "hidden", marginBottom: "8px" }}>
                            <div style={{ width: `${taskPct}%`, height: "100%", background: taskPct === 100 ? "#10b981" : "#38bdf8", borderRadius: "2px" }}></div>
                          </div>

                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px" }}>
                            <span style={{ color: "var(--text-muted)" }}>
                              📁 {h.exhibits_count} Exhibit(s)
                            </span>
                            <span
                              style={{
                                padding: "2px 6px",
                                borderRadius: "4px",
                                fontSize: "10px",
                                fontWeight: 700,
                                background: h.bundle_status === "FINALIZED" ? "rgba(16, 185, 129, 0.15)" : h.bundle_status === "DRAFT" ? "rgba(245, 158, 11, 0.15)" : "rgba(255, 255, 255, 0.08)",
                                color: h.bundle_status === "FINALIZED" ? "#10b981" : h.bundle_status === "DRAFT" ? "#fbbf24" : "var(--text-muted)",
                              }}
                            >
                              {h.bundle_status ? `Bundle: ${h.bundle_status}` : "No Bundle Draft"}
                            </span>
                          </div>
                        </div>

                        <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                          <Link
                            href={h.action_href}
                            className="btn btn-secondary"
                            style={{ flex: 1, textAlign: "center", padding: "6px", fontSize: "11px" }}
                          >
                            📋 Hearing Tasks
                          </Link>
                          <Link
                            href={`/cases/${h.case_id}/bundles`}
                            className="btn btn-primary"
                            style={{ flex: 1, textAlign: "center", padding: "6px", fontSize: "11px" }}
                          >
                            📦 Open Bundle
                          </Link>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Upcoming Statutory Limitations & Deadlines Radar */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "20px 22px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <div>
                  <h2 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                    ⏱ Statutory Limitation & Filing Radar
                  </h2>
                  <p style={{ fontSize: "12px", color: "var(--text-muted)", margin: "2px 0 0 0" }}>
                    Authoritative cutoffs tracked across procedural rules, court directions, and statutory limitation acts.
                  </p>
                </div>
                <Link href="/calendar" style={{ fontSize: "12px", color: "var(--accent-secondary)", fontWeight: 600 }}>
                  Limitation Calendar →
                </Link>
              </div>

              {upcomingDeadlines.length === 0 ? (
                <div style={{ padding: "16px", textAlign: "center", color: "var(--text-muted)", fontSize: "12px", background: "rgba(255,255,255,0.02)", borderRadius: "6px" }}>
                  No statutory deadlines or compliance cutoffs within this window.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {upcomingDeadlines.map((dl) => (
                    <div
                      key={dl.deadline_id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "10px 14px",
                        borderRadius: "6px",
                        background: dl.is_urgent ? "rgba(245, 158, 11, 0.08)" : "rgba(255, 255, 255, 0.02)",
                        border: dl.is_urgent ? "1px solid rgba(245, 158, 11, 0.25)" : "1px solid rgba(255, 255, 255, 0.05)",
                        gap: "12px",
                      }}
                    >
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontSize: "13px", fontWeight: 600, color: "#fff" }}>
                            {dl.title}
                          </span>
                          <span style={{ fontSize: "10px", padding: "2px 6px", borderRadius: "4px", background: "rgba(255,255,255,0.08)", color: "var(--text-muted)" }}>
                            {dl.source}
                          </span>
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                          Matter: <strong>{dl.case_title}</strong> · Cutoff: <strong>{dl.time_display}</strong>
                        </div>
                      </div>

                      <Link
                        href={dl.action_href}
                        className="btn btn-secondary"
                        style={{ padding: "4px 10px", fontSize: "11px", whiteSpace: "nowrap" }}
                      >
                        Review Filing →
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* High Priority Tasks */}
            {highPriorityTasks.length > 0 && (
              <div
                style={{
                  background: "var(--surface-card)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "var(--radius-md)",
                  padding: "18px 20px",
                }}
              >
                <h2 style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-primary)", margin: "0 0 12px 0" }}>
                  🔴 High Priority Action Items ({highPriorityTasks.length})
                </h2>
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {highPriorityTasks.map((t) => (
                    <div
                      key={t.id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "10px 12px",
                        borderRadius: "6px",
                        background: "rgba(255, 255, 255, 0.02)",
                        border: "1px solid rgba(255, 255, 255, 0.05)",
                      }}
                    >
                      <div>
                        <span style={{ fontSize: "13px", fontWeight: 600, color: "#fff" }}>
                          {t.title}
                        </span>
                        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                          Matter: <strong>{t.case_title}</strong> · Due: <strong>{t.time_display}</strong>
                        </div>
                      </div>
                      <Link
                        href={t.action_href}
                        className="btn btn-secondary"
                        style={{ padding: "4px 8px", fontSize: "11px" }}
                      >
                        Action →
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* RIGHT COLUMN: Chamber Status & Scheduled Video Consultations */}
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {/* Quick Hub Navigation Card */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "18px",
              }}
            >
              <h3 style={{ fontSize: "14px", fontWeight: 700, color: "#fff", margin: "0 0 12px 0" }}>
                Chamber Command
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <Link
                  href="/calendar"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "10px 12px",
                    borderRadius: "6px",
                    background: "rgba(255,255,255,0.03)",
                    color: "#fff",
                    fontSize: "12px",
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  <span>📅</span> Unified Hearing & Deadline Calendar
                </Link>
                <Link
                  href="/court-tracking"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "10px 12px",
                    borderRadius: "6px",
                    background: "rgba(255,255,255,0.03)",
                    color: "#fff",
                    fontSize: "12px",
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  <span>🏛</span> eCourts Cause List Tracker
                </Link>
                <Link
                  href="/cases/new"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "10px 12px",
                    borderRadius: "6px",
                    background: "rgba(99, 102, 241, 0.15)",
                    color: "var(--accent-secondary)",
                    fontSize: "12px",
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  <span>+</span> Create New Case Workspace
                </Link>
                <Link
                  href="/notifications"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "10px 12px",
                    borderRadius: "6px",
                    background: "rgba(255,255,255,0.03)",
                    color: "#fff",
                    fontSize: "12px",
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  <span>🔔</span> Chamber Notification Center ({metrics.unread_notifications_count})
                </Link>
              </div>
            </div>

            {/* Scheduled Consultations Sidebar */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "18px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <h3 style={{ fontSize: "14px", fontWeight: 700, color: "#fff", margin: 0 }}>
                  Client Consultations ({consultations.length})
                </h3>
                <Link href="/consultations" style={{ fontSize: "11px", color: "var(--accent-secondary)", fontWeight: 600 }}>
                  View All →
                </Link>
              </div>

              {consultations.length === 0 ? (
                <EmptyState
                  icon="🎥"
                  title="No Scheduled Calls"
                  description="When clients book consultation slots, appointments will appear here."
                />
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {consultations.slice(0, 5).map((cs) => {
                    const isRoomReady = cs.status === "SCHEDULED" || cs.status === "IN_PROGRESS";
                    return (
                      <div
                        key={cs.id}
                        style={{
                          background: "rgba(255,255,255,0.02)",
                          border: "1px solid rgba(255,255,255,0.06)",
                          borderRadius: "6px",
                          padding: "12px",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "4px" }}>
                          <span style={{ fontSize: "12px", fontWeight: 600, color: "#fff" }}>
                            {cs.client_name || "Client"}
                          </span>
                          <span style={{ fontSize: "11px", fontWeight: 700, color: "#10b981" }}>
                            ₹{cs.fee_amount}
                          </span>
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "8px" }}>
                          {cs.scheduled_at
                            ? new Date(cs.scheduled_at).toLocaleDateString("en-IN", {
                                day: "numeric",
                                month: "short",
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : "Instant Call"} · {cs.duration_minutes}m
                        </div>
                        <div style={{ display: "flex", gap: "6px" }}>
                          {isRoomReady ? (
                            <Link
                              href={`/consultations/${cs.id}/room`}
                              className="btn btn-primary"
                              style={{ flex: 1, textAlign: "center", padding: "4px 8px", fontSize: "11px" }}
                            >
                              Enter Room 🎥
                            </Link>
                          ) : (
                            <button
                              onClick={() => setActionModal({ type: "SCHEDULE", consultation: cs })}
                              className="btn btn-secondary"
                              style={{ flex: 1, padding: "4px 8px", fontSize: "11px" }}
                            >
                              Manage Slot
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 4. ASSIGNED MATTERS OPERATIONAL DIRECTORY */}
        <section
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "22px 24px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px", flexWrap: "wrap", gap: "12px" }}>
            <div>
              <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", margin: 0 }}>
                ⚖ Assigned Matters Directory ({assignedMatters.length})
              </h2>
              <p style={{ fontSize: "12px", color: "var(--text-muted)", margin: "2px 0 0 0" }}>
                Operational health summary across all client workspaces where you are designated counsel.
              </p>
            </div>

            <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
              {/* Search input */}
              <input
                type="text"
                placeholder="Search matter, court..."
                value={mattersSearch}
                onChange={(e) => setMattersSearch(e.target.value)}
                style={{
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "6px",
                  padding: "6px 12px",
                  fontSize: "12px",
                  color: "#fff",
                  outline: "none",
                  width: "180px",
                }}
              />

              {/* Filter tabs */}
              <div style={{ display: "flex", gap: "4px", background: "rgba(255,255,255,0.03)", padding: "2px", borderRadius: "6px" }}>
                <button
                  type="button"
                  onClick={() => setMattersFilter("ALL")}
                  style={{
                    padding: "4px 10px",
                    fontSize: "11px",
                    fontWeight: 600,
                    borderRadius: "4px",
                    border: "none",
                    cursor: "pointer",
                    background: mattersFilter === "ALL" ? "var(--accent-secondary)" : "transparent",
                    color: mattersFilter === "ALL" ? "#fff" : "var(--text-muted)",
                  }}
                >
                  All ({assignedMatters.length})
                </button>
                <button
                  type="button"
                  onClick={() => setMattersFilter("ATTENTION")}
                  style={{
                    padding: "4px 10px",
                    fontSize: "11px",
                    fontWeight: 600,
                    borderRadius: "4px",
                    border: "none",
                    cursor: "pointer",
                    background: mattersFilter === "ATTENTION" ? "#ef4444" : "transparent",
                    color: mattersFilter === "ATTENTION" ? "#fff" : "var(--text-muted)",
                  }}
                >
                  Needs Attention
                </button>
                <button
                  type="button"
                  onClick={() => setMattersFilter("ACTIVE")}
                  style={{
                    padding: "4px 10px",
                    fontSize: "11px",
                    fontWeight: 600,
                    borderRadius: "4px",
                    border: "none",
                    cursor: "pointer",
                    background: mattersFilter === "ACTIVE" ? "rgba(255,255,255,0.15)" : "transparent",
                    color: mattersFilter === "ACTIVE" ? "#fff" : "var(--text-muted)",
                  }}
                >
                  Active Only
                </button>
              </div>
            </div>
          </div>

          {filteredMatters.length === 0 ? (
            <div style={{ padding: "32px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
              No matters matching current directory filters.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {filteredMatters.map((m) => (
                <div
                  key={m.case_id}
                  style={{
                    background: "rgba(255, 255, 255, 0.02)",
                    border: m.overdue_tasks_count > 0 ? "1px solid rgba(239, 68, 68, 0.3)" : "1px solid rgba(255, 255, 255, 0.06)",
                    borderRadius: "8px",
                    padding: "16px 18px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "14px",
                    transition: "border 0.15s ease",
                  }}
                >
                  <div style={{ flex: 1, minWidth: "260px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", marginBottom: "4px" }}>
                      <Link
                        href={m.action_href}
                        style={{ fontSize: "15px", fontWeight: 700, color: "#fff", textDecoration: "none" }}
                      >
                        {m.title}
                      </Link>
                      <StatusBadge status={m.status} />
                      {m.bundle_status && (
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 700,
                            padding: "2px 6px",
                            borderRadius: "4px",
                            background: m.bundle_status === "FINALIZED" ? "rgba(16, 185, 129, 0.15)" : "rgba(245, 158, 11, 0.15)",
                            color: m.bundle_status === "FINALIZED" ? "#10b981" : "#fbbf24",
                          }}
                        >
                          Bundle: {m.bundle_status}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                      {m.court_name ? `Court: ${m.court_name}` : "Chamber Advisory Matter"}
                      {m.next_hearing_at && (
                        <span style={{ marginLeft: "10px", color: "#38bdf8", fontWeight: 600 }}>
                          Next: {new Date(m.next_hearing_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                          {m.next_hearing_purpose ? ` (${m.next_hearing_purpose})` : ""}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Telemetry pill tags */}
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                    <div
                      style={{
                        padding: "4px 10px",
                        borderRadius: "6px",
                        background: m.overdue_tasks_count > 0 ? "rgba(239, 68, 68, 0.15)" : "rgba(255,255,255,0.04)",
                        color: m.overdue_tasks_count > 0 ? "#f87171" : "var(--text-muted)",
                        fontSize: "11px",
                        fontWeight: 600,
                      }}
                    >
                      {m.overdue_tasks_count > 0 ? `⚠️ ${m.overdue_tasks_count} Overdue` : "Tasks Clean"}
                    </div>

                    <div
                      style={{
                        padding: "4px 10px",
                        borderRadius: "6px",
                        background: "rgba(255,255,255,0.04)",
                        color: "var(--text-muted)",
                        fontSize: "11px",
                        fontWeight: 600,
                      }}
                    >
                      ⏱ {m.active_deadlines_count} Deadlines
                    </div>

                    <div
                      style={{
                        padding: "4px 10px",
                        borderRadius: "6px",
                        background: m.unreviewed_evidence_count > 0 ? "rgba(56, 189, 248, 0.12)" : "rgba(255,255,255,0.04)",
                        color: m.unreviewed_evidence_count > 0 ? "#38bdf8" : "var(--text-muted)",
                        fontSize: "11px",
                        fontWeight: 600,
                      }}
                    >
                      📁 {m.unreviewed_evidence_count} Unreviewed
                    </div>

                    <Link
                      href={m.action_href}
                      className="btn btn-secondary"
                      style={{ padding: "6px 14px", fontSize: "12px" }}
                    >
                      Open Case →
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Action Modal for Consultations */}
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
    </div>
  );
}
