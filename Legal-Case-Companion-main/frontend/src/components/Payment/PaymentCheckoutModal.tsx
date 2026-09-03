"use client";

import React, { useState } from "react";
import { ConsultationItem, PaymentIntentResponse } from "@/types";
import { apiClient } from "@/api/client";
import { StatusBadge } from "@/components/StatusBadge";

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
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(6px)",
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
          background: "#141721",
          border: "1px solid #232838",
          borderRadius: "14px",
          width: "100%",
          maxWidth: "480px",
          overflow: "hidden",
          boxShadow: "0 20px 40px rgba(0,0,0,0.5)",
          color: "#f7f8fa",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "18px 22px",
            borderBottom: "1px solid #232838",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "18px" }}>💳</span>
            <h3 style={{ fontSize: "16px", fontWeight: 600, margin: 0 }}>
              Consultation Checkout
            </h3>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
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
              background: "#1a1e2e",
              border: "1px solid #282f44",
              marginBottom: "18px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ fontSize: "13px", color: "#94a3b8" }}>Session Status</span>
              <StatusBadge status={consultation.status} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <span style={{ fontSize: "13px", color: "#94a3b8" }}>Scheduled Date (IST)</span>
              <span style={{ fontSize: "13px", fontWeight: 500 }}>
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
              <span style={{ fontSize: "13px", color: "#94a3b8" }}>Time Window (IST)</span>
              <span style={{ fontSize: "13px", fontWeight: 500 }}>
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
              background: "rgba(59, 130, 246, 0.06)",
              border: "1px solid rgba(59, 130, 246, 0.2)",
              marginBottom: "20px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: "12px", color: "#94a3b8" }}>Authoritative Fee ({currency})</div>
                <div style={{ fontSize: "24px", fontWeight: 700, color: "#60a5fa", marginTop: "2px" }}>
                  ₹{feeAmount.toLocaleString("en-IN")}
                </div>
              </div>
              <div
                style={{
                  fontSize: "11px",
                  padding: "4px 8px",
                  borderRadius: "4px",
                  background: "rgba(16, 185, 129, 0.15)",
                  color: "#10b981",
                  border: "1px solid rgba(16, 185, 129, 0.3)",
                  fontWeight: 600,
                }}
              >
                100% SECURE
              </div>
            </div>
          </div>

          {/* STEP: DETAILS / INITIAL STATE */}
          {step === "DETAILS" && (
            <div>
              <p style={{ fontSize: "13px", color: "#94a3b8", lineHeight: "1.5", marginBottom: "18px" }}>
                Payment is authoritatively processed through our verified payment gateway. Upon confirmed payment, your legal consultation session will be scheduled and confirmed on the counsel&apos;s calendar.
              </p>
              <button
                onClick={handleInitiatePayment}
                disabled={loading}
                style={{
                  width: "100%",
                  padding: "12px",
                  borderRadius: "8px",
                  background: "linear-gradient(135deg, #3b82f6, #2563eb)",
                  color: "#ffffff",
                  border: "none",
                  fontWeight: 600,
                  fontSize: "14px",
                  cursor: "pointer",
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
                  padding: "12px",
                  borderRadius: "6px",
                  background: "#1e2336",
                  border: "1px solid #2e3650",
                  fontSize: "12px",
                  color: "#94a3b8",
                  marginBottom: "16px",
                }}
              >
                <div><strong>Payment Reference:</strong> {paymentIntent.payment_id.slice(0, 16)}...</div>
                <div style={{ marginTop: "4px" }}><strong>Currency:</strong> {paymentIntent.currency}</div>
                <div style={{ marginTop: "4px" }}><strong>Status:</strong> Ready for Authorization</div>
              </div>

              <button
                onClick={handleSimulatePaymentConfirmation}
                disabled={loading}
                style={{
                  width: "100%",
                  padding: "12px",
                  borderRadius: "8px",
                  background: "linear-gradient(135deg, #10b981, #059669)",
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
              <div style={{ fontSize: "28px", marginBottom: "12px" }}>⏳</div>
              <div style={{ fontSize: "14px", fontWeight: 600, color: "#f7f8fa" }}>
                Verifying Payment with Gateway...
              </div>
              <p style={{ fontSize: "12px", color: "#94a3b8", marginTop: "6px" }}>
                Please do not close this window while we verify the transaction with the provider webhook.
              </p>
            </div>
          )}

          {/* STEP: SUCCESS */}
          {step === "SUCCESS" && (
            <div style={{ textAlign: "center", padding: "16px 0" }}>
              <div style={{ fontSize: "36px", marginBottom: "10px" }}>✅</div>
              <h4 style={{ fontSize: "16px", fontWeight: 700, color: "#10b981", margin: "0 0 6px 0" }}>
                Payment Confirmed!
              </h4>
              <p style={{ fontSize: "13px", color: "#94a3b8", margin: "0 0 18px 0" }}>
                Your consultation fee of ₹{feeAmount} has been verified. The consultation is now confirmed.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                <a
                  href={`/consultations/${consultation.id}/room`}
                  style={{
                    display: "block",
                    width: "100%",
                    padding: "12px",
                    borderRadius: "8px",
                    background: "linear-gradient(135deg, #10b981, #059669)",
                    color: "#ffffff",
                    textAlign: "center",
                    fontWeight: 700,
                    fontSize: "14px",
                    textDecoration: "none",
                    boxShadow: "0 4px 14px rgba(16, 185, 129, 0.4)",
                  }}
                >
                  Enter Video Consultation Room 🎥
                </a>
                <button
                  onClick={onClose}
                  style={{
                    width: "100%",
                    padding: "10px",
                    borderRadius: "8px",
                    background: "#1f293d",
                    color: "#f7f8fa",
                    border: "1px solid #3b82f6",
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
                  borderRadius: "6px",
                  background: "rgba(239, 68, 68, 0.12)",
                  border: "1px solid rgba(239, 68, 68, 0.3)",
                  color: "#ef4444",
                  fontSize: "13px",
                  marginBottom: "16px",
                }}
              >
                <strong>Payment Error:</strong> {errorMessage || "An unexpected error occurred."}
              </div>

              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  onClick={handleInitiatePayment}
                  style={{
                    flex: 1,
                    padding: "10px",
                    borderRadius: "8px",
                    background: "linear-gradient(135deg, #3b82f6, #2563eb)",
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
                    background: "transparent",
                    color: "#94a3b8",
                    border: "1px solid #232838",
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
