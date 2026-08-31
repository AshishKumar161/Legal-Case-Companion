"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/api/client";
import Link from "next/link";

export default function NewCase() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setLoading(true);
    setError("");

    try {
      const res = await apiClient.post("/api/v1/cases", {
        title: title.trim(),
        description: description.trim(),
      });
      router.push(`/cases/${res.id}`);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to provision case workspace. Please try again.");
      }
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "32px 0 80px" }}>
      <div className="container" style={{ maxWidth: "760px" }}>
        {/* Navigation Breadcrumb */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--text-muted)", marginBottom: "20px" }}>
          <Link href="/dashboard" style={{ color: "var(--text-secondary)" }}>Matters</Link>
          <span>/</span>
          <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>Open New Case</span>
        </div>

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
            <span>●</span> Matter Provisioning Intake
          </div>
          <h1 style={{ fontSize: "28px", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.03em" }}>
            Open a New Case File
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "14px", marginTop: "6px", lineHeight: 1.5 }}>
            Establish a secure legal workspace to organize dispute documentation, track statutory limitation deadlines, and access evidence-grounded AI analysis.
          </p>
        </div>

        {/* Card Form */}
        <div
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "32px",
            boxShadow: "var(--shadow-md)",
          }}
        >
          {error && (
            <div
              style={{
                color: "var(--error)",
                background: "rgba(239, 68, 68, 0.12)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                padding: "12px 16px",
                borderRadius: "8px",
                fontSize: "13px",
                marginBottom: "20px",
              }}
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="input-group">
              <label className="input-label">Matter Caption / Title</label>
              <input
                type="text"
                className="input-field"
                placeholder="e.g. Commercial Lease Dispute with Alpha Corp"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                autoFocus
              />
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                Provide a descriptive reference for the dispute, contract, or advisory matter.
              </span>
            </div>

            <div className="input-group" style={{ marginTop: "18px" }}>
              <label className="input-label">Summary & Factual Background</label>
              <textarea
                className="input-field"
                placeholder="Detail the dispute history, involved parties, key dates, or specific relief sought..."
                rows={6}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                style={{ resize: "vertical", lineHeight: 1.5 }}
              />
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                This summary initializes the matter intelligence graph and helps counsel quickly assess the brief.
              </span>
            </div>

            <div
              style={{
                marginTop: "32px",
                paddingTop: "20px",
                borderTop: "1px solid var(--border-subtle)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <Link href="/dashboard" className="btn btn-secondary">
                ← Return to Matters
              </Link>
              <button
                type="submit"
                className={`btn btn-primary ${loading ? "btn-disabled" : ""}`}
                disabled={loading || !title.trim()}
              >
                {loading ? "Provisioning..." : "Establish Matter Workspace →"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
