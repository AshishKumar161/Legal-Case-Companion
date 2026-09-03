"use client";

import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { apiClient } from "@/api/client";
import Link from "next/link";
import { LawyerProfileItem, LawyerAvailabilityItem } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function LawyerProfile() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<LawyerProfileItem | null>(null);
  const [availabilities, setAvailabilities] = useState<LawyerAvailabilityItem[]>([]);
  const [fetching, setFetching] = useState(true);

  // Tab state
  const [activeTab, setActiveTab] = useState<"profile" | "availability" | "verification">("profile");

  // Edit Profile Form state
  const [fee, setFee] = useState<number>(2500);
  const [location, setLocation] = useState<string>("");
  const [experience, setExperience] = useState<number>(5);
  const [bio, setBio] = useState<string>("");
  const [practiceAreasInput, setPracticeAreasInput] = useState<string>("");
  const [languagesInput, setLanguagesInput] = useState<string>("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMsg, setProfileMsg] = useState<{ text: string; isError: boolean } | null>(null);

  // Availability Form state
  const [newDay, setNewDay] = useState<number>(0);
  const [newStartTime, setNewStartTime] = useState<string>("10:00:00");
  const [newEndTime, setNewEndTime] = useState<string>("18:00:00");
  const [newDuration, setNewDuration] = useState<number>(30);
  const [addingAvail, setAddingAvail] = useState(false);
  const [availMsg, setAvailMsg] = useState<{ text: string; isError: boolean } | null>(null);

  // Verification Form state
  const [enrollment, setEnrollment] = useState("");
  const [barCouncil, setBarCouncil] = useState("");
  const [submittingVerif, setSubmittingVerif] = useState(false);
  const [verifMsg, setVerifMsg] = useState<{ text: string; isError: boolean } | null>(null);

  // Presence heartbeat while lawyer profile tab is open
  useEffect(() => {
    if (!user || (user.role !== "LAWYER" && user.role !== "ADMIN")) return;
    const sendHeartbeat = () => {
      apiClient.post("/api/v1/lawyers/heartbeat", {}).catch(() => {});
    };
    sendHeartbeat();
    const interval = setInterval(sendHeartbeat, 15000);
    return () => clearInterval(interval);
  }, [user]);

  const fetchProfileAndAvailability = useCallback(async () => {
    try {
      setFetching(true);
      const [profRes, availRes] = await Promise.all([
        apiClient.get("/api/v1/profiles/me"),
        apiClient.get("/api/v1/profiles/lawyer/availability").catch(() => []),
      ]);

      setProfile(profRes);
      setAvailabilities(Array.isArray(availRes) ? availRes : []);

      if (profRes) {
        setFee(profRes.consultation_fee || 2500);
        setLocation(profRes.location || "");
        setExperience(profRes.experience_years || 5);
        setBio(profRes.bio || "");
        const pas = Array.isArray(profRes.practice_areas)
          ? profRes.practice_areas.join(", ")
          : profRes.practice_areas || "";
        setPracticeAreasInput(pas);
        const langs = Array.isArray(profRes.languages)
          ? profRes.languages.join(", ")
          : profRes.languages || "English, Hindi";
        setLanguagesInput(langs);
      }
    } catch (err) {
      console.error("Failed to load lawyer profile", err);
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
    else if (user?.role !== "LAWYER" && user?.role !== "ADMIN") router.push("/dashboard");
    else void fetchProfileAndAvailability();
  }, [user, loading, router, fetchProfileAndAvailability]);

  // Handle Profile Update
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    setProfileMsg(null);

    try {
      const pas = practiceAreasInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const langs = languagesInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const res = await apiClient.patch("/api/v1/profiles/lawyer", {
        consultation_fee: Number(fee),
        location: location.trim(),
        experience_years: Number(experience),
        bio: bio.trim(),
        practice_areas: pas,
        languages: langs,
      });

      setProfile(res);
      setProfileMsg({ text: "Advocate profile credentials updated successfully.", isError: false });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update profile";
      setProfileMsg({ text: msg, isError: true });
    } finally {
      setSavingProfile(false);
    }
  };

  // Handle Add Availability Slot
  const handleAddAvailability = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddingAvail(true);
    setAvailMsg(null);

    try {
      await apiClient.post("/api/v1/profiles/lawyer/availability", {
        day_of_week: Number(newDay),
        start_time: newStartTime.length === 5 ? `${newStartTime}:00` : newStartTime,
        end_time: newEndTime.length === 5 ? `${newEndTime}:00` : newEndTime,
        slot_duration_minutes: Number(newDuration),
        is_active: true,
      });

      setAvailMsg({ text: "Availability window configured successfully.", isError: false });
      void fetchProfileAndAvailability();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to add availability";
      setAvailMsg({ text: msg, isError: true });
    } finally {
      setAddingAvail(false);
    }
  };

  // Handle Delete Availability Slot
  const handleDeleteAvailability = async (id: string) => {
    try {
      await apiClient.delete(`/api/v1/profiles/lawyer/availability/${id}`);
      setAvailabilities((prev) => prev.filter((a) => a.id !== id));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete slot";
      alert(msg);
    }
  };

  // Handle Verification Submission
  const handleSubmitVerification = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enrollment.trim() || !barCouncil.trim()) return;

    setSubmittingVerif(true);
    setVerifMsg(null);
    try {
      await apiClient.post("/api/v1/profiles/lawyer/verification", {
        enrollment_number: enrollment.trim(),
        state_bar_council: barCouncil.trim(),
      });
      setVerifMsg({
        text: "Bar Council verification submitted. Platform administrators will review your credentials.",
        isError: false,
      });
      void fetchProfileAndAvailability();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to submit verification credentials.";
      setVerifMsg({ text: msg, isError: true });
    } finally {
      setSubmittingVerif(false);
    }
  };

  if (loading || fetching) {
    return (
      <div style={{ padding: "80px 0", textAlign: "center", color: "var(--text-secondary)" }}>
        Loading advocate practice suite...
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
          <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>Practice Profile & Availability</span>
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
              <span>●</span> Chambers Profile & Operating Hours
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
              <h1 style={{ fontSize: "28px", fontWeight: 700, color: "var(--text-primary)" }}>
                {profile?.full_name || "Advocate Chambers"}
              </h1>
              <StatusBadge
                status={isVerified ? "VERIFIED" : "PENDING"}
                label={isVerified ? "Verified Bar Counsel" : "Verification Pending"}
              />
            </div>
            <p style={{ color: "var(--text-secondary)", fontSize: "14px", marginTop: "6px" }}>
              Maintain your directory credentials, recurring consultation slots, and Bar Council verification.
            </p>
          </div>

          <div style={{ display: "flex", gap: "10px" }}>
            {profile && (
              <Link href={`/lawyers/${profile.id}`} className="btn btn-secondary">
                View Public Profile →
              </Link>
            )}
            <Link href="/lawyer/dashboard" className="btn btn-secondary">
              ← Return to Hub
            </Link>
          </div>
        </div>

        {/* Sub-Navigation Tabs */}
        <div
          style={{
            display: "flex",
            gap: "12px",
            borderBottom: "1px solid var(--border-subtle)",
            marginBottom: "28px",
          }}
        >
          <button
            onClick={() => setActiveTab("profile")}
            style={{
              background: "none",
              border: "none",
              borderBottom: activeTab === "profile" ? "2px solid var(--accent-secondary)" : "2px solid transparent",
              padding: "10px 16px",
              fontSize: "14px",
              fontWeight: activeTab === "profile" ? 700 : 500,
              color: activeTab === "profile" ? "var(--text-primary)" : "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            📋 Practice Details & Fee
          </button>
          <button
            onClick={() => setActiveTab("availability")}
            style={{
              background: "none",
              border: "none",
              borderBottom: activeTab === "availability" ? "2px solid var(--accent-secondary)" : "2px solid transparent",
              padding: "10px 16px",
              fontSize: "14px",
              fontWeight: activeTab === "availability" ? 700 : 500,
              color: activeTab === "availability" ? "var(--text-primary)" : "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            📅 Availability Schedule ({availabilities.length})
          </button>
          <button
            onClick={() => setActiveTab("verification")}
            style={{
              background: "none",
              border: "none",
              borderBottom: activeTab === "verification" ? "2px solid var(--accent-secondary)" : "2px solid transparent",
              padding: "10px 16px",
              fontSize: "14px",
              fontWeight: activeTab === "verification" ? 700 : 500,
              color: activeTab === "verification" ? "var(--text-primary)" : "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            🛡️ Bar Verification {isVerified ? "✓" : "⚠️"}
          </button>
        </div>

        {/* TAB 1: Edit Profile Form */}
        {activeTab === "profile" && (
          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "32px",
              maxWidth: "720px",
            }}
          >
            <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "8px" }}>
              Update Practice Profile
            </h2>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "20px" }}>
              These parameters are displayed publicly in the advocate directory and determine consultation booking rates.
            </p>

            {profileMsg && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: "6px",
                  background: profileMsg.isError ? "rgba(239, 68, 68, 0.12)" : "rgba(16, 185, 129, 0.12)",
                  color: profileMsg.isError ? "#ef4444" : "#10b981",
                  border: profileMsg.isError ? "1px solid rgba(239, 68, 68, 0.25)" : "1px solid rgba(16, 185, 129, 0.25)",
                  fontSize: "13px",
                  marginBottom: "18px",
                }}
              >
                {profileMsg.text}
              </div>
            )}

            <form onSubmit={handleSaveProfile}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div className="input-group">
                  <label className="input-label">Consultation Fee (₹ per 30 min session) *</label>
                  <input
                    type="number"
                    className="input-field"
                    value={fee}
                    onChange={(e) => setFee(Number(e.target.value))}
                    min={0}
                    step={100}
                    required
                  />
                </div>

                <div className="input-group">
                  <label className="input-label">Years of Standing at Bar *</label>
                  <input
                    type="number"
                    className="input-field"
                    value={experience}
                    onChange={(e) => setExperience(Number(e.target.value))}
                    min={0}
                    max={60}
                    required
                  />
                </div>
              </div>

              <div className="input-group">
                <label className="input-label">Chambers Location / Base Jurisdiction</label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. New Delhi, Delhi High Court"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
              </div>

              <div className="input-group">
                <label className="input-label">Practice Areas (comma separated)</label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. Corporate Law, Commercial Arbitration, Intellectual Property"
                  value={practiceAreasInput}
                  onChange={(e) => setPracticeAreasInput(e.target.value)}
                />
              </div>

              <div className="input-group">
                <label className="input-label">Languages (comma separated)</label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. English, Hindi, Punjabi"
                  value={languagesInput}
                  onChange={(e) => setLanguagesInput(e.target.value)}
                />
              </div>

              <div className="input-group">
                <label className="input-label">Professional Bio & Chambers Summary</label>
                <textarea
                  className="input-field"
                  rows={4}
                  placeholder="Summarize your counsel background, notable litigation experience, and advisory domains..."
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                />
              </div>

              <div style={{ marginTop: "24px" }}>
                <button
                  type="submit"
                  className={`btn btn-primary ${savingProfile ? "btn-disabled" : ""}`}
                  disabled={savingProfile}
                >
                  {savingProfile ? "Saving Profile..." : "Save Profile Changes →"}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* TAB 2: Availability Schedule Management */}
        {activeTab === "availability" && (
          <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "28px", alignItems: "start" }}>
            {/* Existing Availability List */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "28px",
              }}
            >
              <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "8px" }}>
                Active Availability Schedule
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "20px" }}>
                Clients can only book video consultation sessions during these configured recurring hours.
              </p>

              {availabilities.length === 0 ? (
                <div style={{ padding: "24px", background: "var(--surface-elevated)", borderRadius: "8px", textAlign: "center", fontSize: "13px", color: "var(--text-muted)" }}>
                  No recurring availability configured. Configure your weekly chambers hours on the right to become bookable.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {availabilities.map((slot) => (
                    <div
                      key={slot.id}
                      style={{
                        padding: "14px 18px",
                        background: "var(--surface-elevated)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "8px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: "var(--text-primary)" }}>
                          {DAY_NAMES[slot.day_of_week] || `Day ${slot.day_of_week}`}
                        </div>
                        <div style={{ fontSize: "12px", color: "var(--accent-secondary)", marginTop: "2px" }}>
                          {slot.start_time.slice(0, 5)} - {slot.end_time.slice(0, 5)} ({slot.slot_duration_minutes || 30} min slots)
                        </div>
                      </div>

                      <button
                        onClick={() => handleDeleteAvailability(slot.id)}
                        className="btn btn-secondary"
                        style={{ padding: "4px 10px", fontSize: "11px", color: "#ef4444" }}
                        title="Delete slot rule"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Add Availability Slot Form */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "28px",
              }}
            >
              <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "8px" }}>
                Configure Recurring Slot
              </h2>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "18px" }}>
                Add a new recurring consultation window for your weekly chambers roster.
              </p>

              {availMsg && (
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "6px",
                    background: availMsg.isError ? "rgba(239, 68, 68, 0.12)" : "rgba(16, 185, 129, 0.12)",
                    color: availMsg.isError ? "#ef4444" : "#10b981",
                    border: availMsg.isError ? "1px solid rgba(239, 68, 68, 0.25)" : "1px solid rgba(16, 185, 129, 0.25)",
                    fontSize: "13px",
                    marginBottom: "16px",
                  }}
                >
                  {availMsg.text}
                </div>
              )}

              <form onSubmit={handleAddAvailability}>
                <div className="input-group">
                  <label className="input-label">Day of the Week</label>
                  <select
                    className="input-field"
                    value={newDay}
                    onChange={(e) => setNewDay(Number(e.target.value))}
                  >
                    {DAY_NAMES.map((name, idx) => (
                      <option key={idx} value={idx}>
                        {name}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                  <div className="input-group">
                    <label className="input-label">Start Time</label>
                    <input
                      type="time"
                      className="input-field"
                      value={newStartTime.slice(0, 5)}
                      onChange={(e) => setNewStartTime(e.target.value)}
                      required
                    />
                  </div>

                  <div className="input-group">
                    <label className="input-label">End Time</label>
                    <input
                      type="time"
                      className="input-field"
                      value={newEndTime.slice(0, 5)}
                      onChange={(e) => setNewEndTime(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="input-group">
                  <label className="input-label">Slot Duration (Minutes)</label>
                  <select
                    className="input-field"
                    value={newDuration}
                    onChange={(e) => setNewDuration(Number(e.target.value))}
                  >
                    <option value={15}>15 minutes</option>
                    <option value={30}>30 minutes (Standard)</option>
                    <option value={45}>45 minutes</option>
                    <option value={60}>60 minutes</option>
                  </select>
                </div>

                <div style={{ marginTop: "20px" }}>
                  <button
                    type="submit"
                    className={`btn btn-primary ${addingAvail ? "btn-disabled" : ""}`}
                    disabled={addingAvail}
                    style={{ width: "100%", justifyContent: "center" }}
                  >
                    {addingAvail ? "Adding Slot..." : "+ Add Availability Rule"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* TAB 3: Bar Council Verification */}
        {activeTab === "verification" && (
          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "32px",
              maxWidth: "680px",
            }}
          >
            <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "8px" }}>
              State Bar Council Verification Credentials
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: 1.6, marginBottom: "20px" }}>
              To ensure verified professional standing on Legal Case Companion, counsel must provide active State Bar Council enrollment credentials. Upon verification by platform administrators, you become discoverable in public counsel search.
            </p>

            {verifMsg && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: "6px",
                  background: verifMsg.isError ? "rgba(239, 68, 68, 0.12)" : "rgba(16, 185, 129, 0.12)",
                  color: verifMsg.isError ? "#ef4444" : "#10b981",
                  border: verifMsg.isError ? "1px solid rgba(239, 68, 68, 0.25)" : "1px solid rgba(16, 185, 129, 0.25)",
                  fontSize: "13px",
                  marginBottom: "18px",
                }}
              >
                {verifMsg.text}
              </div>
            )}

            <form onSubmit={handleSubmitVerification}>
              <div className="input-group">
                <label className="input-label">Bar Enrollment Number *</label>
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
                <label className="input-label">State Bar Council *</label>
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
                  className={`btn btn-primary ${submittingVerif ? "btn-disabled" : ""}`}
                  disabled={submittingVerif || !enrollment.trim() || !barCouncil.trim()}
                >
                  {submittingVerif ? "Submitting Credentials..." : "Submit for Bar Verification →"}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
