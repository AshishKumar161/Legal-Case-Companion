"use client";

import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { apiClient } from "@/api/client";
import {
  VerificationItem,
  BackgroundJobItem,
  MetricsSnapshotItem,
  ProductHealthItem,
  PilotFeedbackItem,
} from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";

type AdminTab = "verifications" | "jobs" | "legal_data" | "metrics" | "pilot_health";

export default function AdminDashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<AdminTab>("verifications");
  const [verifications, setVerifications] = useState<VerificationItem[]>([]);
  const [jobs, setJobs] = useState<BackgroundJobItem[]>([]);
  const [metrics, setMetrics] = useState<MetricsSnapshotItem | null>(null);
  const [productHealth, setProductHealth] = useState<ProductHealthItem | null>(null);
  const [feedbackList, setFeedbackList] = useState<PilotFeedbackItem[]>([]);
  const [fetching, setFetching] = useState(true);

  // Legal Data state
  const [syncingFixtures, setSyncingFixtures] = useState(false);
  const [syncResult, setSyncResult] = useState<string>("");
  const [rawSourcePayload, setRawSourcePayload] = useState("");
  const [importingRaw, setImportingRaw] = useState(false);

  const fetchAdminData = useCallback(async () => {
    try {
      setFetching(true);
      const [verRes, jobsRes, metricsRes, healthRes, fbRes] = await Promise.all([
        apiClient.get("/api/v1/admin/verifications").catch(() => []),
        apiClient.get("/api/v1/admin/jobs?limit=20").catch(() => []),
        apiClient.get("/api/v1/admin/metrics").catch(() => null),
        apiClient.get("/api/v1/analytics/product-health").catch(() => null),
        apiClient.get("/api/v1/feedback?limit=30").catch(() => []),
      ]);
      setVerifications(verRes?.items || (Array.isArray(verRes) ? verRes : []));
      setJobs(jobsRes?.items || (Array.isArray(jobsRes) ? jobsRes : []));
      setMetrics(metricsRes);
      setProductHealth(healthRes);
      setFeedbackList(Array.isArray(fbRes) ? fbRes : fbRes?.items || []);
    } catch (err) {
      console.error(err);
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    } else if (user && user.role !== "ADMIN") {
      router.push("/dashboard");
    } else if (user) {
      void fetchAdminData();
    }
  }, [user, loading, router, fetchAdminData]);

  // Handle Verification Review
  const handleReview = async (id: string, approve: boolean) => {
    try {
      await apiClient.post(`/api/v1/admin/verifications/${id}/${approve ? "approve" : "reject"}`, {});
      setVerifications((prev) => prev.filter((v) => v.id !== id));
      alert(`Lawyer verification ${approve ? "approved" : "rejected"} successfully.`);
    } catch {
      alert("Failed to review verification");
    }
  };

  // Handle Fixtures Sync
  const handleSyncFixtures = async () => {
    setSyncingFixtures(true);
    setSyncResult("");
    try {
      const res = await apiClient.post("/api/v1/admin/legal-sources/sync-fixtures", {});
      setSyncResult(`Synced ${res?.synced_count ?? "all"} curated Indian statutory & judicial authorities successfully.`);
      void fetchAdminData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Sync failed";
      setSyncResult(`Sync failed: ${msg}`);
    } finally {
      setSyncingFixtures(false);
    }
  };

  // Handle Import Raw Legal Source
  const handleImportRaw = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawSourcePayload.trim()) return;
    setImportingRaw(true);
    try {
      const parsed = JSON.parse(rawSourcePayload);
      await apiClient.post("/api/v1/admin/legal-sources/import-raw", parsed);
      alert("Raw legal source imported and dispatched for ingestion successfully.");
      setRawSourcePayload("");
      void fetchAdminData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Invalid JSON payload";
      alert(`Failed to import raw legal source: ${msg}`);
    } finally {
      setImportingRaw(false);
    }
  };

  if (loading || fetching || !user || user.role !== "ADMIN") {
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
        <div style={{ marginBottom: "28px" }}>
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
            <span>●</span> Platform Operations Control Center
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
            <h1 style={{ fontSize: "28px", fontWeight: 700, color: "var(--text-primary)" }}>
              Platform Administration Console
            </h1>
            <StatusBadge status="ADMIN" label="Superuser Privileges" />
          </div>
          <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginTop: "6px", maxWidth: "720px" }}>
            Audit advocate credential filings, supervise distributed task queues, synchronize authoritative Indian statutory databases, and inspect live operational telemetry.
          </p>
        </div>

        {/* Tab Bar */}
        <div
          style={{
            display: "flex",
            gap: "6px",
            borderBottom: "1px solid var(--border-subtle)",
            marginBottom: "24px",
            overflowX: "auto",
          }}
        >
          <button
            onClick={() => setActiveTab("verifications")}
            style={{
              padding: "10px 18px",
              fontSize: "13px",
              fontWeight: 600,
              color: activeTab === "verifications" ? "#fff" : "var(--text-secondary)",
              borderBottom: activeTab === "verifications" ? "2px solid var(--accent-primary)" : "2px solid transparent",
              background: activeTab === "verifications" ? "rgba(79, 91, 247, 0.08)" : "transparent",
              borderRadius: "6px 6px 0 0",
            }}
          >
            📜 Bar Verifications ({verifications.length})
          </button>
          <button
            onClick={() => setActiveTab("jobs")}
            style={{
              padding: "10px 18px",
              fontSize: "13px",
              fontWeight: 600,
              color: activeTab === "jobs" ? "#fff" : "var(--text-secondary)",
              borderBottom: activeTab === "jobs" ? "2px solid var(--accent-primary)" : "2px solid transparent",
              background: activeTab === "jobs" ? "rgba(79, 91, 247, 0.08)" : "transparent",
              borderRadius: "6px 6px 0 0",
            }}
          >
            ⚙ Background Execution Jobs ({jobs.length})
          </button>
          <button
            onClick={() => setActiveTab("legal_data")}
            style={{
              padding: "10px 18px",
              fontSize: "13px",
              fontWeight: 600,
              color: activeTab === "legal_data" ? "#fff" : "var(--text-secondary)",
              borderBottom: activeTab === "legal_data" ? "2px solid var(--accent-primary)" : "2px solid transparent",
              background: activeTab === "legal_data" ? "rgba(79, 91, 247, 0.08)" : "transparent",
              borderRadius: "6px 6px 0 0",
            }}
          >
            ⚖ Indian Legal Data Pipeline
          </button>
          <button
            onClick={() => setActiveTab("metrics")}
            style={{
              padding: "10px 18px",
              fontSize: "13px",
              fontWeight: 600,
              color: activeTab === "metrics" ? "#fff" : "var(--text-secondary)",
              borderBottom: activeTab === "metrics" ? "2px solid var(--accent-primary)" : "2px solid transparent",
              background: activeTab === "metrics" ? "rgba(79, 91, 247, 0.08)" : "transparent",
              borderRadius: "6px 6px 0 0",
            }}
          >
            📊 System Observability
          </button>
          <button
            onClick={() => setActiveTab("pilot_health")}
            style={{
              padding: "10px 18px",
              fontSize: "13px",
              fontWeight: 600,
              color: activeTab === "pilot_health" ? "#f59e0b" : "var(--text-secondary)",
              borderBottom: activeTab === "pilot_health" ? "2px solid #f59e0b" : "2px solid transparent",
              background: activeTab === "pilot_health" ? "rgba(245, 158, 11, 0.1)" : "transparent",
              borderRadius: "6px 6px 0 0",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span>🎯</span> Pilot Health & Product Intelligence
            {productHealth?.unresolved_feedback_p0_p1 ? (
              <span
                style={{
                  background: "#ef4444",
                  color: "#fff",
                  padding: "1px 6px",
                  borderRadius: "10px",
                  fontSize: "10px",
                  fontWeight: 700,
                }}
              >
                {productHealth.unresolved_feedback_p0_p1} P0/P1
              </span>
            ) : null}
          </button>
        </div>

        {/* TAB 1: LAWYER VERIFICATIONS */}
        {activeTab === "verifications" && (
          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "24px",
            }}
          >
            <h2 style={{ fontSize: "17px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "16px" }}>
              Pending Bar Council Verifications
            </h2>

            {verifications.length === 0 ? (
              <EmptyState
                icon="✓"
                title="All Bar Verifications Reviewed"
                description="No advocate credential filings are awaiting administrative review at this time."
              />
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", textAlign: "left" }}>
                      <th style={{ padding: "10px 12px" }}>Enrollment Number</th>
                      <th style={{ padding: "10px 12px" }}>State Bar Council</th>
                      <th style={{ padding: "10px 12px" }}>Filing Status</th>
                      <th style={{ padding: "10px 12px" }}>Submitted Date</th>
                      <th style={{ padding: "10px 12px", textAlign: "right" }}>Review Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {verifications.map((v) => (
                      <tr key={v.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "14px 12px", fontWeight: 600, color: "#fff" }}>{v.enrollment_number}</td>
                        <td style={{ padding: "14px 12px", color: "var(--text-primary)" }}>{v.state_bar_council}</td>
                        <td style={{ padding: "14px 12px" }}>
                          <StatusBadge status={v.status} />
                        </td>
                        <td style={{ padding: "14px 12px", color: "var(--text-muted)" }}>
                          {new Date(v.created_at).toLocaleDateString("en-IN")}
                        </td>
                        <td style={{ padding: "14px 12px", textAlign: "right" }}>
                          <div style={{ display: "inline-flex", gap: "8px" }}>
                            <button
                              onClick={() => handleReview(v.id, true)}
                              style={{
                                padding: "6px 12px",
                                borderRadius: "6px",
                                background: "#10b981",
                                color: "#fff",
                                fontSize: "12px",
                                fontWeight: 600,
                              }}
                            >
                              Approve Bar
                            </button>
                            <button
                              onClick={() => handleReview(v.id, false)}
                              style={{
                                padding: "6px 12px",
                                borderRadius: "6px",
                                background: "rgba(239, 68, 68, 0.2)",
                                color: "#ef4444",
                                border: "1px solid rgba(239, 68, 68, 0.4)",
                                fontSize: "12px",
                                fontWeight: 600,
                              }}
                            >
                              Reject
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: BACKGROUND JOBS */}
        {activeTab === "jobs" && (
          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "24px",
            }}
          >
            <h2 style={{ fontSize: "17px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "16px" }}>
              Asynchronous Background Execution Workers
            </h2>

            {jobs.length === 0 ? (
              <EmptyState
                icon="⚙"
                title="Job Pipeline Idle"
                description="No active or pending document extraction, vector indexing, or notification jobs."
              />
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-secondary)", textAlign: "left" }}>
                      <th style={{ padding: "10px 12px" }}>Job ID</th>
                      <th style={{ padding: "10px 12px" }}>Job Type</th>
                      <th style={{ padding: "10px 12px" }}>Status</th>
                      <th style={{ padding: "10px 12px" }}>Attempts</th>
                      <th style={{ padding: "10px 12px" }}>Scheduled</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((j) => (
                      <tr key={j.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "14px 12px", fontFamily: "monospace", fontSize: "12px", color: "var(--text-secondary)" }}>
                          #{j.id.slice(0, 8).toUpperCase()}
                        </td>
                        <td style={{ padding: "14px 12px", fontWeight: 600, color: "#fff" }}>{j.job_type}</td>
                        <td style={{ padding: "14px 12px" }}>
                          <StatusBadge status={j.status} />
                        </td>
                        <td style={{ padding: "14px 12px", color: "var(--text-secondary)" }}>
                          {j.attempt_count} / {j.max_attempts}
                        </td>
                        <td style={{ padding: "14px 12px", color: "var(--text-muted)" }}>
                          {new Date(j.scheduled_at).toLocaleTimeString("en-IN")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: LEGAL DATA PIPELINE */}
        {activeTab === "legal_data" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "24px",
              }}
            >
              <h2 style={{ fontSize: "17px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
                Curated Statutory & Precedent Fixtures
              </h2>
              <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.5, marginBottom: "16px" }}>
                Synchronize authoritative Indian legal enactments (Commercial Courts Act 2015, Limitation Act 1963, Arbitration & Conciliation Act 1996, Negotiable Instruments Act 1881) into vector embeddings.
              </p>
              <button
                onClick={handleSyncFixtures}
                disabled={syncingFixtures}
                className="btn btn-primary"
              >
                {syncingFixtures ? "Synchronizing Authorities..." : "Sync Curated Indian Fixtures →"}
              </button>

              {syncResult && (
                <div style={{ marginTop: "14px", padding: "12px", borderRadius: "6px", background: "rgba(16, 185, 129, 0.15)", color: "#10b981", fontSize: "13px" }}>
                  {syncResult}
                </div>
              )}
            </div>

            {/* Raw Ingestion Form */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "24px",
              }}
            >
              <h2 style={{ fontSize: "17px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
                Import Raw Precedent JSON
              </h2>
              <form onSubmit={handleImportRaw}>
                <textarea
                  value={rawSourcePayload}
                  onChange={(e) => setRawSourcePayload(e.target.value)}
                  placeholder='{"source_system": "INDIAN_KANOON", "external_identifier": "IN-SC-2024-TEST", "source_type": "JUDICIAL_PRECEDENT", "raw_content": {...}}'
                  rows={5}
                  className="input-field"
                  style={{ width: "100%", fontFamily: "monospace", fontSize: "12px", marginBottom: "14px" }}
                />
                <button
                  type="submit"
                  disabled={importingRaw || !rawSourcePayload.trim()}
                  className="btn btn-secondary"
                >
                  {importingRaw ? "Ingesting..." : "Import Raw Legal Source"}
                </button>
              </form>
            </div>
          </div>
        )}

        {/* TAB 4: METRICS */}
        {activeTab === "metrics" && metrics && (
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px" }}>
              <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "20px" }}>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase" }}>
                  Engine Uptime
                </div>
                <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--accent-secondary)", marginTop: "6px" }}>
                  {(metrics.uptime_seconds / 60).toFixed(1)} mins
                </div>
              </div>

              <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "20px" }}>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase" }}>
                  Total Handled Requests
                </div>
                <div style={{ fontSize: "28px", fontWeight: 700, color: "#10b981", marginTop: "6px" }}>
                  {metrics.total_http_requests}
                </div>
              </div>

              <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "20px" }}>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase" }}>
                  Average Latency
                </div>
                <div style={{ fontSize: "28px", fontWeight: 700, color: "#8b5cf6", marginTop: "6px" }}>
                  {(metrics.latency_ms?.avg || 0).toFixed(1)} ms
                </div>
              </div>

              <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "20px" }}>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase" }}>
                  P95 Latency
                </div>
                <div style={{ fontSize: "28px", fontWeight: 700, color: "#f59e0b", marginTop: "6px" }}>
                  {(metrics.latency_ms?.p95 || 0).toFixed(1)} ms
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: PILOT HEALTH & PRODUCT INTELLIGENCE */}
        {activeTab === "pilot_health" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            {/* Top KPI Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
              <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "18px" }}>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase" }}>
                  Active Matters
                </div>
                <div style={{ fontSize: "26px", fontWeight: 700, color: "var(--accent-secondary)", marginTop: "6px" }}>
                  {productHealth?.active_matters || 0}
                </div>
              </div>
              <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "18px" }}>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase" }}>
                  Evidence Ingested
                </div>
                <div style={{ fontSize: "26px", fontWeight: 700, color: "#10b981", marginTop: "6px" }}>
                  {productHealth?.total_documents_uploaded || 0}
                </div>
              </div>
              <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "18px" }}>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase" }}>
                  AI Grounding Score
                </div>
                <div style={{ fontSize: "26px", fontWeight: 700, color: "#60a5fa", marginTop: "6px" }}>
                  {((productHealth?.ai_health?.avg_grounding_score || 0) * 100).toFixed(0)}%
                </div>
              </div>
              <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "18px" }}>
                <div style={{ fontSize: "11px", color: "var(--text-secondary)", fontWeight: 700, textTransform: "uppercase" }}>
                  Unresolved P0/P1 Issues
                </div>
                <div style={{ fontSize: "26px", fontWeight: 700, color: productHealth?.unresolved_feedback_p0_p1 ? "#ef4444" : "#10b981", marginTop: "6px" }}>
                  {productHealth?.unresolved_feedback_p0_p1 || 0}
                </div>
              </div>
            </div>

            {/* Conversion Funnel */}
            <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "20px" }}>
              <h3 style={{ fontSize: "15px", fontWeight: 700, color: "#fff", marginBottom: "16px" }}>
                Pilot Conversion & Workflow Funnel
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {(productHealth?.funnel || []).map((step, idx) => (
                  <div key={idx} style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <div style={{ width: "160px", fontSize: "13px", color: "var(--text-secondary)", fontWeight: 600 }}>
                      {step.step}
                    </div>
                    <div style={{ flex: 1, height: "16px", background: "rgba(255, 255, 255, 0.05)", borderRadius: "4px", overflow: "hidden" }}>
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.max(step.conversion_rate * 100, 4)}%`,
                          background: idx === 0 ? "#4f5bf7" : idx === 1 ? "#60a5fa" : idx === 2 ? "#10b981" : idx === 3 ? "#f59e0b" : "#8b5cf6",
                          borderRadius: "4px",
                        }}
                      />
                    </div>
                    <div style={{ width: "80px", textAlign: "right", fontSize: "12px", color: "#fff", fontWeight: 700 }}>
                      {step.count} ({Math.round(step.conversion_rate * 100)}%)
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Pilot Feedback & Friction Queue */}
            <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <h3 style={{ fontSize: "15px", fontWeight: 700, color: "#fff", margin: 0 }}>
                  Controlled Pilot Feedback & Friction Queue ({feedbackList.length})
                </h3>
              </div>

              {feedbackList.length === 0 ? (
                <EmptyState
                  title="No pilot friction reported"
                  description="All pilot participants are navigating matters smoothly."
                />
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {feedbackList.map((item) => (
                    <div
                      key={item.id}
                      style={{
                        background: "#151923",
                        border: "1px solid #232838",
                        borderRadius: "6px",
                        padding: "14px 18px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "flex-start",
                        gap: "16px",
                      }}
                    >
                      <div style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span
                            style={{
                              fontSize: "10px",
                              fontWeight: 700,
                              padding: "2px 6px",
                              borderRadius: "4px",
                              background: item.priority === "P0" || item.priority === "P1" ? "rgba(239, 68, 68, 0.2)" : "rgba(245, 158, 11, 0.2)",
                              color: item.priority === "P0" || item.priority === "P1" ? "#ef4444" : "#f59e0b",
                            }}
                          >
                            {item.priority || "P2"}
                          </span>
                          <span style={{ fontSize: "11px", color: "#8d98ff", fontWeight: 600 }}>
                            {item.category}
                          </span>
                          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                            {item.page_url}
                          </span>
                        </div>
                        <p style={{ fontSize: "13px", color: "#e2e8f0", margin: 0, lineHeight: "1.5" }}>
                          {item.description}
                        </p>
                        {item.resolution_notes && (
                          <div style={{ fontSize: "11px", color: "#10b981", marginTop: "4px" }}>
                            Resolution: {item.resolution_notes}
                          </div>
                        )}
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 600,
                            padding: "3px 8px",
                            borderRadius: "4px",
                            background: item.status === "RESOLVED" ? "rgba(16, 185, 129, 0.15)" : "rgba(255, 255, 255, 0.05)",
                            color: item.status === "RESOLVED" ? "#10b981" : "var(--text-secondary)",
                          }}
                        >
                          {item.status}
                        </span>
                        {item.status !== "RESOLVED" && (
                          <button
                            onClick={async () => {
                              try {
                                await apiClient.patch(`/api/v1/feedback/${item.id}`, {
                                  status: "RESOLVED",
                                  resolution_notes: "Resolved in controlled pilot sprint.",
                                });
                                void fetchAdminData();
                              } catch (err) {
                                console.error(err);
                              }
                            }}
                            style={{
                              padding: "4px 10px",
                              borderRadius: "4px",
                              border: "1px solid #10b981",
                              background: "rgba(16, 185, 129, 0.1)",
                              color: "#10b981",
                              fontSize: "11px",
                              cursor: "pointer",
                              fontWeight: 600,
                            }}
                          >
                            Mark Resolved ✓
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
