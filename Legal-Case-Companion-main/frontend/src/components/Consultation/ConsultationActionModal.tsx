"use client";

import React, { useState } from "react";
import { apiClient } from "@/api/client";
import { ConsultationItem } from "@/types";

interface Props {
  type: "RESCHEDULE" | "CANCEL" | "REJECT" | "NO_SHOW" | "COMPLETE" | "SCHEDULE";
  consultation: ConsultationItem;
  onClose: () => void;
  onSuccess: () => void;
}

export function ConsultationActionModal({
  type,
  consultation,
  onClose,
  onSuccess,
}: Props) {
  const [scheduledAt, setScheduledAt] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(consultation.duration_minutes || 30);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const dateVal = scheduledAt.includes("T") ? scheduledAt : `${scheduledAt}T10:00:00+05:30`;
      if (type === "RESCHEDULE") {
        if (!scheduledAt) {
          setError("Please select a date.");
          setLoading(false);
          return;
        }
        await apiClient.post(`/api/v1/consultations/${consultation.id}/reschedule`, {
          scheduled_at: new Date(dateVal).toISOString(),
          duration_minutes: durationMinutes,
          reason: reason || undefined,
        });
      } else if (type === "SCHEDULE") {
        if (!scheduledAt) {
          setError("Please select a date for the consultation.");
          setLoading(false);
          return;
        }
        await apiClient.post(`/api/v1/consultations/${consultation.id}/schedule`, {
          scheduled_at: new Date(dateVal).toISOString(),
          duration_minutes: durationMinutes,
        });
      } else if (type === "CANCEL") {
        await apiClient.post(`/api/v1/consultations/${consultation.id}/cancel`, {
          reason: reason || undefined,
        });
      } else if (type === "REJECT") {
        await apiClient.post(`/api/v1/consultations/${consultation.id}/reject`, {
          reason: reason || undefined,
        });
      } else if (type === "NO_SHOW") {
        await apiClient.post(`/api/v1/consultations/${consultation.id}/no-show`, {
          reason: reason || "Participant did not attend scheduled session",
        });
      } else if (type === "COMPLETE") {
        await apiClient.post(`/api/v1/consultations/${consultation.id}/complete`, {});
      }

      onSuccess();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Operation failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const getTitle = () => {
    switch (type) {
      case "RESCHEDULE":
        return "↻ Reschedule Consultation";
      case "SCHEDULE":
        return "📅 Schedule Consultation Session";
      case "CANCEL":
        return "⚠️ Cancel Consultation";
      case "REJECT":
        return "🛑 Decline Consultation Request";
      case "NO_SHOW":
        return "⚠️ Mark as No-Show";
      case "COMPLETE":
        return "✓ Complete Consultation Session";
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.8)",
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
          background: "#141721",
          border: "1px solid #232838",
          borderRadius: "12px",
          width: "100%",
          maxWidth: "460px",
          padding: "24px",
          color: "#f7f8fa",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ fontSize: "16px", fontWeight: 600, margin: "0 0 12px 0" }}>
          {getTitle()}
        </h3>

        {error && (
          <div
            style={{
              padding: "10px 14px",
              borderRadius: "6px",
              background: "rgba(239, 68, 68, 0.15)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              color: "#fca5a5",
              fontSize: "12px",
              marginBottom: "16px",
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {(type === "RESCHEDULE" || type === "SCHEDULE") && (
            <div style={{ display: "flex", flexDirection: "column", gap: "14px", marginBottom: "16px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                  Select Consultation Date (IST):
                </label>
                <input
                  type="date"
                  required
                  min={new Date().toISOString().split("T")[0]}
                  value={scheduledAt}
                  onChange={(e) => setScheduledAt(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px",
                    borderRadius: "6px",
                    background: "#1a1e2e",
                    border: "1px solid #282f44",
                    color: "#f7f8fa",
                    fontSize: "13px",
                  }}
                />
                <p style={{ margin: "4px 0 0 0", fontSize: "11px", color: "#64748b" }}>
                  Timing is flexible within standard chamber hours (08:00 AM - 08:00 PM IST) and coordinated with counsel.
                </p>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                  Duration (Minutes):
                </label>
                <select
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(Number(e.target.value))}
                  style={{
                    width: "100%",
                    padding: "10px",
                    borderRadius: "6px",
                    background: "#1a1e2e",
                    border: "1px solid #282f44",
                    color: "#f7f8fa",
                    fontSize: "13px",
                  }}
                >
                  <option value={15}>15 Minutes</option>
                  <option value={30}>30 Minutes</option>
                  <option value={45}>45 Minutes</option>
                  <option value={60}>60 Minutes (1 Hour)</option>
                  <option value={90}>90 Minutes</option>
                  <option value={120}>120 Minutes (2 Hours)</option>
                </select>
              </div>
            </div>
          )}

          {(type === "CANCEL" || type === "REJECT" || type === "NO_SHOW" || type === "RESCHEDULE") && (
            <div style={{ marginBottom: "18px" }}>
              <label style={{ display: "block", fontSize: "12px", color: "#94a3b8", marginBottom: "6px" }}>
                {type === "CANCEL" && "Cancellation Reason (Optional):"}
                {type === "REJECT" && "Decline Reason:"}
                {type === "NO_SHOW" && "No-Show Observation Notes:"}
                {type === "RESCHEDULE" && "Reason for Rescheduling (Optional):"}
              </label>
              <textarea
                rows={3}
                placeholder="Enter details for record..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px",
                  borderRadius: "6px",
                  background: "#1a1e2e",
                  border: "1px solid #282f44",
                  color: "#f7f8fa",
                  fontSize: "13px",
                }}
              />
            </div>
          )}

          {type === "COMPLETE" && (
            <p style={{ fontSize: "13px", color: "#94a3b8", lineHeight: "1.5", marginBottom: "18px" }}>
              Mark this consultation as successfully completed. This will close out the scheduled session and record completion in the matter timeline.
            </p>
          )}

          <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                background: "transparent",
                border: "1px solid #232838",
                color: "#94a3b8",
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                background:
                  type === "CANCEL" || type === "REJECT" || type === "NO_SHOW"
                    ? "#ef4444"
                    : "linear-gradient(135deg, #3b82f6, #2563eb)",
                border: "none",
                color: "#ffffff",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {loading ? "Processing..." : "Confirm"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
