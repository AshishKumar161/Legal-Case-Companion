"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import { CaseItem } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { EmptyState } from "@/components/EmptyState";

export default function CasesPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [cases, setCases] = useState<CaseItem[]>([]);
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
          <EmptyState
            title="No Legal Matters Found"
            description={
              searchQuery || statusFilter !== "ALL"
                ? "No matters match the current filter criteria. Try resetting your search."
                : "You have no active legal matters. Create a new matter or schedule a consultation with verified counsel."
            }
            actionLabel={!searchQuery && statusFilter === "ALL" ? "+ Create First Matter" : undefined}
            onAction={!searchQuery && statusFilter === "ALL" ? () => setCreateModalOpen(true) : undefined}
          />
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: "20px" }}>
            {filteredCases.map((c) => (
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
                  transition: "border-color 0.2s, transform 0.2s",
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "10px", marginBottom: "12px" }}>
                    <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      MATTER #{c.id.slice(0, 8).toUpperCase()}
                    </span>
                    <StatusBadge status={c.status} />
                  </div>

                  <h3 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
                    {c.title}
                  </h3>

                  <p
                    style={{
                      fontSize: "13px",
                      color: "var(--text-secondary)",
                      lineHeight: 1.5,
                      marginBottom: "16px",
                      display: "-webkit-box",
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {c.description || "No matter synopsis recorded. Access workspace to attach evidence documents and timelines."}
                  </p>
                </div>

                <div
                  style={{
                    borderTop: "1px solid var(--border-subtle)",
                    paddingTop: "14px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                    Opened {new Date(c.created_at).toLocaleDateString()}
                  </span>

                  <Link href={`/cases/${c.id}`} className="btn btn-secondary" style={{ fontSize: "12px", padding: "6px 14px" }}>
                    Open Workspace →
                  </Link>
                </div>
              </div>
            ))}
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
