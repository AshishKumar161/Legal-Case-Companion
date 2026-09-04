"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { apiClient } from "@/api/client";
import { LawyerProfileItem } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useAuth, UserRole } from "@/providers/AuthProvider";

interface SlotItem {
  start_time: string;
  end_time: string;
  duration_minutes: number;
  is_available: boolean;
}

export default function LawyerDiscovery() {
  const { user, login } = useAuth();
  const [lawyers, setLawyers] = useState<LawyerProfileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [authPromptLawyer, setAuthPromptLawyer] = useState<LawyerProfileItem | null>(null);
  const [quickLoginLoading, setQuickLoginLoading] = useState(false);

  // Filter states
  const [searchTerm, setSearchTerm] = useState("");
  const [location, setLocation] = useState("");
  const [practiceArea, setPracticeArea] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [minExp, setMinExp] = useState("");
  const [maxFee, setMaxFee] = useState("");
  const [language, setLanguage] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [onlineOnly, setOnlineOnly] = useState(false);

  // Live IST Clock
  const [istClock, setIstClock] = useState("");

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
      });
      const dateStr = now.toLocaleDateString("en-IN", {
        timeZone: "Asia/Kolkata",
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      });
      setIstClock(`${dateStr} • ${timeStr} IST`);
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  // Instant Consultation Modal state
  const [instantCallLawyer, setInstantCallLawyer] = useState<LawyerProfileItem | null>(null);
  const [instantSubmitting, setInstantSubmitting] = useState(false);
  const [instantError, setInstantError] = useState("");

  // Booking modal state
  const [bookingLawyer, setBookingLawyer] = useState<LawyerProfileItem | null>(null);
  const [selectedDate, setSelectedDate] = useState(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split("T")[0];
  });
  const [slots, setSlots] = useState<SlotItem[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<SlotItem | null>(null);
  const [fetchingSlots, setFetchingSlots] = useState(false);
  const [bookingSubmitting, setBookingSubmitting] = useState(false);
  const [bookingSuccess, setBookingSuccess] = useState("");
  const [bookingError, setBookingError] = useState("");
  const [bookedConsultationId, setBookedConsultationId] = useState<string | null>(null);

  const handleQuickClientLogin = async () => {
    setQuickLoginLoading(true);
    try {
      const res = await apiClient.post('/api/v1/auth/login', {
        email: 'client@lcc.test',
        password: 'Password123!',
      });
      const payload = JSON.parse(atob(res.access_token.split('.')[1]));
      login(
        res.access_token,
        {
          id: payload.sub,
          email: 'client@lcc.test',
          role: (payload.role || 'CLIENT') as UserRole,
          account_status: "ACTIVE",
          full_name: "Vikram Sharma",
        },
        res.refresh_token
      );
      const targetLawyer = authPromptLawyer;
      setAuthPromptLawyer(null);
      if (targetLawyer) {
        setBookingLawyer(targetLawyer);
      }
    } catch (err) {
      console.error("Quick client login failed", err);
    } finally {
      setQuickLoginLoading(false);
    }
  };

  const fetchLawyers = useCallback(async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    try {
      const params = new URLSearchParams();
      if (searchTerm.trim()) params.set("search", searchTerm.trim());
      if (location.trim()) params.set("location", location.trim());
      if (practiceArea.trim()) params.set("practice_area", practiceArea.trim());
      if (jurisdiction.trim()) params.set("court_jurisdiction", jurisdiction.trim());
      if (language.trim()) params.set("language", language.trim());
      if (minExp) params.set("min_experience", minExp);
      if (maxFee) params.set("max_fee", maxFee);
      params.set("verified_only", verifiedOnly ? "true" : "false");
      if (onlineOnly) params.set("online_only", "true");

      const url = `/api/v1/lawyers?${params.toString()}`;
      const res = await apiClient.get(url, { requireAuth: false });
      setLawyers(res.items || (Array.isArray(res) ? res : []));
    } catch (err) {
      console.error("Failed to fetch lawyers", err);
      if (!isBackground) setLawyers([]);
    } finally {
      if (!isBackground) setLoading(false);
    }
  }, [searchTerm, location, practiceArea, jurisdiction, language, minExp, maxFee, verifiedOnly, onlineOnly]);

  useEffect(() => {
    void fetchLawyers(false);
  }, [fetchLawyers]);

  // Periodic background refresh (every 6 seconds) to detect lawyer presence changes live
  useEffect(() => {
    const pollInterval = setInterval(() => {
      void fetchLawyers(true);
    }, 6000);
    return () => clearInterval(pollInterval);
  }, [fetchLawyers]);

  // Fetch slots when booking lawyer or date changes
  useEffect(() => {
    if (!bookingLawyer) return;
    const fetchSlots = async () => {
      setFetchingSlots(true);
      setSelectedSlot(null);
      try {
        const lawyerId = bookingLawyer.user_id || bookingLawyer.id;
        const res = await apiClient.get(`/api/v1/lawyers/${lawyerId}/slots?date=${selectedDate}&duration_minutes=30`, { requireAuth: false });
        setSlots(Array.isArray(res) ? res : res?.items || []);
      } catch {
        setSlots([]);
      } finally {
        setFetchingSlots(false);
      }
    };
    void fetchSlots();
  }, [bookingLawyer, selectedDate]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    void fetchLawyers();
  };

  const handleConfirmInstantCall = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!instantCallLawyer) return;
    setInstantSubmitting(true);
    setInstantError("");

    try {
      const lawyerId = instantCallLawyer.user_id || instantCallLawyer.id;
      // 1. Create immediate consultation at current time
      const conRes: any = await apiClient.post("/api/v1/consultations", {
        lawyer_id: lawyerId,
        scheduled_at: new Date().toISOString(),
        duration_minutes: 30,
        is_instant: true,
      });

      // 2. Authoritatively settle simulated test payment
      await apiClient.post(`/api/v1/consultations/${conRes.id}/pay-test`, {});

      // 3. Immediately redirect to video room
      window.location.href = `/consultations/${conRes.id}/room`;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to initiate instant video call.";
      setInstantError(msg);
      setInstantSubmitting(false);
    }
  };

  const handleBookConsultation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bookingLawyer || !selectedSlot) return;
    setBookingSubmitting(true);
    setBookingError("");
    setBookingSuccess("");

    try {
      const lawyerId = bookingLawyer.user_id || bookingLawyer.id;
      const res: any = await apiClient.post("/api/v1/consultations", {
        lawyer_id: lawyerId,
        scheduled_at: selectedSlot.start_time,
        duration_minutes: 30,
      });
      setBookedConsultationId(res.id);
      setBookingSuccess(
        `Consultation slot reserved successfully with ${bookingLawyer.full_name} for ${new Date(
          selectedSlot.start_time
        ).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}!`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Selected slot is no longer available.";
      setBookingError(msg);
    } finally {
      setBookingSubmitting(false);
    }
  };

  return (
    <div style={{ padding: "36px 0 80px" }}>
      <div className="container">
        {/* Header */}
        <div style={{ marginBottom: "32px", maxWidth: "820px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap", marginBottom: "8px" }}>
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
              }}
            >
              <span>●</span> Verified Indian Bar Directory
            </div>
            {istClock && (
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "4px 12px",
                  borderRadius: "16px",
                  background: "rgba(79, 91, 247, 0.12)",
                  border: "1px solid rgba(79, 91, 247, 0.3)",
                  color: "#a5b4fc",
                  fontSize: "12px",
                  fontWeight: 600,
                }}
              >
                <span>🕒</span> Indian Standard Time: <strong>{istClock}</strong>
              </div>
            )}
          </div>
          <h1 style={{ fontSize: "32px", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "-0.03em" }}>
            Retain Verified Indian Legal Counsel
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "14px", marginTop: "8px", lineHeight: 1.5 }}>
            Discover verified advocates across High Courts, Supreme Court, and specialized National Tribunals. Review verified enrollment credentials, transparent fee schedules, and schedule or conduct instant video consultation sessions.
          </p>
        </div>

        {/* Filter Bar */}
        <form
          onSubmit={handleSearch}
          style={{
            background: "var(--surface-card)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            padding: "20px 24px",
            marginBottom: "32px",
            display: "flex",
            flexDirection: "column",
            gap: "14px",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: "12px" }}>
            <input
              type="text"
              placeholder="Search advocate name or legal specialty..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input-field"
            />
            <input
              type="text"
              placeholder="Location (e.g. New Delhi, Mumbai)"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="input-field"
            />
            <input
              type="text"
              placeholder="Practice Area (e.g. Arbitration, Commercial)"
              value={practiceArea}
              onChange={(e) => setPracticeArea(e.target.value)}
              className="input-field"
            />
          </div>

          <div style={{ display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" }}>
            <input
              type="text"
              placeholder="Court Jurisdiction (e.g. Supreme Court, Delhi HC)"
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value)}
              className="input-field"
              style={{ flex: 1 }}
            />
            <input
              type="number"
              placeholder="Min Exp (Years)"
              value={minExp}
              onChange={(e) => setMinExp(e.target.value)}
              className="input-field"
              style={{ width: "150px" }}
            />
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="input-field"
              style={{ width: "160px" }}
            >
              <option value="">All Languages</option>
              <option value="English">English</option>
              <option value="Hindi">Hindi (हिंदी)</option>
              <option value="Bengali">Bengali (বাংলা)</option>
              <option value="Tamil">Tamil (தமிழ்)</option>
              <option value="Telugu">Telugu (తెలుగు)</option>
              <option value="Marathi">Marathi (मराठी)</option>
              <option value="Gujarati">Gujarati (ગુજરાતી)</option>
              <option value="Kannada">Kannada (ಕನ್ನಡ)</option>
              <option value="Malayalam">Malayalam (മലയാളം)</option>
              <option value="Punjabi">Punjabi (ਪੰਜਾਬੀ)</option>
            </select>
            <input
              type="number"
              placeholder="Max Fee (₹)"
              value={maxFee}
              onChange={(e) => setMaxFee(e.target.value)}
              className="input-field"
              style={{ width: "150px" }}
            />
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "13px",
                fontWeight: 600,
                color: onlineOnly ? "#10b981" : "var(--text-secondary)",
                cursor: "pointer",
                padding: "6px 12px",
                borderRadius: "6px",
                background: onlineOnly ? "rgba(16, 185, 129, 0.15)" : "rgba(255,255,255,0.04)",
                border: onlineOnly ? "1px solid rgba(16, 185, 129, 0.4)" : "1px solid var(--border-subtle)",
              }}
            >
              <input
                type="checkbox"
                checked={onlineOnly}
                onChange={(e) => setOnlineOnly(e.target.checked)}
              />
              🟢 Online Advocates Only
            </label>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "13px",
                color: "var(--text-secondary)",
                cursor: "pointer",
                padding: "0 8px",
              }}
            >
              <input
                type="checkbox"
                checked={verifiedOnly}
                onChange={(e) => setVerifiedOnly(e.target.checked)}
              />
              Verified Only
            </label>
            <button type="submit" className="btn btn-primary" style={{ padding: "9px 20px" }}>
              Filter Counsel
            </button>
          </div>
        </form>

        {/* Directory Grid */}
        {loading ? (
          <LoadingSkeleton type="card" count={4} />
        ) : lawyers.length === 0 ? (
          <EmptyState
            icon="⚖"
            title="No Matching Advocates Found"
            description="No legal counsel currently matches your search filters. Try broadening your keywords, clearing court jurisdiction, or resetting practice area filters."
            actionLabel="Reset Search Filters"
            onAction={() => {
              setSearchTerm("");
              setLocation("");
              setPracticeArea("");
              setJurisdiction("");
              setLanguage("");
              setMinExp("");
              setMaxFee("");
              setVerifiedOnly(false);
              void fetchLawyers();
            }}
          />
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
              gap: "20px",
            }}
          >
            {lawyers.map((lawyer) => {
              const isVer = lawyer.verification_status === "VERIFIED";
              return (
                <div
                  key={lawyer.id}
                  style={{
                    background: "var(--surface-card)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                    padding: "24px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    gap: "16px",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                      <div>
                        <h3 style={{ fontSize: "17px", fontWeight: 700, color: "var(--text-primary)" }}>
                          {lawyer.full_name}
                        </h3>
                        <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "2px" }}>
                          📍 {lawyer.location || "India"} • {lawyer.experience_years ? `${lawyer.experience_years}+ Yrs at Bar` : "Advocate"}
                        </div>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "6px" }}>
                        <StatusBadge
                          status={isVer ? "VERIFIED" : "PENDING"}
                          label={isVer ? "Verified Bar" : "Enrolled"}
                        />
                        {lawyer.is_online ? (
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "5px",
                              fontSize: "11px",
                              fontWeight: 700,
                              color: "#10b981",
                              backgroundColor: "rgba(16, 185, 129, 0.15)",
                              border: "1px solid rgba(16, 185, 129, 0.35)",
                              padding: "2px 8px",
                              borderRadius: "12px",
                            }}
                          >
                            <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#10b981" }}></span>
                            ONLINE NOW
                          </span>
                        ) : (
                          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>⚪ Offline</span>
                        )}
                      </div>
                    </div>

                    <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: 1.5, marginBottom: "14px" }}>
                      {lawyer.bio ? lawyer.bio.slice(0, 140) + (lawyer.bio.length > 140 ? "..." : "") : "Specialized legal practitioner representing clients in commercial and civil matters."}
                    </p>

                    {/* Practice Areas Badges */}
                    {lawyer.practice_areas && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                        {(Array.isArray(lawyer.practice_areas) ? lawyer.practice_areas : [lawyer.practice_areas]).map((pa, idx) => (
                          <span
                            key={idx}
                            style={{
                              fontSize: "11px",
                              padding: "2px 8px",
                              borderRadius: "4px",
                              background: "rgba(79, 91, 247, 0.12)",
                              color: "#8d98ff",
                              border: "1px solid rgba(79, 91, 247, 0.25)",
                            }}
                          >
                            {pa}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Languages Spoken */}
                    {lawyer.languages && (
                      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "6px", marginTop: "10px" }}>
                        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>🗣️ Speaks:</span>
                        {(Array.isArray(lawyer.languages) ? lawyer.languages : [lawyer.languages]).map((lang, idx) => (
                          <span
                            key={idx}
                            style={{
                              fontSize: "11px",
                              padding: "2px 8px",
                              borderRadius: "4px",
                              background: "rgba(16, 185, 129, 0.12)",
                              color: "#34d399",
                              border: "1px solid rgba(16, 185, 129, 0.25)",
                            }}
                          >
                            {lang}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      borderTop: "1px solid var(--border-subtle)",
                      paddingTop: "14px",
                    }}
                  >
                    <div>
                      <span style={{ fontSize: "16px", fontWeight: 700, color: "#fff" }}>
                        ₹{lawyer.consultation_fee || 2500}
                      </span>
                      <span style={{ fontSize: "11px", color: "var(--text-muted)" }}> / 30 min</span>
                    </div>
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      <Link
                        href={`/lawyers/${lawyer.id}`}
                        className="btn btn-secondary"
                        style={{ padding: "7px 12px", fontSize: "12px" }}
                      >
                        Profile
                      </Link>
                      {lawyer.is_online ? (
                        <button
                          onClick={() => {
                            if (!user) {
                              setAuthPromptLawyer(lawyer);
                              return;
                            }
                            setInstantCallLawyer(lawyer);
                            setInstantError("");
                          }}
                          className="btn btn-primary"
                          style={{
                            padding: "7px 14px",
                            fontSize: "12px",
                            fontWeight: 700,
                            background: "linear-gradient(135deg, #10b981, #059669)",
                            border: "none",
                            boxShadow: "0 2px 10px rgba(16, 185, 129, 0.35)",
                            cursor: "pointer",
                          }}
                        >
                          ⚡ Instant Video Call
                        </button>
                      ) : (
                        <button
                          onClick={() => {
                            if (!user) {
                              setAuthPromptLawyer(lawyer);
                              return;
                            }
                            setBookingLawyer(lawyer);
                            setBookingError("");
                            setBookingSuccess("");
                          }}
                          className="btn btn-primary"
                          style={{ padding: "7px 14px", fontSize: "12px" }}
                        >
                          Book Session →
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Instant Video Call & Simulated Test Payment Modal */}
        {instantCallLawyer && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.85)",
              backdropFilter: "blur(10px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
              padding: "20px",
            }}
            onClick={() => setInstantCallLawyer(null)}
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
                color: "#fff",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "18px" }}>
                <div>
                  <div style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "11px", fontWeight: 700, color: "#10b981", textTransform: "uppercase", marginBottom: "4px" }}>
                    <span>●</span> Instant Counsel Video Session
                  </div>
                  <h2 style={{ fontSize: "20px", fontWeight: 700, color: "#fff", margin: 0 }}>
                    Connect with {instantCallLawyer.full_name}
                  </h2>
                </div>
                <button
                  onClick={() => setInstantCallLawyer(null)}
                  style={{ color: "var(--text-muted)", fontSize: "20px", background: "none", border: "none", cursor: "pointer" }}
                >
                  ✕
                </button>
              </div>

              {/* Session Details Card */}
              <div
                style={{
                  background: "#1a1e2e",
                  border: "1px solid #282f44",
                  borderRadius: "8px",
                  padding: "16px",
                  marginBottom: "18px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
                  <span style={{ color: "#94a3b8" }}>Advocate Status:</span>
                  <span style={{ color: "#10b981", fontWeight: 700 }}>🟢 Present & Online Now</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
                  <span style={{ color: "#94a3b8" }}>Scheduled Start:</span>
                  <span style={{ fontWeight: 600 }}>Immediately ({istClock ? istClock.split("•")[1]?.trim() : "Current Indian Time"})</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
                  <span style={{ color: "#94a3b8" }}>Session Duration:</span>
                  <span>30 Minutes Video Room</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", borderTop: "1px solid #282f44", paddingTop: "8px" }}>
                  <span style={{ color: "#94a3b8" }}>Consultation Fee:</span>
                  <span style={{ fontSize: "18px", fontWeight: 700, color: "#60a5fa" }}>₹{instantCallLawyer.consultation_fee || 2500}</span>
                </div>
              </div>

              {/* Temporary Payment Box */}
              <div
                style={{
                  padding: "14px 16px",
                  borderRadius: "8px",
                  background: "rgba(16, 185, 129, 0.08)",
                  border: "1px solid rgba(16, 185, 129, 0.25)",
                  marginBottom: "20px",
                  fontSize: "12px",
                  color: "#a7f3d0",
                  lineHeight: 1.5,
                }}
              >
                <strong style={{ display: "block", marginBottom: "4px", color: "#34d399" }}>💳 Simulated Test Payment Gateway:</strong>
                This is a temporary test transaction. No real credit card charge will occur. Clicking below authoritatively marks the session as paid and initiates the video consultation with permission of both parties.
              </div>

              {instantError && (
                <div style={{ padding: "12px", borderRadius: "6px", background: "rgba(239, 68, 68, 0.15)", color: "#ef4444", fontSize: "13px", marginBottom: "16px" }}>
                  {instantError}
                </div>
              )}

              <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                <button
                  type="button"
                  onClick={() => setInstantCallLawyer(null)}
                  className="btn btn-secondary"
                  disabled={instantSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmInstantCall}
                  disabled={instantSubmitting}
                  className="btn btn-primary"
                  style={{
                    padding: "10px 22px",
                    background: "linear-gradient(135deg, #10b981, #059669)",
                    border: "none",
                    fontWeight: 700,
                    fontSize: "14px",
                    boxShadow: "0 4px 14px rgba(16, 185, 129, 0.4)",
                    cursor: "pointer",
                  }}
                >
                  {instantSubmitting ? "Starting Video Call..." : "Confirm Test Payment & Join Call 🎥"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Booking Modal */}
        {bookingLawyer && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.8)",
              backdropFilter: "blur(10px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
              padding: "20px",
            }}
            onClick={() => setBookingLawyer(null)}
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
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
                <div>
                  <h2 style={{ fontSize: "20px", fontWeight: 700, color: "#fff" }}>
                    Schedule Consultation: {bookingLawyer.full_name}
                  </h2>
                  <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginTop: "2px" }}>
                    Fee: ₹{bookingLawyer.consultation_fee || 2500} for 30 minutes video consultation.
                  </p>
                </div>
                <button
                  onClick={() => setBookingLawyer(null)}
                  style={{ color: "var(--text-muted)", fontSize: "18px" }}
                >
                  ✕
                </button>
              </div>

              {bookingSuccess && bookedConsultationId ? (
                <div style={{ textAlign: "center", padding: "12px 0" }}>
                  <div
                    style={{
                      width: "56px",
                      height: "56px",
                      borderRadius: "50%",
                      backgroundColor: "rgba(16, 185, 129, 0.15)",
                      color: "#10b981",
                      fontSize: "28px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      margin: "0 auto 16px",
                    }}
                  >
                    ✓
                  </div>
                  <h3 style={{ fontSize: "18px", fontWeight: 700, color: "#fff", marginBottom: "8px" }}>
                    Appointment Confirmed!
                  </h3>
                  <p style={{ color: "var(--text-secondary)", fontSize: "14px", lineHeight: 1.5, marginBottom: "20px" }}>
                    {bookingSuccess}
                  </p>
                  <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    <a
                      href={`/consultations/${bookedConsultationId}/room`}
                      className="btn btn-primary"
                      style={{
                        padding: "12px",
                        fontSize: "14px",
                        textAlign: "center",
                        textDecoration: "none",
                        fontWeight: 600,
                      }}
                    >
                      Enter Video Consultation Room 🎥
                    </a>
                    <button
                      type="button"
                      onClick={() => {
                        setBookingLawyer(null);
                        setBookingSuccess("");
                        setBookedConsultationId(null);
                      }}
                      className="btn btn-secondary"
                      style={{ padding: "10px" }}
                    >
                      Done & Return to Directory
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {bookingError && (
                    <div style={{ padding: "12px", borderRadius: "6px", background: "rgba(239, 68, 68, 0.15)", color: "#ef4444", fontSize: "13px", marginBottom: "16px" }}>
                      {bookingError}
                    </div>
                  )}

                  <form onSubmit={handleBookConsultation}>
                    <div className="input-group">
                      <label className="input-label">Consultation Date</label>
                      <input
                        type="date"
                        value={selectedDate}
                        min={new Date().toISOString().split("T")[0]}
                        onChange={(e) => setSelectedDate(e.target.value)}
                        required
                        className="input-field"
                      />
                    </div>

                    <div className="input-group">
                      <label className="input-label">Available Time Slots</label>
                      {fetchingSlots ? (
                        <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Synchronizing advocate calendar...</div>
                      ) : slots.length === 0 ? (
                        <div style={{ fontSize: "12px", color: "#f59e0b", padding: "10px", background: "rgba(245, 158, 11, 0.08)", borderRadius: "6px" }}>
                          No available slots on this date. Please select another date.
                        </div>
                      ) : (
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px", maxHeight: "150px", overflowY: "auto" }}>
                          {slots.map((slot, idx) => (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => setSelectedSlot(slot)}
                              style={{
                                padding: "8px",
                                borderRadius: "6px",
                                fontSize: "12px",
                                background: selectedSlot?.start_time === slot.start_time ? "var(--accent-primary)" : "var(--surface-subtle)",
                                color: selectedSlot?.start_time === slot.start_time ? "#fff" : "var(--text-primary)",
                                border: "1px solid var(--border-subtle)",
                                fontWeight: 500,
                              }}
                            >
                              {new Date(slot.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "24px" }}>
                      <button
                        type="button"
                        onClick={() => setBookingLawyer(null)}
                        className="btn btn-secondary"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={bookingSubmitting || (!selectedSlot && slots.length > 0)}
                        className="btn btn-primary"
                      >
                        {bookingSubmitting ? "Reserving Slot..." : "Confirm & Reserve Slot →"}
                      </button>
                    </div>
                  </form>
                </>
              )}
            </div>
          </div>
        )}
        {/* Unauthenticated User Prompt Modal */}
        {authPromptLawyer && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.85)",
              backdropFilter: "blur(10px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1100,
              padding: "20px",
            }}
          >
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-lg)",
                padding: "36px 32px",
                maxWidth: "460px",
                width: "100%",
                textAlign: "center",
                boxShadow: "0 24px 48px rgba(0,0,0,0.7)",
              }}
            >
              <div style={{ fontSize: "42px", marginBottom: "14px" }}>⚖</div>
              <h3 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px", color: "var(--text-primary)" }}>
                Sign In to Consult Counsel
              </h3>
              <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "24px", lineHeight: "1.5" }}>
                To schedule or start a video consultation with <strong>{authPromptLawyer.full_name}</strong>, please log in or open a free legal account.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <button
                  type="button"
                  id="quick-demo-client-modal-btn"
                  onClick={handleQuickClientLogin}
                  disabled={quickLoginLoading}
                  className="btn btn-primary"
                  style={{
                    padding: "12px",
                    fontSize: "14px",
                    fontWeight: 600,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "8px",
                    background: "linear-gradient(135deg, #3b82f6, #2563eb)",
                    border: "none",
                  }}
                >
                  ⚡ {quickLoginLoading ? "Logging in..." : "1-Click Client Login (Vikram Sharma)"}
                </button>
                <Link
                  href={`/login?redirect=/lawyers`}
                  className="btn btn-secondary"
                  style={{ padding: "12px", fontSize: "14px", fontWeight: 600 }}
                >
                  Log In with Email
                </Link>
                <Link
                  href={`/register?redirect=/lawyers`}
                  style={{ color: "var(--text-muted)", fontSize: "13px", marginTop: "4px" }}
                >
                  Create New Client Account
                </Link>
                <button
                  type="button"
                  onClick={() => setAuthPromptLawyer(null)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--text-muted)",
                    fontSize: "13px",
                    cursor: "pointer",
                    marginTop: "6px",
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
