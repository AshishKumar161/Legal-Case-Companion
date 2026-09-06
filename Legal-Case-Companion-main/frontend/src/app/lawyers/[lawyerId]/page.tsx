"use client";

import React, { use, useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/providers/AuthProvider";
import { apiClient } from "@/api/client";
import {
  LawyerPublicItem,
  SlotItem,
  LawyerAvailabilityItem,
  ConsultationItem,
  ConsultationPricingResponse,
} from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { PaymentCheckoutModal } from "@/components/Payment/PaymentCheckoutModal";
import { trackFunnelEvent } from "@/lib/analytics";

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
  const [pricing, setPricing] = useState<ConsultationPricingResponse | null>(null);
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

  // Booking Flow Steps (Section 11)
  // "SELECT_SLOT" -> "REVIEW_PRICE" -> "PAYMENT" -> "CONFIRMED"
  const [bookingStep, setBookingStep] = useState<"SELECT_SLOT" | "REVIEW_PRICE" | "CONFIRMED">("SELECT_SLOT");
  const [bookingSubmitting, setBookingSubmitting] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookedConsultation, setBookedConsultation] = useState<ConsultationItem | null>(null);
  const [showPaymentModal, setShowPaymentModal] = useState(false);

  // 1. Fetch lawyer profile, availability schedule, and authoritative pricing preview
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

      // Authoritative pricing preview directly from backend pricing system (Section 8)
      const targetId = lawyerRes?.id || lawyerId;
      try {
        const pricingRes = await apiClient.get(
          `/api/v1/consultations/pricing-preview?lawyer_id=${targetId}&duration_minutes=30`,
          { requireAuth: false }
        );
        setPricing(pricingRes);
      } catch {
        // Safe fallback if pricing preview is not reachable
        setPricing(null);
      }

      trackFunnelEvent("profile_opened", { lawyer_id: lawyerId });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Lawyer profile not found.";
      setError(msg);
    } finally {
      setFetching(false);
    }
  }, [lawyerId]);

  useEffect(() => {
    void fetchLawyerDetails();
  }, [fetchLawyerDetails]);

  // 2. Fetch available slots for selected date (in IST)
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
    } catch {
      setSlots([]);
    } finally {
      setLoadingSlots(false);
    }
  }, [lawyerId, selectedDate]);

  useEffect(() => {
    void fetchSlots();
  }, [fetchSlots]);

  // 3. Initiate Consultation Booking
  const handleProceedToReview = () => {
    if (!selectedSlot) return;

    if (!user) {
      router.push(`/login?redirect=/lawyers/${lawyerId}`);
      return;
    }

    if (user.role === "LAWYER" && user.id === lawyerId) {
      setBookingError("Counsel cannot book a consultation with themselves.");
      return;
    }

    setBookingError(null);
    setBookingStep("REVIEW_PRICE");
    trackFunnelEvent("checkout_started", { lawyer_id: lawyerId });
  };

  const handleConfirmAndPay = async () => {
    if (!selectedSlot || !lawyer) return;

    setBookingSubmitting(true);
    setBookingError(null);

    try {
      const res: any = await apiClient.post("/api/v1/consultations", {
        lawyer_id: lawyer.id || lawyerId,
        scheduled_at: selectedSlot.start_time,
        duration_minutes: 30,
      });

      setBookedConsultation(res);
      setShowPaymentModal(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to book consultation session.";
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
  const feeAmount = pricing?.fee_amount ?? lawyer.consultation_fee ?? 2500;
  const gstAmount = pricing?.gst_amount ?? Math.round(feeAmount * 0.18 * 100) / 100;
  const totalPayable = pricing?.total_amount ?? Math.round((feeAmount + gstAmount) * 100) / 100;

  return (
    <div style={{ padding: "32px 16px 80px" }}>
      <div className="container" style={{ maxWidth: "1140px", margin: "0 auto" }}>
        {/* Breadcrumb Navigation */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--text-muted)", marginBottom: "24px" }}>
          <Link href="/lawyers" style={{ color: "var(--text-secondary)" }}>
            Advocate Directory
          </Link>
          <span>/</span>
          <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>Adv. {lawyer.full_name}</span>
        </div>

        {/* Two-Column Responsive Layout */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "32px", alignItems: "start" }}>
          {/* Left Column: Advocate Credentials, Standing, and Transparent Pricing */}
          <div>
            {/* Top Identity Card (Section 7) */}
            <div
              style={{
                background: "var(--surface-card, #0e121a)",
                border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                borderRadius: "var(--radius-md, 12px)",
                padding: "28px",
                marginBottom: "24px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px", flexWrap: "wrap" }}>
                    <h1 style={{ fontSize: "26px", fontWeight: 800, color: "#ffffff", margin: 0 }}>
                      Adv. {lawyer.full_name}
                    </h1>
                    {isVerified ? (
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "#34d399",
                          background: "rgba(16, 185, 129, 0.12)",
                          border: "1px solid rgba(16, 185, 129, 0.25)",
                          padding: "3px 8px",
                          borderRadius: "4px",
                        }}
                      >
                        ✓ Verified Bar Counsel
                      </span>
                    ) : (
                      <StatusBadge status="PENDING" label="Verification Pending" />
                    )}
                  </div>
                  <p style={{ color: "var(--text-secondary, #94a3b8)", fontSize: "14px", margin: 0 }}>
                    {lawyer.primary_practice_area || "High Court & District Counsel"} • {lawyer.experience_years ? `${lawyer.experience_years} Years at Bar` : "Enrolled Advocate"}
                  </p>
                </div>

                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "24px", fontWeight: 800, color: "#818cf8" }}>
                    ₹{feeAmount.toLocaleString("en-IN")}
                  </div>
                  <span style={{ fontSize: "12px", color: "#94a3b8" }}>consultation fee</span>
                </div>
              </div>

              {/* Location & Languages */}
              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "18px" }}>
                <span style={{ fontSize: "12px", padding: "4px 10px", background: "rgba(255, 255, 255, 0.04)", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "6px", color: "#ffffff" }}>
                  📍 {lawyer.location || "National Jurisdiction"}
                </span>

                {lawyer.languages && (
                  <span style={{ fontSize: "12px", padding: "4px 10px", background: "rgba(16, 185, 129, 0.08)", border: "1px solid rgba(16, 185, 129, 0.2)", borderRadius: "6px", color: "#34d399" }}>
                    🗣️ {(Array.isArray(lawyer.languages) ? lawyer.languages : [lawyer.languages]).join(", ")}
                  </span>
                )}
              </div>

              {/* Professional Bio */}
              <div style={{ marginTop: "24px", borderTop: "1px solid rgba(255, 255, 255, 0.06)", paddingTop: "20px" }}>
                <h3 style={{ fontSize: "15px", fontWeight: 700, color: "#ffffff", marginBottom: "8px" }}>
                  Professional Bio & Chambers Profile
                </h3>
                <p style={{ fontSize: "14px", color: "#cbd5e1", lineHeight: 1.6, margin: 0 }}>
                  {lawyer.bio || "Enrolled Advocate available for legal advisory, contract drafting, legal notice responses, and court representation."}
                </p>
              </div>

              {/* Practice Areas */}
              {lawyer.practice_areas && lawyer.practice_areas.length > 0 && (
                <div style={{ marginTop: "20px", borderTop: "1px solid rgba(255, 255, 255, 0.06)", paddingTop: "18px" }}>
                  <h3 style={{ fontSize: "14px", fontWeight: 700, color: "#ffffff", marginBottom: "10px" }}>
                    Specializations & Practice Areas
                  </h3>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {lawyer.practice_areas.map((pa, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: "12px",
                          padding: "4px 10px",
                          borderRadius: "4px",
                          background: "rgba(99, 102, 241, 0.1)",
                          color: "#cbd5e1",
                          border: "1px solid rgba(99, 102, 241, 0.25)",
                        }}
                      >
                        {pa}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Transparent Pricing Card (Section 8) */}
            <div
              style={{
                background: "var(--surface-card, #0e121a)",
                border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                borderRadius: "var(--radius-md, 12px)",
                padding: "24px",
                marginBottom: "24px",
              }}
            >
              <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#ffffff", marginBottom: "14px", display: "flex", alignItems: "center", gap: "8px" }}>
                <span>💳</span> Transparent Fee Breakdown
              </h3>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", color: "#94a3b8" }}>
                  <span>Advocate Consultation (30 min)</span>
                  <span style={{ color: "#ffffff", fontWeight: 600 }}>₹{feeAmount.toFixed(2)}</span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", color: "#94a3b8" }}>
                  <span>Statutory 18% GST (9% CGST + 9% SGST)</span>
                  <span style={{ color: "#ffffff", fontWeight: 600 }}>₹{gstAmount.toFixed(2)}</span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", color: "#94a3b8" }}>
                  <span>Platform Fee</span>
                  <span style={{ color: "#34d399", fontWeight: 600 }}>₹0.00 (Free)</span>
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    paddingTop: "12px",
                    marginTop: "6px",
                    borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                    fontSize: "16px",
                    fontWeight: 700,
                  }}
                >
                  <span style={{ color: "#ffffff" }}>Total Payable</span>
                  <span style={{ color: "#818cf8" }}>₹{totalPayable.toFixed(2)}</span>
                </div>
              </div>

              <div style={{ marginTop: "12px", fontSize: "12px", color: "#64748b" }}>
                Official invoice with GST break-up issued immediately upon confirmed payment.
              </div>
            </div>

            {/* Weekly Chambers Schedule */}
            {availabilities.length > 0 && (
              <div
                style={{
                  background: "var(--surface-card, #0e121a)",
                  border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
                  borderRadius: "var(--radius-md, 12px)",
                  padding: "24px",
                }}
              >
                <h3 style={{ fontSize: "15px", fontWeight: 700, color: "#ffffff", marginBottom: "12px" }}>
                  Weekly Chambers Schedule
                </h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "10px" }}>
                  {availabilities.map((rule) => (
                    <div
                      key={rule.id}
                      style={{
                        padding: "10px 12px",
                        background: "rgba(255, 255, 255, 0.03)",
                        border: "1px solid rgba(255, 255, 255, 0.08)",
                        borderRadius: "8px",
                      }}
                    >
                      <div style={{ fontSize: "12px", fontWeight: 700, color: "#ffffff" }}>
                        {DAY_NAMES[rule.day_of_week] || `Day ${rule.day_of_week}`}
                      </div>
                      <div style={{ fontSize: "12px", color: "#818cf8", marginTop: "2px" }}>
                        {rule.start_time.slice(0, 5)} - {rule.end_time.slice(0, 5)} IST
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Interactive Slot Picker & Transparent Booking Flow */}
          <div
            style={{
              background: "var(--surface-card, #0e121a)",
              border: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))",
              borderRadius: "var(--radius-md, 12px)",
              padding: "28px",
              boxShadow: "0 10px 30px rgba(0, 0, 0, 0.4)",
            }}
          >
            {/* STAGE 1: SELECT SLOT */}
            {bookingStep === "SELECT_SLOT" && (
              <div>
                <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#ffffff", margin: "0 0 6px 0" }}>
                  Schedule Video Consultation
                </h2>
                <p style={{ fontSize: "13px", color: "#94a3b8", margin: "0 0 20px 0" }}>
                  Choose your preferred date and time. Consultations take place securely in-browser via encrypted WebRTC.
                </p>

                {bookingError && (
                  <div
                    style={{
                      padding: "12px 14px",
                      borderRadius: "8px",
                      background: "rgba(239, 68, 68, 0.12)",
                      color: "#f87171",
                      fontSize: "13px",
                      marginBottom: "16px",
                      border: "1px solid rgba(239, 68, 68, 0.25)",
                    }}
                  >
                    {bookingError}
                  </div>
                )}

                {/* Date Picker */}
                <div style={{ marginBottom: "18px" }}>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#cbd5e1", display: "block", marginBottom: "6px" }}>
                    Select Consultation Date (IST)
                  </label>
                  <input
                    type="date"
                    min={new Date().toISOString().split("T")[0]}
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "10px 14px",
                      background: "rgba(10, 13, 20, 0.9)",
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      borderRadius: "8px",
                      color: "#ffffff",
                      fontSize: "14px",
                      outline: "none",
                    }}
                  />
                </div>

                {/* Slots Grid */}
                <div style={{ marginBottom: "24px" }}>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#cbd5e1", display: "block", marginBottom: "8px" }}>
                    Available 30-Minute Slots ({slots.length})
                  </label>

                  {loadingSlots ? (
                    <div style={{ padding: "24px 0", textAlign: "center", color: "#94a3b8", fontSize: "13px" }}>
                      Checking counsel calendar...
                    </div>
                  ) : slots.length === 0 ? (
                    <div style={{ padding: "20px", background: "rgba(255, 255, 255, 0.03)", borderRadius: "8px", textAlign: "center", fontSize: "13px", color: "#94a3b8" }}>
                      No available consultation slots on this date. Please pick another date.
                    </div>
                  ) : (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", maxHeight: "220px", overflowY: "auto" }}>
                      {slots.map((slot, idx) => {
                        const isSelected = selectedSlot?.start_time === slot.start_time;
                        const startTime = new Date(slot.start_time).toLocaleTimeString("en-IN", {
                          timeZone: "Asia/Kolkata",
                          hour: "2-digit",
                          minute: "2-digit",
                        });
                        const endTime = new Date(slot.end_time).toLocaleTimeString("en-IN", {
                          timeZone: "Asia/Kolkata",
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
                              background: isSelected ? "var(--accent-primary, #6366f1)" : "rgba(255, 255, 255, 0.04)",
                              color: isSelected ? "#ffffff" : "#cbd5e1",
                              border: isSelected ? "1px solid #818cf8" : "1px solid rgba(255, 255, 255, 0.08)",
                              fontSize: "12px",
                              fontWeight: isSelected ? 700 : 500,
                              cursor: "pointer",
                              transition: "all 0.15s ease",
                            }}
                          >
                            {startTime} - {endTime} IST
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  onClick={handleProceedToReview}
                  disabled={!selectedSlot}
                  className="btn btn-primary"
                  style={{ width: "100%", padding: "12px", fontSize: "14px", fontWeight: 700 }}
                >
                  {selectedSlot ? `Continue to Price Review (₹${totalPayable.toFixed(2)}) →` : "Select a time slot"}
                </button>
              </div>
            )}

            {/* STAGE 2: PRE-PAYMENT PRICE REVIEW (Section 12) */}
            {bookingStep === "REVIEW_PRICE" && (
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
                  <button
                    type="button"
                    onClick={() => setBookingStep("SELECT_SLOT")}
                    style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "13px" }}
                  >
                    ← Change Slot
                  </button>
                </div>

                <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#ffffff", margin: "0 0 4px 0" }}>
                  Review Consultation Summary
                </h2>
                <p style={{ fontSize: "13px", color: "#94a3b8", margin: "0 0 18px 0" }}>
                  Verify your session details and complete payment securely.
                </p>

                {bookingError && (
                  <div
                    style={{
                      padding: "12px 14px",
                      borderRadius: "8px",
                      background: "rgba(239, 68, 68, 0.12)",
                      color: "#f87171",
                      fontSize: "13px",
                      marginBottom: "16px",
                      border: "1px solid rgba(239, 68, 68, 0.25)",
                    }}
                  >
                    {bookingError}
                  </div>
                )}

                {/* Booking Summary Box */}
                <div
                  style={{
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: "10px",
                    padding: "16px",
                    marginBottom: "18px",
                    fontSize: "13px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                  }}
                >
                  <div><strong>Advocate:</strong> Adv. {lawyer.full_name}</div>
                  <div><strong>Format:</strong> In-App Video Consultation (30 Minutes)</div>
                  <div>
                    <strong>Date & Time:</strong>{" "}
                    {selectedSlot && (
                      <span>
                        {new Date(selectedSlot.start_time).toLocaleDateString("en-IN", {
                          timeZone: "Asia/Kolkata",
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })}{" "}
                        at{" "}
                        {new Date(selectedSlot.start_time).toLocaleTimeString("en-IN", {
                          timeZone: "Asia/Kolkata",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}{" "}
                        IST
                      </span>
                    )}
                  </div>
                  <div style={{ borderTop: "1px solid rgba(255, 255, 255, 0.06)", paddingTop: "8px" }}>
                    <strong>Fee:</strong> ₹{feeAmount.toFixed(2)} + ₹{gstAmount.toFixed(2)} (18% GST)
                  </div>
                  <div style={{ fontSize: "15px", fontWeight: 700, color: "#818cf8" }}>
                    Total Payable: ₹{totalPayable.toFixed(2)}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleConfirmAndPay}
                  disabled={bookingSubmitting}
                  className="btn btn-primary"
                  style={{ width: "100%", padding: "12px", fontSize: "14px", fontWeight: 700 }}
                >
                  {bookingSubmitting ? "Locking slot & opening gateway..." : `Pay Securely (₹${totalPayable.toFixed(2)}) →`}
                </button>
              </div>
            )}

            {/* STAGE 3: BOOKING CONFIRMED (Section 13) */}
            {bookingStep === "CONFIRMED" && bookedConsultation && (
              <div style={{ textAlign: "center", padding: "10px 0" }}>
                <div style={{ fontSize: "36px", marginBottom: "8px" }}>🎉</div>
                <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#ffffff", margin: "0 0 6px 0" }}>
                  Your consultation is booked
                </h2>
                <p style={{ fontSize: "13px", color: "#94a3b8", margin: "0 0 16px 0" }}>
                  You and Adv. {lawyer.full_name} will receive email reminders prior to the session.
                </p>

                <div
                  style={{
                    background: "rgba(16, 185, 129, 0.08)",
                    border: "1px solid rgba(16, 185, 129, 0.2)",
                    borderRadius: "8px",
                    padding: "12px",
                    marginBottom: "18px",
                    fontSize: "13px",
                    textAlign: "left",
                  }}
                >
                  <div><strong>Advocate:</strong> Adv. {lawyer.full_name}</div>
                  <div><strong>Status:</strong> Confirmed & Paid</div>
                  <div><strong>Scheduled:</strong> {bookedConsultation.scheduled_start || (bookedConsultation as unknown as { scheduled_at?: string }).scheduled_at ? new Date(bookedConsultation.scheduled_start || (bookedConsultation as unknown as { scheduled_at?: string }).scheduled_at!).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) : "Confirmed on calendar"} IST</div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  <Link href="/consultations" className="btn btn-primary" style={{ textAlign: "center" }}>
                    View Consultation Session →
                  </Link>
                  <Link href="/dashboard" className="btn btn-secondary" style={{ textAlign: "center" }}>
                    Return to Dashboard
                  </Link>
                </div>
              </div>
            )}

            <div style={{ marginTop: "16px", textAlign: "center", fontSize: "12px", color: "var(--text-muted, #64748b)" }}>
              🔒 Protected by 256-bit encryption & Bar Council compliance
            </div>
          </div>
        </div>

        {/* Payment Checkout Modal (Section 12 & 14) */}
        {showPaymentModal && bookedConsultation && (
          <PaymentCheckoutModal
            consultation={bookedConsultation}
            onClose={() => {
              setShowPaymentModal(false);
              setBookingStep("REVIEW_PRICE");
            }}
            onPaymentSuccess={() => {
              setShowPaymentModal(false);
              setBookingStep("CONFIRMED");
              trackFunnelEvent("payment_success", { lawyer_id: lawyerId });
              trackFunnelEvent("booking_completed", { lawyer_id: lawyerId });
            }}
          />
        )}
      </div>
    </div>
  );
}
