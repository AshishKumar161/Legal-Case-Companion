"use client";

import { use, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import { LawyerPublicItem, SlotItem, LawyerAvailabilityItem, ConsultationItem } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { PaymentCheckoutModal } from "@/components/Payment/PaymentCheckoutModal";

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function LawyerPublicProfilePage({
  params,
}: {
  params: Promise<{ lawyerId: string }>;
}) {
  const unwrappedParams = use(params);
  const { lawyerId } = unwrappedParams;
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [lawyer, setLawyer] = useState<LawyerPublicItem | null>(null);
  const [availabilities, setAvailabilities] = useState<LawyerAvailabilityItem[]>([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Slot Selection state
  const [selectedDate, setSelectedDate] = useState<string>(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split("T")[0];
  });
  const [slots, setSlots] = useState<SlotItem[]>([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<SlotItem | null>(null);

  // Booking state
  const [bookingSubmitting, setBookingSubmitting] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookedConsultation, setBookedConsultation] = useState<ConsultationItem | null>(null);
  const [showPaymentModal, setShowPaymentModal] = useState(false);

  // 1. Fetch lawyer public profile & availability rules
  const fetchLawyerDetails = useCallback(async () => {
    try {
      setFetching(true);
      setError(null);
      const [lawyerRes, availRes] = await Promise.all([
        apiClient.get(`/api/v1/lawyers/${lawyerId}`, { requireAuth: false }),
        apiClient.get(`/api/v1/lawyers/${lawyerId}/availability`, { requireAuth: false }).catch(() => []),
      ]);
      setLawyer(lawyerRes);
      setAvailabilities(Array.isArray(availRes) ? availRes : []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Lawyer profile not found";
      setError(msg);
    } finally {
      setFetching(false);
    }
  }, [lawyerId]);

  useEffect(() => {
    void fetchLawyerDetails();
  }, [fetchLawyerDetails]);

  // 2. Fetch available slots for selected date
  const fetchSlots = useCallback(async () => {
    if (!selectedDate || !lawyerId) return;
    try {
      setLoadingSlots(true);
      setSelectedSlot(null);
      const res = await apiClient.get(
        `/api/v1/lawyers/${lawyerId}/slots?date=${selectedDate}&duration_minutes=30`,
        { requireAuth: false }
      );
      setSlots(Array.isArray(res) ? res : []);
    } catch (err) {
      console.error("Failed to fetch slots", err);
      setSlots([]);
    } finally {
      setLoadingSlots(false);
    }
  }, [lawyerId, selectedDate]);

  useEffect(() => {
    void fetchSlots();
  }, [fetchSlots]);

  // 3. Handle Booking Submission
  const handleBookSession = async () => {
    if (!selectedSlot) return;

    if (!user) {
      router.push(`/login?redirect=/lawyers/${lawyerId}`);
      return;
    }

    if (user.role === "LAWYER" && user.id === lawyerId) {
      setBookingError("Counsel cannot book a consultation with themselves.");
      return;
    }

    setBookingSubmitting(true);
    setBookingError(null);

    try {
      const res: any = await apiClient.post("/api/v1/consultations", {
        lawyer_id: lawyer?.id || lawyerId,
        scheduled_at: selectedSlot.start_time,
        duration_minutes: 30,
      });

      setBookedConsultation(res);
      setShowPaymentModal(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to book consultation";
      setBookingError(msg);
    } finally {
      setBookingSubmitting(false);
    }
  };

  if (fetching || authLoading) {
    return (
      <div style={{ padding: "60px 0" }}>
        <div className="container">
          <LoadingSkeleton type="card" count={2} />
        </div>
      </div>
    );
  }

  if (error || !lawyer) {
    return (
      <div style={{ padding: "80px 0", textAlign: "center" }}>
        <div className="container">
          <div style={{ fontSize: "40px", marginBottom: "16px" }}>⚖️</div>
          <h2 style={{ color: "var(--text-primary)", fontSize: "24px", fontWeight: 700 }}>
            {error || "Advocate Profile Not Found"}
          </h2>
          <p style={{ color: "var(--text-secondary)", marginTop: "8px", marginBottom: "24px" }}>
            The requested advocate profile is either inactive or does not exist.
          </p>
          <Link href="/lawyers" className="btn btn-primary">
            ← Return to Advocate Directory
          </Link>
        </div>
      </div>
    );
  }

  const isVerified = lawyer.verification_status === "VERIFIED";

  return (
    <div style={{ padding: "32px 0 80px" }}>
      <div className="container">
        {/* Breadcrumbs */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--text-muted)", marginBottom: "24px" }}>
          <Link href="/lawyers" style={{ color: "var(--text-secondary)" }}>Advocate Directory</Link>
          <span>/</span>
          <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{lawyer.full_name}</span>
        </div>

        {/* Two Column Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "32px", alignItems: "start" }}>
          {/* Left: Advocate Credentials & Standing */}
          <div>
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "32px",
                marginBottom: "24px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                    <h1 style={{ fontSize: "28px", fontWeight: 700, color: "var(--text-primary)" }}>
                      {lawyer.full_name}
                    </h1>
                    <StatusBadge status={isVerified ? "VERIFIED" : "PENDING"} label={isVerified ? "Verified Bar Counsel" : "Verification Pending"} />
                  </div>
                  <p style={{ color: "var(--text-secondary)", fontSize: "15px" }}>
                    {lawyer.primary_practice_area || "General Practice Counsel"} • {lawyer.experience_years ? `${lawyer.experience_years} Years at Bar` : "Senior Counsel"}
                  </p>
                </div>

                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "24px", fontWeight: 800, color: "var(--accent-secondary)" }}>
                    ₹{lawyer.consultation_fee || 2500}
                  </div>
                  <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>per 30 min session</span>
                </div>
              </div>

              {/* Badges / Jurisdiction */}
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", marginTop: "20px" }}>
                <span style={{ fontSize: "12px", padding: "4px 10px", background: "var(--surface-elevated)", border: "1px solid var(--border-subtle)", borderRadius: "6px", color: "var(--text-primary)" }}>
                  📍 {lawyer.location || "National Jurisdiction"}
                </span>

                {lawyer.languages && (
                  <span style={{ fontSize: "12px", padding: "4px 10px", background: "rgba(16, 185, 129, 0.1)", border: "1px solid rgba(16, 185, 129, 0.25)", borderRadius: "6px", color: "#34d399" }}>
                    🗣️ {(Array.isArray(lawyer.languages) ? lawyer.languages : [lawyer.languages]).join(", ")}
                  </span>
                )}
              </div>

              {/* Bio */}
              <div style={{ marginTop: "24px", borderTop: "1px solid var(--border-subtle)", paddingTop: "20px" }}>
                <h3 style={{ fontSize: "15px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
                  Professional Bio & Chambers Summary
                </h3>
                <p style={{ fontSize: "14px", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                  {lawyer.bio || "No professional biography on file. Retain advocate for advisory, contract review, or dispute representation."}
                </p>
              </div>

              {/* Practice Areas */}
              {lawyer.practice_areas && lawyer.practice_areas.length > 0 && (
                <div style={{ marginTop: "20px", borderTop: "1px solid var(--border-subtle)", paddingTop: "20px" }}>
                  <h3 style={{ fontSize: "15px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "10px" }}>
                    Practice Areas & Legal Specializations
                  </h3>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {lawyer.practice_areas.map((pa, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: "12px",
                          padding: "4px 10px",
                          borderRadius: "4px",
                          background: "var(--surface-elevated)",
                          color: "var(--text-secondary)",
                          border: "1px solid var(--border-subtle)",
                        }}
                      >
                        {pa}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Weekly Availability Rules Card */}
            <div
              style={{
                background: "var(--surface-card)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                padding: "24px",
              }}
            >
              <h3 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "14px" }}>
                Weekly Consultation Chambers Schedule
              </h3>
              {availabilities.length === 0 ? (
                <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>
                  Advocate maintains custom appointment scheduling. Check available calendar dates on the right.
                </p>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "10px" }}>
                  {availabilities.map((rule) => (
                    <div
                      key={rule.id}
                      style={{
                        padding: "10px 14px",
                        background: "var(--surface-elevated)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "6px",
                      }}
                    >
                      <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-primary)" }}>
                        {DAY_NAMES[rule.day_of_week] || `Day ${rule.day_of_week}`}
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--accent-secondary)", marginTop: "2px" }}>
                        {rule.start_time.slice(0, 5)} - {rule.end_time.slice(0, 5)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right: Interactive Booking & Slot Picker */}
          <div
            style={{
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              padding: "28px",
              position: "sticky",
              top: "84px",
              boxShadow: "var(--shadow-md)",
            }}
          >
            <h2 style={{ fontSize: "18px", fontWeight: 700, color: "var(--text-primary)", marginBottom: "4px" }}>
              Schedule Video Consultation
            </h2>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", marginBottom: "20px" }}>
              Select an available appointment slot. All sessions are conducted via secure in-app WebRTC video.
            </p>

            {bookingError && (
              <div
                style={{
                  padding: "10px 14px",
                  borderRadius: "6px",
                  background: "rgba(239, 68, 68, 0.12)",
                  color: "#ef4444",
                  fontSize: "13px",
                  marginBottom: "16px",
                  border: "1px solid rgba(239, 68, 68, 0.25)",
                }}
              >
                {bookingError}
              </div>
            )}

            {/* Date Selection */}
            <div className="input-group">
              <label className="input-label">Select Consultation Date</label>
              <input
                type="date"
                className="input-field"
                min={new Date().toISOString().split("T")[0]}
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
              />
            </div>

            {/* Slots Matrix */}
            <div style={{ marginTop: "16px", marginBottom: "24px" }}>
              <label className="input-label" style={{ marginBottom: "8px", display: "block" }}>
                Available 30-Minute Slots ({slots.length})
              </label>

              {loadingSlots ? (
                <div style={{ padding: "20px 0", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                  Synchronizing counsel calendar...
                </div>
              ) : slots.length === 0 ? (
                <div style={{ padding: "16px", background: "var(--surface-elevated)", borderRadius: "6px", textAlign: "center", fontSize: "13px", color: "var(--text-muted)" }}>
                  No open consultation slots on this date. Please select another date.
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", maxHeight: "200px", overflowY: "auto" }}>
                  {slots.map((slot, idx) => {
                    const isSelected = selectedSlot?.start_time === slot.start_time;
                    const startTimeStr = new Date(slot.start_time).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    });
                    const endTimeStr = new Date(slot.end_time).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    });

                    return (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setSelectedSlot(slot)}
                        style={{
                          padding: "10px 8px",
                          borderRadius: "6px",
                          background: isSelected ? "var(--accent-primary)" : "var(--surface-elevated)",
                          color: isSelected ? "#fff" : "var(--text-primary)",
                          border: isSelected ? "1px solid var(--accent-secondary)" : "1px solid var(--border-subtle)",
                          fontSize: "12px",
                          fontWeight: isSelected ? 700 : 500,
                          cursor: "pointer",
                          transition: "all 0.15s",
                        }}
                      >
                        {startTimeStr} - {endTimeStr}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Booking Action Button */}
            <button
              onClick={handleBookSession}
              disabled={bookingSubmitting || !selectedSlot}
              className={`btn btn-primary ${bookingSubmitting || !selectedSlot ? "btn-disabled" : ""}`}
              style={{ width: "100%", justifyContent: "center", padding: "12px", fontSize: "14px" }}
            >
              {bookingSubmitting
                ? "Securing Appointment..."
                : selectedSlot
                ? `Confirm Booking (₹${lawyer.consultation_fee || 2500}) →`
                : "Select an Available Slot"}
            </button>

            <div style={{ marginTop: "16px", textAlign: "center", fontSize: "12px", color: "var(--text-muted)" }}>
              🔒 Protected by 256-bit encryption & Bar Council compliance
            </div>
          </div>
        </div>

        {/* Payment Checkout Modal */}
        {showPaymentModal && bookedConsultation && (
          <PaymentCheckoutModal
            consultation={bookedConsultation}
            onClose={() => {
              setShowPaymentModal(false);
              router.push("/consultations");
            }}
            onPaymentSuccess={() => {
              setShowPaymentModal(false);
              router.push(`/consultations/${bookedConsultation.id}/room`);
            }}
          />
        )}
      </div>
    </div>
  );
}
