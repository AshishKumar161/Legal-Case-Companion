"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import { CaseItem, MatterBriefItem } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { EmptyState } from "@/components/EmptyState";
import LegalTerm from "@/components/LegalTerm";

export default function CasesPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [cases, setCases] = useState<CaseItem[]>([]);
  const [briefsByCaseId, setBriefsByCaseId] = useState<Record<string, MatterBriefItem>>({});
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [sortBy, setSortBy] = useState<"updated" | "title" | "status">("updated");

  // Create Case Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const fetchCases = useCallback(async () => {
    try {
      setFetching(true);
      setError(null);
      const res = await apiClient.get("/api/v1/cases");
      const items: CaseItem[] = Array.isArray(res) ? res : res?.items || [];
      setCases(items);

      if (items.length > 0) {
        const topCases = items.slice(0, 12);
        const briefs = await Promise.all(
          topCases.map(async (c) => {
            const brief = await apiClient.get(`/api/v1/cases/${c.id}/collaboration/brief`).catch(() => null);
            return { caseId: c.id, brief };
          })
        );
        const newBriefs: Record<string, MatterBriefItem> = {};
        for (const b of briefs) {
          if (b.brief) newBriefs[b.caseId] = b.brief;
        }
        setBriefsByCaseId(newBriefs);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load matters";
      setError(msg);
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    } else if (user) {
      void fetchCases();
    }
  }, [user, loading, router, fetchCases]);

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || creating) return;

    setCreating(true);
    setCreateError(null);
    try {
      const res: any = await apiClient.post("/api/v1/cases", {
        title: newTitle.trim(),
        description: newDesc.trim(),
      });
      setCreateModalOpen(false);
      setNewTitle("");
      setNewDesc("");
      router.push(`/cases/${res.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create case";
      setCreateError(msg);
    } finally {
      setCreating(false);
    }
  };

  const filteredCases = useMemo(() => {
    return cases
      .filter((c) => {
        const matchesStatus = statusFilter === "ALL" || c.status === statusFilter;
        const matchesSearch =
          searchQuery === "" ||
          c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (c.description && c.description.toLowerCase().includes(searchQuery.toLowerCase()));
        return matchesStatus && matchesSearch;
      })
      .sort((a, b) => {
        if (sortBy === "title") return a.title.localeCompare(b.title);
        if (sortBy === "status") return a.status.localeCompare(b.status);
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
  }, [cases, statusFilter, searchQuery, sortBy]);

  const openCount = cases.filter((c) => c.status === "OPEN" || c.status === "IN_PROGRESS").length;
  const closedCount = cases.filter((c) => c.status === "CLOSED" || c.status === "ARCHIVED").length;

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
              <span>●</span> Active Legal Portfolio
            </div>
            <h1 style={{ fontSize: "28px", fontWeight: 700, color: "var(--text-primary)" }}>
              {user?.role === "LAWYER" ? "Counsel Matter Roster" : "Legal Matters & Cases"}
            </h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "14px", marginTop: "6px" }}>
              Secure collaborative workspaces, evidence repositories, and litigation timelines.
            </p>
          </div>

          <button onClick={() => setCreateModalOpen(true)} className="btn btn-primary">
            + Create New Matter
          </button>
        </div>

        {/* Metrics Bar */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "16px",
            marginBottom: "28px",
          }}
        >
          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "16px 20px",
            }}
          >
            <div style={{ fontSize: "12px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
              Total Matters
            </div>
            <div style={{ fontSize: "26px", fontWeight: 700, color: "var(--text-primary)", marginTop: "4px" }}>
              {cases.length}
            </div>
          </div>

          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "16px 20px",
            }}
          >
            <div style={{ fontSize: "12px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
              Active / In Progress
            </div>
            <div style={{ fontSize: "26px", fontWeight: 700, color: "var(--accent-secondary)", marginTop: "4px" }}>
              {openCount}
            </div>
          </div>

          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "16px 20px",
            }}
          >
            <div style={{ fontSize: "12px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
              Closed / Resolved
            </div>
            <div style={{ fontSize: "26px", fontWeight: 700, color: "#94a3b8", marginTop: "4px" }}>
              {closedCount}
            </div>
          </div>
        </div>

        {/* Search & Filter Bar */}
        <div
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "16px 20px",
            marginBottom: "24px",
            display: "flex",
            gap: "14px",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", gap: "12px", flex: 1, minWidth: "260px" }}>
            <input
              type="text"
              placeholder="Search matters by title or keywords..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field"
              style={{ flex: 1 }}
            />
          </div>

          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center" }}>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input-field"
              style={{ width: "auto" }}
            >
              <option value="ALL">All Statuses</option>
              <option value="OPEN">Open</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="CLOSED">Closed</option>
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="input-field"
              style={{ width: "auto" }}
            >
              <option value="updated">Sort: Newest</option>
              <option value="title">Sort: Title</option>
              <option value="status">Sort: Status</option>
            </select>
          </div>
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

        {/* Matters Grid */}
        {filteredCases.length === 0 ? (
          cases.length === 0 ? (
            <div
              style={{
                background: "var(--surface-card, #0e121a)",
                border: "1px dashed var(--border-subtle, rgba(255, 255, 255, 0.15))",
                borderRadius: "16px",
                padding: "48px 24px",
                textAlign: "center",
                maxWidth: "600px",
                margin: "40px auto",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
              }}
            >
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "50%",
                  background: "rgba(99, 102, 241, 0.12)",
                  border: "1px solid rgba(99, 102, 241, 0.25)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "24px",
                  color: "var(--brand-primary, #818cf8)",
                  marginBottom: "16px",
                }}
              >
                ⚖
              </div>
              <h2 style={{ fontSize: "20px", fontWeight: 700, color: "#fff", marginBottom: "8px" }}>
                You don&apos;t have a case yet.
              </h2>
              <p style={{ fontSize: "14px", color: "var(--text-secondary, #94a3b8)", lineHeight: "1.6", maxWidth: "440px", marginBottom: "24px" }}>
                Create a case to keep your documents, hearings, lawyer and important updates together.
              </p>
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", justifyContent: "center" }}>
                <button
                  onClick={() => setCreateModalOpen(true)}
                  className="btn btn-primary"
                  style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}
                >
                  <span>+</span> Create a case
                </button>
                <Link
                  href="/lawyers"
                  className="btn btn-secondary"
                  style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}
                >
                  <span>⚖</span> Find a lawyer
                </Link>
              </div>
            </div>
          ) : (
            <EmptyState
              title="No Legal Matters Found"
              description="No matters match the current filter criteria. Try resetting your search."
            />
          )
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: "20px" }}>
            {filteredCases.map((c) => {
              const brief = briefsByCaseId[c.id];
              const courtDisplay = brief?.next_hearing_court || "Official Court Record";
              const nextEventDisplay = brief?.next_hearing_date
                ? `Next hearing: ${new Date(brief.next_hearing_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}`
                : "Waiting for next hearing";
              const lawyerDisplay = brief?.lead_counsel_name
                ? `Adv. ${brief.lead_counsel_name}`
                : "Not assigned yet";

              return (
                <div
                  key={c.id}
                  style={{
                    background: "var(--surface-card)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                    padding: "24px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    gap: "16px",
                    transition: "border-color 0.2s, transform 0.2s",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "10px", marginBottom: "8px" }}>
                      <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                        MATTER #{c.id.slice(0, 8).toUpperCase()}
                      </span>
                      <StatusBadge status={c.status} />
                    </div>

                    <div style={{ fontSize: "12px", color: "#38bdf8", fontWeight: 500, marginBottom: "4px" }}>
                      🏛 {courtDisplay}
                    </div>

                    <h3 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
                      {c.title}
                    </h3>

                    <div style={{ marginBottom: "12px" }}>
                      <LegalTerm term={c.status} layout="stacked" showBadge={false} />
                    </div>

                    <div
                      style={{
                        background: "rgba(7, 9, 14, 0.6)",
                        border: "1px solid rgba(255, 255, 255, 0.06)",
                        borderRadius: "8px",
                        padding: "8px 12px",
                        fontSize: "12px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "2px",
                        marginBottom: "12px",
                      }}
                    >
                      <span style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--brand-primary, #818cf8)", fontWeight: 700 }}>
                        Next Event
                      </span>
                      <span style={{ color: "#f1f5f9", fontWeight: 500 }}>
                        {nextEventDisplay}
                      </span>
                    </div>

                    <p
                      style={{
                        fontSize: "13px",
                        color: "var(--text-secondary)",
                        lineHeight: 1.5,
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {c.description || "No matter synopsis recorded."}
                    </p>
                  </div>

                  <div
                    style={{
                      borderTop: "1px solid var(--border-subtle)",
                      paddingTop: "14px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: "10px",
                      flexWrap: "wrap",
                    }}
                  >
                    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      <div><strong>Lawyer:</strong> {lawyerDisplay}</div>
                      <div>Updated: {new Date(c.updated_at || c.created_at).toLocaleDateString("en-IN")}</div>
                    </div>

                    <Link
                      href={`/cases/${c.id}`}
                      className="btn btn-secondary"
                      style={{ fontSize: "12px", padding: "6px 14px", whiteSpace: "nowrap" }}
                    >
                      Open case →
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Create Case Modal */}
        {createModalOpen && (
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
            onClick={() => setCreateModalOpen(false)}
          >
            <div
              style={{
                background: "var(--surface-elevated)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "28px",
                width: "100%",
                maxWidth: "520px",
                boxShadow: "var(--shadow-lg)",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                <h2 style={{ fontSize: "20px", fontWeight: 700, color: "var(--text-primary)" }}>
                  Initiate New Legal Matter
                </h2>
                <button
                  onClick={() => setCreateModalOpen(false)}
                  style={{ background: "none", border: "none", color: "var(--text-muted)", fontSize: "18px", cursor: "pointer" }}
                >
                  ✕
                </button>
              </div>

              {createError && (
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "6px",
                    background: "rgba(239, 68, 68, 0.12)",
                    color: "#ef4444",
                    border: "1px solid rgba(239, 68, 68, 0.25)",
                    fontSize: "13px",
                    marginBottom: "16px",
                  }}
                >
                  {createError}
                </div>
              )}

              <form onSubmit={handleCreateCase}>
                <div className="input-group">
                  <label className="input-label">Matter / Case Title *</label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="e.g. Commercial Lease Dispute - Phase 2"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    required
                  />
                </div>

                <div className="input-group">
                  <label className="input-label">Matter Brief & Description</label>
                  <textarea
                    className="input-field"
                    rows={4}
                    placeholder="Provide overview of claims, involved entities, and key factual background..."
                    value={newDesc}
                    onChange={(e) => setNewDesc(e.target.value)}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "24px" }}>
                  <button
                    type="button"
                    onClick={() => setCreateModalOpen(false)}
                    className="btn btn-secondary"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className={`btn btn-primary ${creating ? "btn-disabled" : ""}`}
                    disabled={creating || !newTitle.trim()}
                  >
                    {creating ? "Creating Workspace..." : "Create Case Workspace →"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
