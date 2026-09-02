"use client";

import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback, useMemo } from "react";
import { apiClient } from "@/api/client";
import Link from "next/link";
import { CaseItem, ConsultationItem } from "@/types";
import styles from "./dashboard.module.css";
import { StatusBadge } from "@/components/StatusBadge";
import { PaymentCheckoutModal } from "@/components/Payment/PaymentCheckoutModal";
import { ConsultationActionModal } from "@/components/Consultation/ConsultationActionModal";

export default function Dashboard() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [cases, setCases] = useState<CaseItem[]>([]);
  const [consultations, setConsultations] = useState<ConsultationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [fetching, setFetching] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [checkoutConsultation, setCheckoutConsultation] = useState<ConsultationItem | null>(null);
  const [actionConsultationModal, setActionConsultationModal] = useState<{
    type: "RESCHEDULE" | "CANCEL";
    consultation: ConsultationItem;
  } | null>(null);

  // Search, Filter & View state
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [sortBy, setSortBy] = useState<"updated" | "title" | "status">("updated");

  // Create Case Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchDashboardData = useCallback(async () => {
    try {
      setFetching(true);
      setFetchError(null);

      const [casesRes, consultRes, unreadRes] = await Promise.all([
        apiClient.get("/api/v1/cases").catch(() => ({ items: [] })),
        apiClient.get("/api/v1/consultations").catch(() => ({ items: [] })),
        apiClient.get("/api/v1/notifications/unread-count").catch(() => ({ unread_count: 0 })),
      ]);

      const caseItems: CaseItem[] = Array.isArray(casesRes)
        ? casesRes
        : casesRes?.items || [];
      const consultItems: ConsultationItem[] = Array.isArray(consultRes)
        ? consultRes
        : consultRes?.items || [];

      setCases(caseItems);
      setConsultations(consultItems);
      setUnreadCount(unreadRes?.unread_count || 0);
    } catch (err: unknown) {
      console.error("Dashboard fetch error:", err);
      setFetchError("Unable to synchronize dashboard matters. Please verify your connection.");
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    } else if (user?.role === "LAWYER") {
      router.push("/lawyer/dashboard");
    } else if (user?.role === "ADMIN") {
      router.push("/admin/dashboard");
    } else if (user) {
      void fetchDashboardData();
    }
  }, [user, loading, router, fetchDashboardData]);

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || creating) return;
    setCreating(true);
    try {
      const res = await apiClient.post("/api/v1/cases", {
        title: newTitle.trim(),
        description: newDesc.trim(),
      });
      setCreateModalOpen(false);
      setNewTitle("");
      setNewDesc("");
      router.push(`/cases/${res.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create case";
      alert(`Matter creation error: ${msg}`);
    } finally {
      setCreating(false);
    }
  };

  // Filtered & Sorted Cases
  const filteredCases = useMemo(() => {
    return cases
      .filter((c) => {
        const matchesStatus =
          statusFilter === "ALL" ? true : c.status === statusFilter;
        const matchesSearch =
          searchQuery === ""
            ? true
            : c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
              (c.description && c.description.toLowerCase().includes(searchQuery.toLowerCase()));
        return matchesStatus && matchesSearch;
      })
      .sort((a, b) => {
        if (sortBy === "title") return a.title.localeCompare(b.title);
        if (sortBy === "status") return a.status.localeCompare(b.status);
        return new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime();
      });
  }, [cases, searchQuery, statusFilter, sortBy]);

  // Active case counts

  if (loading || (!user && fetching)) {
    return (
      <div className={styles.dashboardPage}>
        <div className="container" style={{ textAlign: "center", paddingTop: "100px" }}>
          <div className={styles.eyebrow}>
            <span className={styles.eyebrowDot} /> Synchronizing Secure Workspace
          </div>
          <p style={{ color: "#7b8596", marginTop: "12px" }}>Authenticating credentials and retrieving matter registry...</p>
        </div>
      </div>
    );
  }

  const activeCasesCount = cases.filter((c) => c.status === "OPEN" || c.status === "IN_PROGRESS").length;
  const inReviewCount = cases.filter((c) => c.status === "IN_REVIEW" || c.status === "PENDING_COURT").length;

  return (
    <div className={styles.dashboardPage}>
      <div className="container">
        {/* Dashboard Top Command Header */}
        <div className={styles.dashboardHeader}>
          <div className={styles.headerTitleSection}>
            <div className={styles.eyebrow}>
              <span className={styles.eyebrowDot} /> Case Command Center • Client Portal
            </div>
            <h1 className={styles.pageHeading}>
              Welcome, {user?.full_name || user?.email?.split("@")[0] || "Counsel"}
            </h1>
            <p className={styles.subHeading}>
              Manage active litigation matters, monitor statutory deadlines, inspect evidence-grounded research, and collaborate with verified counsel.
            </p>
          </div>

          <div className={styles.headerActions}>
            <Link href="/lawyers" className={styles.secondaryActionBtn}>
              <span>⚖</span> Browse Counsel
            </Link>
            <button
              onClick={() => setCreateModalOpen(true)}
              className={styles.primaryActionBtn}
            >
              <span>+</span> New Case Workspace
            </button>
          </div>
        </div>

        {/* Operational Metrics Row */}
        <div className={styles.metricsGrid}>
          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>
              <span>Active Matters</span>
              <span style={{ color: "#6d7cff" }}>●</span>
            </div>
            <div className={styles.metricValue}>{activeCasesCount}</div>
            <div className={styles.metricSubtitle}>
              <span className={styles.metricSubtitleDot} style={{ background: "#10b981" }} />
              {cases.length} total matters on file
            </div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>
              <span>Under Review</span>
              <span style={{ color: "#3b82f6" }}>◈</span>
            </div>
            <div className={styles.metricValue}>{inReviewCount}</div>
            <div className={styles.metricSubtitle}>
              <span className={styles.metricSubtitleDot} style={{ background: "#3b82f6" }} />
              Pending legal review or court list
            </div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>
              <span>Consultations</span>
              <span style={{ color: "#10b981" }}>◷</span>
            </div>
            <div className={styles.metricValue}>{consultations.length}</div>
            <div className={styles.metricSubtitle}>
              <span className={styles.metricSubtitleDot} style={{ background: "#10b981" }} />
              Active counsel sessions scheduled
            </div>
          </div>

          <div className={styles.metricCard}>
            <div className={styles.metricLabel}>
              <span>Unread Alerts</span>
              <span style={{ color: "#8b5cf6" }}>✦</span>
            </div>
            <div className={styles.metricValue}>{unreadCount}</div>
            <div className={styles.metricSubtitle}>
              <span className={styles.metricSubtitleDot} style={{ background: unreadCount > 0 ? "#ef4444" : "#6b7280" }} />
              {unreadCount > 0 ? "Requires review" : "All updates cleared"}
            </div>
          </div>
        </div>

        {fetchError && (
          <div style={{
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            borderRadius: "8px",
            padding: "12px 16px",
            marginBottom: "24px",
            color: "#fca5a5",
            fontSize: "13px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <span>{fetchError}</span>
            <button
              onClick={() => void fetchDashboardData()}
              style={{ background: "none", border: "none", color: "#fff", cursor: "pointer", textDecoration: "underline", fontSize: "12px" }}
            >
              Retry
            </button>
          </div>
        )}

        {/* Main Split Layout: Case Repository + Operational Widgets */}
        <div className={styles.mainLayout}>
          {/* Main Case List Section */}
          <section className={styles.mattersSection}>
            <div className={styles.sectionTopBar}>
              <h2 className={styles.sectionTitle}>
                Legal Matters <span className={styles.counterBadge}>{filteredCases.length}</span>
              </h2>

              <div className={styles.filterControls}>
                <div className={styles.searchBox}>
                  <span className={styles.searchIcon}>🔍</span>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search by title or summary..."
                    className={styles.searchInput}
                  />
                </div>

                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className={styles.filterSelect}
                  aria-label="Filter matters by status"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="OPEN">Open</option>
                  <option value="IN_PROGRESS">In Progress</option>
                  <option value="IN_REVIEW">In Review</option>
                  <option value="PENDING_COURT">Pending Court</option>
                  <option value="CLOSED">Closed</option>
                </select>

                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as "updated" | "title" | "status")}
                  className={styles.filterSelect}
                  aria-label="Sort matters"
                >
                  <option value="updated">Latest Activity</option>
                  <option value="title">Title (A-Z)</option>
                  <option value="status">Status</option>
                </select>
              </div>
            </div>

            {fetching ? (
              <div style={{ padding: "40px 0", textAlign: "center", color: "#7a8494", fontSize: "14px" }}>
                Loading matters...
              </div>
            ) : filteredCases.length === 0 ? (
              <div className={styles.emptyStateCard}>
                <div className={styles.emptyStateIcon}>⚖</div>
                <h3 className={styles.emptyStateTitle}>
                  {searchQuery || statusFilter !== "ALL" ? "No Matching Matters" : "No Legal Matters on File"}
                </h3>
                <p className={styles.emptyStateText}>
                  {searchQuery || statusFilter !== "ALL"
                    ? "Try adjusting your search criteria or clearing active filters to view all cases."
                    : "Create a matter workspace to organize contracts, evidence documents, statutory limitation timelines, and AI-grounded research."}
                </p>
                <button
                  onClick={() => {
                    if (searchQuery || statusFilter !== "ALL") {
                      setSearchQuery("");
                      setStatusFilter("ALL");
                    } else {
                      setCreateModalOpen(true);
                    }
                  }}
                  className={styles.primaryActionBtn}
                >
                  {searchQuery || statusFilter !== "ALL" ? "Clear Filters" : "+ Create First Matter"}
                </button>
              </div>
            ) : (
              <div className={styles.caseList}>
                {filteredCases.map((item) => (
                  <Link
                    key={item.id}
                    href={`/cases/${item.id}`}
                    className={styles.caseCard}
                  >
                    <div className={styles.caseCardHeader}>
                      <div className={styles.caseTitleGroup}>
                        <h3 className={styles.caseCardTitle}>{item.title}</h3>
                        <span className={styles.caseCardRef}>
                          ID #{item.id.slice(0, 8).toUpperCase()}
                        </span>
                      </div>
                      <div>
                        <StatusBadge status={item.status} />
                      </div>
                    </div>

                    <p className={styles.caseCardDesc}>
                      {item.description || "No matter summary or background provided."}
                    </p>

                    <div className={styles.caseCardFooter}>
                      <div className={styles.caseMetaGroup}>
                        <div className={styles.caseMetaItem}>
                          <span>📅</span>
                          <span>
                            Created {new Date(item.created_at).toLocaleDateString("en-IN", {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                            })}
                          </span>
                        </div>
                        {item.updated_at && item.updated_at !== item.created_at && (
                          <div className={styles.caseMetaItem}>
                            <span>↻</span>
                            <span>
                              Updated {new Date(item.updated_at).toLocaleDateString("en-IN", {
                                day: "numeric",
                                month: "short",
                              })}
                            </span>
                          </div>
                        )}
                      </div>

                      <div className={styles.openLink}>
                        Open Case Workspace <b>→</b>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>

          {/* Right Operational Sidebar */}
          <aside className={styles.sidebarSection}>
            {/* Consultations Card */}
            <div className={styles.widgetCard}>
              <div className={styles.widgetHeader}>
                <div className={styles.widgetTitle}>
                  <span>📅</span> Consultations
                </div>
                <Link href="/lawyers" className={styles.widgetAction}>
                  Find Counsel →
                </Link>
              </div>

              {consultations.length === 0 ? (
                <div style={{ textAlign: "center", padding: "16px 0", color: "#7a8494", fontSize: "12px" }}>
                  <p>No consultations scheduled.</p>
                  <Link
                    href="/lawyers"
                    style={{ display: "inline-block", marginTop: "8px", color: "#8d98ff", fontWeight: 600 }}
                  >
                    Explore Lawyer Directory
                  </Link>
                </div>
              ) : (
                <div className={styles.consultList}>
                  {consultations.slice(0, 4).map((con) => (
                    <div key={con.id} className={styles.consultCard}>
                      <div className={styles.consultHeader}>
                        <StatusBadge status={con.status} />
                        <span className={styles.consultTime}>
                          {new Date(con.scheduled_start).toLocaleDateString("en-IN", {
                            day: "numeric",
                            month: "short",
                          })}
                        </span>
                      </div>
                      <div style={{ fontSize: "12px", color: "#f7f8fa", fontWeight: 500 }}>
                        {new Date(con.scheduled_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        {" - "}
                        {new Date(con.scheduled_end).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </div>

                      {/* Financial Status & Payment Trigger */}
                      {(con.status === "ACCEPTED" || con.status === "REQUESTED") && (con.fee_amount ?? 2500) > 0 && (
                        <button
                          onClick={() => setCheckoutConsultation(con)}
                          style={{
                            marginTop: "8px",
                            padding: "6px 12px",
                            borderRadius: "6px",
                            background: "linear-gradient(135deg, #3b82f6, #2563eb)",
                            color: "#ffffff",
                            border: "none",
                            fontSize: "11px",
                            fontWeight: 600,
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "5px",
                            width: "fit-content",
                          }}
                        >
                          💳 Pay Fee ₹{(con.fee_amount ?? 2500).toLocaleString("en-IN")}
                        </button>
                      )}

                      {con.status === "PAID" && (
                        <div style={{ marginTop: "6px", fontSize: "11px", color: "#10b981", fontWeight: 600 }}>
                          ✓ Fee Paid & Confirmed
                        </div>
                      )}

                      {["SCHEDULED", "IN_PROGRESS"].includes(con.status) && (
                        <a
                          href={`/consultations/${con.id}/room`}
                          className={styles.consultLink}
                          style={{
                            marginTop: "8px",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "6px",
                            backgroundColor: "#2563eb",
                            color: "#ffffff",
                            padding: "6px 12px",
                            borderRadius: "6px",
                            fontWeight: 600,
                            fontSize: "12px",
                            textDecoration: "none",
                          }}
                        >
                          🎥 Enter Video Consultation Room
                        </a>
                      )}

                      {con.status === "COMPLETED" && con.case_id && (
                        <a
                          href={`/cases/${con.case_id}`}
                          style={{
                            marginTop: "6px",
                            display: "inline-block",
                            fontSize: "12px",
                            color: "#38bdf8",
                            textDecoration: "underline",
                            fontWeight: 600,
                          }}
                        >
                          ⚖️ View Linked Case Matter →
                        </a>
                      )}

                      {con.status === "COMPLETED" && !con.case_id && (
                        <a
                          href={`/consultations/${con.id}/room`}
                          style={{
                            marginTop: "6px",
                            display: "inline-block",
                            fontSize: "12px",
                            color: "#a855f7",
                            textDecoration: "underline",
                            fontWeight: 600,
                          }}
                        >
                          ⚖️ Convert into Legal Case →
                        </a>
                      )}

                      {/* Reschedule & Cancel Triggers for Active Consultations */}
                      {["REQUESTED", "ACCEPTED", "PAID", "SCHEDULED"].includes(con.status) && (
                        <div style={{ display: "flex", gap: "6px", marginTop: "8px" }}>
                          <button
                            onClick={() => setActionConsultationModal({ type: "RESCHEDULE", consultation: con })}
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
                            onClick={() => setActionConsultationModal({ type: "CANCEL", consultation: con })}
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
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Indian Legal Operating Tech Quick Info */}
            <div className={styles.quickHelpBox}>
              <div className={styles.quickHelpTitle}>
                <span>✦</span> Grounded Legal Copilot
              </div>
              <p className={styles.quickHelpText}>
                Every case workspace includes an AI Copilot grounded in your uploaded agreements, evidence records, and verified Indian statutory provisions.
              </p>
              <div style={{ fontSize: "11px", color: "#a5b0c4", borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "10px" }}>
                🔒 Strict role-aware authorization & private AWS S3 document architecture.
              </div>
            </div>
          </aside>
        </div>

        {/* New Case Creation Modal */}
        {createModalOpen && (
          <div
            className={styles.modalOverlay}
            onClick={() => setCreateModalOpen(false)}
          >
            <div
              className={styles.modalWindow}
              onClick={(e) => e.stopPropagation()}
            >
              <div className={styles.modalHeader}>
                <h3 className={styles.modalTitle}>Initiate Case Workspace</h3>
                <button
                  type="button"
                  className={styles.modalCloseBtn}
                  onClick={() => setCreateModalOpen(false)}
                  aria-label="Close dialog"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleCreateCase}>
                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Matter Title / Caption</label>
                  <input
                    type="text"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="e.g. Commercial Lease Dispute with Alpha Corp"
                    required
                    className={styles.formInput}
                    autoFocus
                  />
                </div>

                <div className={styles.formGroup}>
                  <label className={styles.formLabel}>Matter Summary & Background</label>
                  <textarea
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                    placeholder="Summarize the core transaction, dispute, involved parties, or advisory scope..."
                    rows={4}
                    className={styles.formTextarea}
                  />
                </div>

                <div className={styles.modalFooter}>
                  <button
                    type="button"
                    onClick={() => setCreateModalOpen(false)}
                    className={styles.secondaryActionBtn}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creating || !newTitle.trim()}
                    className={styles.primaryActionBtn}
                  >
                    {creating ? "Provisioning Workspace..." : "Create Workspace →"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Payment Checkout Modal */}
        {checkoutConsultation && (
          <PaymentCheckoutModal
            consultation={checkoutConsultation}
            onClose={() => setCheckoutConsultation(null)}
            onPaymentSuccess={() => {
              setCheckoutConsultation(null);
              fetchDashboardData();
            }}
          />
        )}

        {/* Consultation Reschedule & Cancel Modal */}
        {actionConsultationModal && (
          <ConsultationActionModal
            type={actionConsultationModal.type}
            consultation={actionConsultationModal.consultation}
            onClose={() => setActionConsultationModal(null)}
            onSuccess={() => {
              setActionConsultationModal(null);
              fetchDashboardData();
            }}
          />
        )}
      </div>
    </div>
  );
}
