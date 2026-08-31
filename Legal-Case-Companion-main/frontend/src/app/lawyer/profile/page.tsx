"use client";

import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { apiClient } from "@/api/client";
import Link from "next/link";
import { LawyerProfileItem } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";

export default function LawyerProfile() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<LawyerProfileItem | null>(null);
  const [fetching, setFetching] = useState(true);

  const [enrollment, setEnrollment] = useState("");
  const [barCouncil, setBarCouncil] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [msg, setMsg] = useState("");
  const [isSuccess, setIsSuccess] = useState(false);

  const fetchProfile = useCallback(async () => {
    try {
      setFetching(true);
      const res = await apiClient.get("/api/v1/profiles/me");
      setProfile(res);
    } catch (err) {
      console.error(err);
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
    else if (user?.role !== "LAWYER" && user?.role !== "ADMIN") router.push("/dashboard");
    else void fetchProfile();
  }, [user, loading, router, fetchProfile]);

  const submitVerification = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enrollment.trim() || !barCouncil.trim()) return;

    setSubmitting(true);
    setMsg("");
    try {
      await apiClient.post("/api/v1/profiles/lawyer/verification", {
        enrollment_number: enrollment.trim(),
        state_bar_council: barCouncil.trim(),
      });
      setIsSuccess(true);
      setMsg("Bar Council verification request submitted successfully. Platform administrators will review your credentials.");
      void fetchProfile();
    } catch (err: unknown) {
      setIsSuccess(false);
      if (err instanceof Error) {
        setMsg(err.message);
      } else {
        setMsg("Failed to submit verification credentials.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || fetching) {
    return (
      <div style={{ padding: "80px 0", textAlign: "center", color: "var(--text-secondary)" }}>
        Loading advocate profile...
      </div>
    );
  }

  const isVerified = profile?.verification_status === "VERIFIED";

  return (
    <div style={{ padding: "32px 0 80px" }}>
      <div className="container">
        {/* Navigation Breadcrumbs */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px", color: "var(--text-muted)", marginBottom: "20px" }}>
          <Link href="/lawyer/dashboard" style={{ color: "var(--text-secondary)" }}>Advocate Hub</Link>
          <span>/</span>
          <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>Profile & Bar Verification</span>
        </div>

        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "28px", flexWrap: "wrap", gap: "16px" }}>
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
              <span>●</span> Bar Council Standing & Public Bio
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
              <h1 style={{ fontSize: "28px", fontWeight: 700, color: "var(--text-primary)" }}>
                {profile?.full_name || "Advocate Profile"}
              </h1>
              <StatusBadge
                status={isVerified ? "VERIFIED" : "PENDING"}
                label={isVerified ? "Verified Bar Counsel" : "Verification Pending"}
              />
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "14px", marginTop: "6px" }}>
              Maintain your official enrollment details, consultation parameters, and public directory standing.
            </p>
          </div>

          <Link href="/lawyer/dashboard" className="btn btn-secondary">
            ← Return to Practice Hub
          </Link>
        </div>

        {/* Two-Column Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
          {/* Public Profile Card */}
          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "28px",
            }}
          >
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "20px" }}>
              Public Directory Credentials
            </h2>

            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                  Full Legal Name
                </div>
                <div style={{ fontSize: "14px", fontWeight: 600, color: "#fff", marginTop: "2px" }}>
                  {profile?.full_name || "Not registered"}
                </div>
              </div>

              <div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                  Chambers Location
                </div>
                <div style={{ fontSize: "14px", color: "var(--text-primary)", marginTop: "2px" }}>
                  {profile?.location || "India"}
                </div>
              </div>

              <div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                  Consultation Fee Rate
                </div>
                <div style={{ fontSize: "15px", fontWeight: 700, color: "var(--accent-secondary)", marginTop: "2px" }}>
                  ₹{profile?.consultation_fee || 2500} <span style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 400 }}>/ 30 min session</span>
                </div>
              </div>

              <div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                  Standing & Experience
                </div>
                <div style={{ fontSize: "14px", color: "var(--text-primary)", marginTop: "2px" }}>
                  {profile?.experience_years ? `${profile.experience_years} Years Standing at Bar` : "Senior Counsel"}
                </div>
              </div>

              <div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 700 }}>
                  Professional Bio
                </div>
                <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5, marginTop: "4px" }}>
                  {profile?.bio || "No professional biography on file. Advise clients of litigation and advisory practice areas."}
                </p>
              </div>
            </div>
          </div>

          {/* Bar Verification Card */}
          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "28px",
            }}
          >
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
              State Bar Council Verification
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.5, marginBottom: "20px" }}>
              To ensure verified professional standing on Legal Case Companion, counsel must provide active State Bar Council enrollment credentials.
            </p>

            {msg && (
              <div
                style={{
                  padding: "12px 14px",
                  borderRadius: "8px",
                  fontSize: "13px",
                  marginBottom: "18px",
                  background: isSuccess ? "rgba(16, 185, 129, 0.12)" : "rgba(239, 68, 68, 0.12)",
                  color: isSuccess ? "#10b981" : "#ef4444",
                  border: isSuccess ? "1px solid rgba(16, 185, 129, 0.3)" : "1px solid rgba(239, 68, 68, 0.3)",
                }}
              >
                {msg}
              </div>
            )}

            <form onSubmit={submitVerification}>
              <div className="input-group">
                <label className="input-label">Bar Enrollment Number</label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. D/1482/2014"
                  value={enrollment}
                  onChange={(e) => setEnrollment(e.target.value)}
                  required
                />
              </div>

              <div className="input-group">
                <label className="input-label">State Bar Council</label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. Bar Council of Delhi"
                  value={barCouncil}
                  onChange={(e) => setBarCouncil(e.target.value)}
                  required
                />
              </div>

              <div style={{ marginTop: "24px" }}>
                <button
                  type="submit"
                  className={`btn btn-primary ${submitting ? "btn-disabled" : ""}`}
                  disabled={submitting || !enrollment.trim() || !barCouncil.trim()}
                >
                  {submitting ? "Submitting Credentials..." : "Submit for Bar Verification →"}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
