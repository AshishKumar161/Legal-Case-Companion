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
