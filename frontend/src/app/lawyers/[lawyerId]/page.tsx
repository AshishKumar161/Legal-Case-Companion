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
  PublicVerificationBadge,
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

  // Phase 14 BCI Rule 36 Verification Badge & Transparency Modal
  const [badge, setBadge] = useState<PublicVerificationBadge | null>(null);
  const [showBadgeModal, setShowBadgeModal] = useState(false);

  // 1. Fetch lawyer profile, availability schedule, and authoritative pricing preview
  const fetchLawyerDetails = useCallback(async () => {
    try {
      setFetching(true);
      setError(null);

      const [lawyerRes, availRes, badgeRes] = await Promise.all([
        apiClient.get(`/api/v1/lawyers/${lawyerId}`, { requireAuth: false }),
        apiClient.get(`/api/v1/lawyers/${lawyerId}/availability`, { requireAuth: false }).catch(() => []),
        apiClient.get<PublicVerificationBadge>(`/api/v1/verification/badge/${lawyerId}`, { requireAuth: false }).catch(() => null),
      ]);

      setLawyer(lawyerRes);
      setAvailabilities(Array.isArray(availRes) ? availRes : []);
      if (badgeRes) {
        setBadge(badgeRes);
      }

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
    if (!selectedDate) return;

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
    if (!selectedDate || !lawyer) return;

    setBookingSubmitting(true);
    setBookingError(null);

    try {
      const schedDate = new Date(`${selectedDate}T10:00:00+05:30`);
      const res = await apiClient.post<ConsultationItem>("/api/v1/consultations", {
        lawyer_id: lawyer.id || lawyerId,
        scheduled_at: schedDate.toISOString(),
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

  const isVerified = badge?.is_verified ?? (lawyer.verification_status === "VERIFIED");
  const feeAmount = pricing?.fee_amount ?? lawyer.consultation_fee ?? 2500;
  const gstAmount = pricing?.gst_amount ?? null;
  const totalPayable = pricing?.total_amount ?? feeAmount;

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
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "12px",
                padding: "28px",
                marginBottom: "24px",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px", flexWrap: "wrap" }}>
                    <h1 style={{ fontSize: "26px", fontWeight: 800, color: "#0f172a", margin: 0 }}>
                      Adv. {lawyer.full_name}
                    </h1>
                    {isVerified ? (
                      <button
                        type="button"
                        onClick={() => setShowBadgeModal(true)}
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          color: "#059669",
                          background: "#ecfdf5",
                          border: "1px solid #a7f3d0",
                          padding: "4px 10px",
                          borderRadius: "6px",
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "5px",
                        }}
                        title="Click to view verified Bar Council enrollment credentials"
                      >
                        <span>✓</span>
                        <span>{badge?.verification_badge_text || "Professional Enrollment Verified"}</span>
                        <span style={{ fontSize: "10px", color: "#059669", background: "#d1fae5", padding: "1px 5px", borderRadius: "3px" }}>ℹ details</span>
                      </button>
                    ) : (
                      <StatusBadge status="PENDING" label="Verification Pending" />
                    )}
                  </div>
                  <p style={{ color: "#475569", fontSize: "14px", margin: 0 }}>
                    {lawyer.primary_practice_area || "High Court & District Counsel"} • {lawyer.experience_years ? `${lawyer.experience_years} Years at Bar` : "Enrolled Advocate"}
                  </p>
                </div>

                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "24px", fontWeight: 800, color: "#2563eb" }}>
                    ₹{feeAmount.toLocaleString("en-IN")}
                  </div>
                  <span style={{ fontSize: "12px", color: "#64748b" }}>consultation fee</span>
                </div>
              </div>

              {/* Location & Languages */}
              <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginTop: "18px" }}>
                <span style={{ fontSize: "12px", padding: "5px 12px", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "6px", color: "#334155", fontWeight: 500 }}>
                  📍 {lawyer.location || "National Jurisdiction"}
                </span>

                {lawyer.languages && (
                  <span style={{ fontSize: "12px", padding: "5px 12px", background: "#ecfdf5", border: "1px solid #a7f3d0", borderRadius: "6px", color: "#059669", fontWeight: 500 }}>
                    🗣️ {(Array.isArray(lawyer.languages) ? lawyer.languages : [lawyer.languages]).join(", ")}
                  </span>
                )}
              </div>

              {/* Professional Bio */}
              <div style={{ marginTop: "24px", borderTop: "1px solid #f1f5f9", paddingTop: "20px" }}>
                <h3 style={{ fontSize: "15px", fontWeight: 700, color: "#0f172a", marginBottom: "8px" }}>
                  Professional Bio & Chambers Profile
                </h3>
                <p style={{ fontSize: "14px", color: "#334155", lineHeight: 1.6, margin: 0 }}>
                  {lawyer.bio || "Enrolled Advocate available for legal advisory, contract drafting, legal notice responses, and court representation."}
                </p>
              </div>

              {/* Practice Areas */}
              {lawyer.practice_areas && lawyer.practice_areas.length > 0 && (
                <div style={{ marginTop: "20px", borderTop: "1px solid #f1f5f9", paddingTop: "18px" }}>
                  <h3 style={{ fontSize: "14px", fontWeight: 700, color: "#0f172a", marginBottom: "10px" }}>
                    Specializations & Practice Areas
                  </h3>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {lawyer.practice_areas.map((pa, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: "12px",
                          padding: "4px 10px",
                          borderRadius: "6px",
                          background: "#eff6ff",
                          color: "#1d4ed8",
                          border: "1px solid #bfdbfe",
                          fontWeight: 500,
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
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "12px",
                padding: "24px",
                marginBottom: "24px",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
              }}
            >
              <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#0f172a", marginBottom: "14px", display: "flex", alignItems: "center", gap: "8px" }}>
                <span>💳</span> Transparent Fee Breakdown
              </h3>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b" }}>
                  <span>Advocate Consultation (30 min)</span>
                  <span style={{ color: "#0f172a", fontWeight: 600 }}>₹{feeAmount.toFixed(2)}</span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b" }}>
                  <span>Statutory 18% GST (9% CGST + 9% SGST)</span>
                  <span style={{ color: "#0f172a", fontWeight: 600 }}>
                    {gstAmount !== null ? `₹${gstAmount.toFixed(2)}` : "Itemized at checkout"}
                  </span>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b" }}>
                  <span>Platform Fee</span>
                  <span style={{ color: "#059669", fontWeight: 600 }}>₹0.00 (Free)</span>
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    paddingTop: "12px",
                    marginTop: "6px",
                    borderTop: "1px solid #f1f5f9",
                    fontSize: "16px",
                    fontWeight: 700,
                  }}
                >
                  <span style={{ color: "#0f172a" }}>Total Payable</span>
                  <span style={{ color: "#2563eb" }}>₹{totalPayable.toFixed(2)}</span>
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
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: "12px",
                  padding: "24px",
                  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
                }}
              >
                <h3 style={{ fontSize: "15px", fontWeight: 700, color: "#0f172a", marginBottom: "12px" }}>
                  Weekly Chambers Schedule
                </h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "10px" }}>
                  {availabilities.map((rule) => (
                    <div
                      key={rule.id}
                      style={{
                        padding: "10px 12px",
                        background: "#f8fafc",
                        border: "1px solid #e2e8f0",
                        borderRadius: "8px",
                      }}
                    >
                      <div style={{ fontSize: "12px", fontWeight: 700, color: "#0f172a" }}>
                        {DAY_NAMES[rule.day_of_week] || `Day ${rule.day_of_week}`}
                      </div>
                      <div style={{ fontSize: "12px", color: "#2563eb", marginTop: "2px", fontWeight: 500 }}>
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
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: "12px",
              padding: "28px",
              boxShadow: "0 1px 3px rgba(0, 0, 0, 0.05)",
            }}
          >
            {/* STAGE 1: SELECT SLOT */}
            {bookingStep === "SELECT_SLOT" && (
              <div>
                <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a", margin: "0 0 6px 0" }}>
                  Book Consultation Appointment
                </h2>
                <p style={{ fontSize: "13px", color: "#64748b", margin: "0 0 20px 0" }}>
                  Select your preferred consultation date. Consultations take place securely in-browser via encrypted WebRTC.
                </p>

                {bookingError && (
                  <div
                    style={{
                      padding: "12px 14px",
                      borderRadius: "8px",
                      background: "#fef2f2",
                      color: "#dc2626",
                      fontSize: "13px",
                      marginBottom: "16px",
                      border: "1px solid #fecaca",
                    }}
                  >
                    {bookingError}
                  </div>
                )}

                {/* Date Picker & Quick Selectors */}
                <div style={{ marginBottom: "20px" }}>
                  <label style={{ fontSize: "13px", fontWeight: 600, color: "#334155", display: "block", marginBottom: "8px" }}>
                    Select Consultation Date (IST)
                  </label>
                  <input
                    type="date"
                    min={new Date().toISOString().split("T")[0]}
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "12px 14px",
                      background: "#ffffff",
                      border: "1px solid #cbd5e1",
                      borderRadius: "8px",
                      color: "#0f172a",
                      fontSize: "14px",
                      outline: "none",
                      marginBottom: "10px",
                    }}
                  />
                  {/* Quick date buttons */}
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {[
                      { label: "Tomorrow", days: 1 },
                      { label: "In 2 Days", days: 2 },
                      { label: "In 3 Days", days: 3 },
                    ].map((btn) => {
                      const d = new Date();
                      d.setDate(d.getDate() + btn.days);
                      const iso = d.toISOString().split("T")[0];
                      const isSelected = selectedDate === iso;
                      return (
                        <button
                          key={btn.label}
                          type="button"
                          onClick={() => setSelectedDate(iso)}
                          style={{
                            padding: "6px 12px",
                            borderRadius: "6px",
                            background: isSelected ? "#eff6ff" : "#f8fafc",
                            color: isSelected ? "#1d4ed8" : "#334155",
                            border: isSelected ? "1px solid #2563eb" : "1px solid #e2e8f0",
                            fontSize: "12px",
                            fontWeight: isSelected ? 600 : 500,
                            cursor: "pointer",
                          }}
                        >
                          {btn.label} ({d.toLocaleDateString("en-IN", { month: "short", day: "numeric" })})
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Consultation Details Card */}
                <div
                  style={{
                    background: "#eff6ff",
                    border: "1px solid #bfdbfe",
                    borderRadius: "10px",
                    padding: "16px",
                    marginBottom: "22px",
                    fontSize: "13px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px", fontWeight: 700, color: "#1d4ed8" }}>
                    <span>🗓️</span>
                    <span>Flexible Session Timing</span>
                  </div>
                  <p style={{ margin: "0 0 10px 0", color: "#1e3a8a", fontSize: "13px", lineHeight: 1.5 }}>
                    No rigid time slot required. Your consultation is scheduled for{" "}
                    <strong style={{ color: "#0f172a" }}>
                      {new Date(selectedDate + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" })}
                    </strong>
                    . Counsel will coordinate directly with you during standard chamber hours (08:00 AM - 08:00 PM IST).
                  </p>
                  <div style={{ display: "flex", gap: "16px", fontSize: "12px", color: "#1e40af", flexWrap: "wrap", fontWeight: 500 }}>
                    <span>✓ In-App HD Video</span>
                    <span>✓ 30-Minute Session</span>
                    <span>✓ Encrypted WebRTC</span>
                    {loadingSlots ? (
                      <span style={{ color: "#64748b" }}>· Checking chamber slots...</span>
                    ) : slots.length > 0 ? (
                      <span style={{ color: "#059669" }}>· {slots.length} chamber slots available</span>
                    ) : null}
                  </div>

                  {slots.length > 0 && (
                    <div style={{ marginTop: "12px" }}>
                      <div style={{ fontSize: "11px", color: "#1d4ed8", marginBottom: "6px", fontWeight: 600 }}>
                        Optional Preferred Time Slot:
                      </div>
                      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                        {slots.slice(0, 6).map((slot, idx) => {
                          const isSelected = selectedSlot === slot;
                          return (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => setSelectedSlot(isSelected ? null : slot)}
                              style={{
                                padding: "5px 12px",
                                borderRadius: "6px",
                                fontSize: "12px",
                                fontWeight: 600,
                                background: isSelected ? "#2563eb" : "#ffffff",
                                color: isSelected ? "#ffffff" : "#334155",
                                border: isSelected ? "1px solid #2563eb" : "1px solid #cbd5e1",
                                cursor: "pointer",
                              }}
                            >
                              {new Date(slot.start_time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true })}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  onClick={handleProceedToReview}
                  disabled={!selectedDate}
                  className="btn btn-primary"
                  style={{ width: "100%", padding: "12px", fontSize: "14px", fontWeight: 700, background: "#2563eb", color: "#ffffff", borderRadius: "8px" }}
                >
                  Continue to Price Review (₹{totalPayable.toFixed(2)}) →
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
                    style={{ background: "transparent", border: "none", color: "#64748b", cursor: "pointer", fontSize: "13px", fontWeight: 500 }}
                  >
                    ← Change Date
                  </button>
                </div>

                <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a", margin: "0 0 4px 0" }}>
                  Review Consultation Summary
                </h2>
                <p style={{ fontSize: "13px", color: "#64748b", margin: "0 0 18px 0" }}>
                  Verify your session details and complete payment securely.
                </p>

                {bookingError && (
                  <div
                    style={{
                      padding: "12px 14px",
                      borderRadius: "8px",
                      background: "#fef2f2",
                      color: "#dc2626",
                      fontSize: "13px",
                      marginBottom: "16px",
                      border: "1px solid #fecaca",
                    }}
                  >
                    {bookingError}
                  </div>
                )}

                {/* Booking Summary Box */}
                <div
                  style={{
                    background: "#f8fafc",
                    border: "1px solid #e2e8f0",
                    borderRadius: "10px",
                    padding: "16px",
                    marginBottom: "18px",
                    fontSize: "13px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "8px",
                    color: "#334155",
                  }}
                >
                  <div><strong style={{ color: "#0f172a" }}>Advocate:</strong> Adv. {lawyer.full_name}</div>
                  <div><strong style={{ color: "#0f172a" }}>Format:</strong> In-App Video Consultation (30 Minutes)</div>
                  <div>
                    <strong style={{ color: "#0f172a" }}>Consultation Date:</strong>{" "}
                    <span>
                      {new Date(selectedDate + "T00:00:00").toLocaleDateString("en-IN", {
                        weekday: "long",
                        day: "numeric",
                        month: "long",
                        year: "numeric",
                      })}
                    </span>
                  </div>
                  <div>
                    <strong style={{ color: "#0f172a" }}>Timing:</strong> Flexible Chamber Hours (Coordinated with counsel)
                  </div>
                  <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: "8px" }}>
                    <strong style={{ color: "#0f172a" }}>Fee:</strong> ₹{feeAmount.toFixed(2)}
                    {gstAmount !== null ? ` + ₹${gstAmount.toFixed(2)} (18% GST)` : ""}
                  </div>
                  <div style={{ fontSize: "15px", fontWeight: 700, color: "#2563eb" }}>
                    Total Payable: ₹{totalPayable.toFixed(2)}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleConfirmAndPay}
                  disabled={bookingSubmitting}
                  className="btn btn-primary"
                  style={{ width: "100%", padding: "12px", fontSize: "14px", fontWeight: 700, background: "#2563eb", color: "#ffffff", borderRadius: "8px" }}
                >
                  {bookingSubmitting ? "Locking session & opening gateway..." : `Pay Securely (₹${totalPayable.toFixed(2)}) →`}
                </button>
              </div>
            )}

            {/* STAGE 3: BOOKING CONFIRMED (Section 13) */}
            {bookingStep === "CONFIRMED" && bookedConsultation && (
              <div style={{ textAlign: "center", padding: "10px 0" }}>
                <div style={{ fontSize: "36px", marginBottom: "8px" }}>🎉</div>
                <h2 style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a", margin: "0 0 6px 0" }}>
                  Your consultation is booked
                </h2>
                <p style={{ fontSize: "13px", color: "#64748b", margin: "0 0 16px 0" }}>
                  You and Adv. {lawyer.full_name} will receive email reminders prior to the session.
                </p>

                <div
                  style={{
                    background: "#ecfdf5",
                    border: "1px solid #a7f3d0",
                    borderRadius: "8px",
                    padding: "14px",
                    marginBottom: "18px",
                    fontSize: "13px",
                    textAlign: "left",
                    color: "#065f46",
                  }}
                >
                  <div><strong style={{ color: "#064e3b" }}>Advocate:</strong> Adv. {lawyer.full_name}</div>
                  <div><strong style={{ color: "#064e3b" }}>Status:</strong> Confirmed & Paid</div>
                  <div><strong style={{ color: "#064e3b" }}>Scheduled:</strong> {bookedConsultation.scheduled_start || (bookedConsultation as unknown as { scheduled_at?: string }).scheduled_at ? new Date(bookedConsultation.scheduled_start || (bookedConsultation as unknown as { scheduled_at?: string }).scheduled_at!).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) : "Confirmed on calendar"} IST</div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  <Link href="/consultations" className="btn btn-primary" style={{ textAlign: "center", background: "#2563eb", color: "#ffffff", padding: "10px", borderRadius: "8px", textDecoration: "none" }}>
                    View Consultation Session →
                  </Link>
                  <Link href="/dashboard" className="btn btn-secondary" style={{ textAlign: "center", border: "1px solid #cbd5e1", padding: "10px", borderRadius: "8px", color: "#334155", textDecoration: "none" }}>
                    Return to Dashboard
                  </Link>
                </div>
              </div>
            )}

            <div style={{ marginTop: "16px", textAlign: "center", fontSize: "12px", color: "#64748b" }}>
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

        {/* Phase 14 BCI Rule 36 Verification Transparency Modal */}
        {showBadgeModal && badge && (
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: "rgba(15, 23, 42, 0.6)",
              backdropFilter: "blur(4px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
              padding: "16px",
            }}
            onClick={() => setShowBadgeModal(false)}
          >
            <div
              style={{
                width: "100%",
                maxWidth: "520px",
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: "12px",
                padding: "24px",
                boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
                <div>
                  <div style={{ fontSize: "11px", fontWeight: 700, color: "#059669", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "4px" }}>
                    Factual Credential Verification
                  </div>
                  <h3 style={{ fontSize: "18px", fontWeight: 700, color: "#0f172a", margin: 0 }}>
                    {badge.verification_badge_text}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setShowBadgeModal(false)}
                  style={{ background: "transparent", border: "none", color: "#64748b", fontSize: "18px", cursor: "pointer" }}
                >
                  ✕
                </button>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "13px", marginBottom: "20px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 10px", background: "#f8fafc", borderRadius: "6px", border: "1px solid #f1f5f9" }}>
                  <span style={{ color: "#64748b" }}>State Bar Council:</span>
                  <span style={{ color: "#0f172a", fontWeight: 600 }}>{badge.state_bar_council || "Enrolled Bar"}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 10px", background: "#f8fafc", borderRadius: "6px", border: "1px solid #f1f5f9" }}>
                  <span style={{ color: "#64748b" }}>Enrollment Number:</span>
                  <span style={{ color: "#2563eb", fontWeight: 600, fontFamily: "monospace" }}>{badge.enrollment_number_masked}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 10px", background: "#f8fafc", borderRadius: "6px", border: "1px solid #f1f5f9" }}>
                  <span style={{ color: "#64748b" }}>Verification Method:</span>
                  <span style={{ color: "#0f172a" }}>{badge.verification_method?.replace(/_/g, " ")}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 10px", background: "#f8fafc", borderRadius: "6px", border: "1px solid #f1f5f9" }}>
                  <span style={{ color: "#64748b" }}>Verified On:</span>
                  <span style={{ color: "#0f172a" }}>{badge.verified_at ? new Date(badge.verified_at).toLocaleDateString() : "Verified"}</span>
                </div>
              </div>

              <div style={{ padding: "12px", background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: "8px", fontSize: "12px", color: "#1e40af", lineHeight: "1.5", marginBottom: "18px" }}>
                <strong style={{ color: "#1e3a8a" }}>Statutory Compliance Declaration:</strong> {badge.compliance_declaration}
              </div>

              <div style={{ fontSize: "11px", color: "#64748b", lineHeight: "1.4", textAlign: "center" }}>
                Notice: Bar Council of India Rule 36 prohibits advocate advertising and solicitation. This badge factualizes verified enrollment without endorsing professional quality, court victory guarantees, or legal outcome ratings.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
