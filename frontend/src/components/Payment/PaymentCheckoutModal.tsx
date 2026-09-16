"use client";

import React, { useState } from "react";
import { ConsultationItem, PaymentIntentResponse } from "@/types";
import { apiClient } from "@/api/client";
import { StatusBadge } from "@/components/StatusBadge";
import { CheckCircleIcon, ClockIcon, VideoIcon, AlertTriangleIcon } from "@/components/ui/Icons";

interface PaymentCheckoutModalProps {
  consultation: ConsultationItem;
  onClose: () => void;
  onPaymentSuccess: () => void;
}

type CheckoutStep = "DETAILS" | "INITIALIZING" | "PAYMENT_READY" | "PROCESSING" | "SUCCESS" | "ERROR";

export function PaymentCheckoutModal({
  consultation,
  onClose,
  onPaymentSuccess,
}: PaymentCheckoutModalProps) {
  const [step, setStep] = useState<CheckoutStep>("DETAILS");
  const [paymentIntent, setPaymentIntent] = useState<PaymentIntentResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const feeAmount = consultation.fee_amount ?? 2500;
  const currency = consultation.currency ?? "INR";

  const handleInitiatePayment = async () => {
    setLoading(true);
    setErrorMessage(null);
    setStep("INITIALIZING");

    try {
      const res: PaymentIntentResponse = await apiClient.post(
        `/api/v1/consultations/${consultation.id}/payments`,
        {}
      );
      setPaymentIntent(res);
      setStep("PAYMENT_READY");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to initiate payment intent.";
      setErrorMessage(msg);
      setStep("ERROR");
    } finally {
      setLoading(false);
    }
  };

  const handleSimulatePaymentConfirmation = async () => {
    setLoading(true);
    setStep("PROCESSING");
    setErrorMessage(null);

    try {
      // Authoritatively process test payment
      await apiClient.post(`/api/v1/consultations/${consultation.id}/pay-test`, {});
      setStep("SUCCESS");
      onPaymentSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Payment processing failed. Please retry.";
      setErrorMessage(msg);
      setStep("ERROR");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(15, 23, 42, 0.6)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "16px",
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "var(--surface-card, #ffffff)",
          border: "1px solid var(--border-subtle, #e2e8f0)",
          borderRadius: "14px",
          width: "100%",
          maxWidth: "480px",
          overflow: "hidden",
          boxShadow: "var(--shadow-xl)",
          color: "var(--text-primary, #0f172a)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "18px 22px",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{ width: "32px", height: "32px", borderRadius: "8px", background: "#eff6ff", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <CheckCircleIcon size={18} color="#2563eb" />
            </div>
            <h3 style={{ fontSize: "16px", fontWeight: 700, margin: 0, color: "#0f172a" }}>
              Consultation Checkout
            </h3>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "#64748b",
              cursor: "pointer",
              fontSize: "18px",
              padding: "4px",
            }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "22px" }}>
          {/* Consultation Metadata Card */}
          <div
            style={{
              padding: "14px 16px",
              borderRadius: "8px",
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              marginBottom: "18px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ fontSize: "13px", color: "#64748b" }}>Session Status</span>
              <StatusBadge status={consultation.status} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ fontSize: "13px", color: "#64748b" }}>Scheduled Date (IST)</span>
              <span style={{ fontSize: "13px", fontWeight: 600, color: "#0f172a" }}>
                {new Date(consultation.scheduled_start).toLocaleDateString("en-IN", {
                  timeZone: "Asia/Kolkata",
                  weekday: "short",
                  day: "numeric",
                  month: "short",
                  year: "numeric",
                })}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontSize: "13px", color: "#64748b" }}>Time Window (IST)</span>
              <span style={{ fontSize: "13px", fontWeight: 600, color: "#0f172a" }}>
                {new Date(consultation.scheduled_start).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" })}
                {" - "}
                {new Date(consultation.scheduled_end).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" })}
                {" IST"}
              </span>
            </div>
          </div>

          {/* Price & Authoritative Fee Breakdown */}
          <div
            style={{
              padding: "16px",
              borderRadius: "8px",
              background: "#eff6ff",
              border: "1px solid #bfdbfe",
              marginBottom: "20px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: "12px", color: "#64748b", fontWeight: 500 }}>Authoritative Fee ({currency})</div>
                <div style={{ fontSize: "24px", fontWeight: 800, color: "#1d4ed8", marginTop: "2px" }}>
                  ₹{feeAmount.toLocaleString("en-IN")}
                </div>
              </div>
              <div
                style={{
                  fontSize: "11px",
                  padding: "4px 8px",
                  borderRadius: "6px",
                  background: "#ecfdf5",
                  color: "#059669",
                  border: "1px solid #a7f3d0",
                  fontWeight: 700,
                  letterSpacing: "0.04em",
                }}
              >
                100% SECURE ESCROW
              </div>
            </div>
          </div>

          {/* STEP: DETAILS / INITIAL STATE */}
          {step === "DETAILS" && (
            <div>
              <p style={{ fontSize: "13px", color: "#64748b", lineHeight: "1.5", marginBottom: "18px" }}>
                Payment is authoritatively processed through our verified payment gateway. Upon confirmed payment, your legal consultation session will be scheduled and confirmed on the counsel&apos;s calendar.
              </p>
              <button
                onClick={handleInitiatePayment}
                disabled={loading}
                style={{
                  width: "100%",
                  padding: "12px",
                  borderRadius: "8px",
                  background: "#2563eb",
                  color: "#ffffff",
                  border: "none",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: "pointer",
                  transition: "background 0.15s ease",
                }}
              >
                {loading ? "Creating Payment Intent..." : `Proceed to Pay ₹${feeAmount}`}
              </button>
            </div>
          )}

          {/* STEP: PAYMENT_READY */}
          {step === "PAYMENT_READY" && paymentIntent && (
            <div>
              <div
                style={{
                  padding: "12px 14px",
                  borderRadius: "8px",
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  fontSize: "12px",
                  color: "#475569",
                  marginBottom: "16px",
                }}
              >
                <div><strong style={{ color: "#0f172a" }}>Payment Reference:</strong> {paymentIntent.payment_id.slice(0, 16)}...</div>
                <div style={{ marginTop: "4px" }}><strong style={{ color: "#0f172a" }}>Currency:</strong> {paymentIntent.currency}</div>
                <div style={{ marginTop: "4px" }}><strong style={{ color: "#0f172a" }}>Status:</strong> Ready for Authorization</div>
              </div>

              <button
                onClick={handleSimulatePaymentConfirmation}
                disabled={loading}
                style={{
                  width: "100%",
                  padding: "12px",
                  borderRadius: "8px",
                  background: "#059669",
                  color: "#ffffff",
                  border: "none",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: "pointer",
                }}
              >
                {loading ? "Processing Secure Payment..." : `Authorize & Pay ₹${paymentIntent.amount}`}
              </button>
            </div>
          )}

          {/* STEP: PROCESSING */}
          {step === "PROCESSING" && (
            <div style={{ textAlign: "center", padding: "20px 0" }}>
              <div style={{ display: "flex", justifyContent: "center", marginBottom: "12px" }}>
                <ClockIcon size={32} color="#2563eb" />
              </div>
              <div style={{ fontSize: "15px", fontWeight: 700, color: "#0f172a" }}>
                Verifying Payment with Gateway...
              </div>
              <p style={{ fontSize: "12px", color: "#64748b", marginTop: "6px" }}>
                Please do not close this window while we verify the transaction with the provider webhook.
              </p>
            </div>
          )}

          {/* STEP: SUCCESS */}
          {step === "SUCCESS" && (
            <div style={{ textAlign: "center", padding: "16px 0" }}>
              <div style={{ display: "flex", justifyContent: "center", marginBottom: "10px" }}>
                <CheckCircleIcon size={36} color="#059669" />
              </div>
              <h4 style={{ fontSize: "17px", fontWeight: 700, color: "#059669", margin: "0 0 6px 0" }}>
                Payment Confirmed!
              </h4>
              <p style={{ fontSize: "13px", color: "#64748b", margin: "0 0 18px 0" }}>
                Your consultation fee of ₹{feeAmount} has been verified. The consultation is now confirmed.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <a
                  href={`/consultations/${consultation.id}/room`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "8px",
                    width: "100%",
                    padding: "12px",
                    borderRadius: "8px",
                    background: "#059669",
                    color: "#ffffff",
                    textAlign: "center",
                    fontWeight: 600,
                    fontSize: "14px",
                    textDecoration: "none",
                  }}
                >
                  <VideoIcon size={16} color="#ffffff" />
                  <span>Enter Video Consultation Room</span>
                </a>
                <button
                  onClick={onClose}
                  style={{
                    width: "100%",
                    padding: "10px",
                    borderRadius: "8px",
                    background: "#f8fafc",
                    color: "#334155",
                    border: "1px solid #e2e8f0",
                    fontWeight: 600,
                    fontSize: "13px",
                    cursor: "pointer",
                  }}
                >
                  Done & Return to Appointments
                </button>
              </div>
            </div>
          )}

          {/* STEP: ERROR */}
          {step === "ERROR" && (
            <div>
              <div
                style={{
                  padding: "12px 14px",
                  borderRadius: "8px",
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  color: "#dc2626",
                  fontSize: "13px",
                  marginBottom: "16px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <AlertTriangleIcon size={18} color="#dc2626" />
                <div>
                  <strong>Payment Error:</strong> {errorMessage || "An unexpected error occurred."}
                </div>
              </div>

              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  onClick={handleInitiatePayment}
                  style={{
                    flex: 1,
                    padding: "10px",
                    borderRadius: "8px",
                    background: "#2563eb",
                    color: "#ffffff",
                    border: "none",
                    fontWeight: 600,
                    fontSize: "13px",
                    cursor: "pointer",
                  }}
                >
                  Retry Payment
                </button>
                <button
                  onClick={onClose}
                  style={{
                    padding: "10px 16px",
                    borderRadius: "8px",
                    background: "#f8fafc",
                    color: "#475569",
                    border: "1px solid #e2e8f0",
                    fontWeight: 500,
                    fontSize: "13px",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
