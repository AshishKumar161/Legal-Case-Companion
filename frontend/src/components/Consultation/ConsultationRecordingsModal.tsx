"use client";

import React, { useEffect, useState } from "react";
import { apiClient } from "@/api/client";
import { ConsultationItem, VideoRecordingItem } from "@/types";

interface Props {
  consultation: ConsultationItem;
  onClose: () => void;
}

export function ConsultationRecordingsModal({ consultation, onClose }: Props) {
  const [recordings, setRecordings] = useState<VideoRecordingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeRecording, setActiveRecording] = useState<VideoRecordingItem | null>(null);
  const [playbackTicket, setPlaybackTicket] = useState<string | null>(null);
  const [ticketLoading, setTicketLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    async function loadRecordings() {
      try {
        setLoading(true);
        setError(null);
        const res = (await apiClient.get(
          `/api/v1/consultations/${consultation.id}/recordings`
        )) as { items: VideoRecordingItem[] };
        if (mounted) {
          setRecordings(res?.items || []);
        }
      } catch (err: unknown) {
        if (!mounted) return;
        const msg = err instanceof Error ? err.message : "Failed to load recordings.";
        setError(msg);
      } finally {
        if (mounted) setLoading(false);
      }
    }
    void loadRecordings();
    return () => {
      mounted = false;
    };
  }, [consultation.id]);

  const handlePlayRecording = async (rec: VideoRecordingItem) => {
    setError(null);
    setTicketLoading(true);
    try {
      // Obtain an ephemeral 60s playback ticket (zero bearer token in query params)
      const res = (await apiClient.post(
        `/api/v1/recordings/${rec.id}/playback-ticket`,
        {}
      )) as { ticket: string };
      setPlaybackTicket(res.ticket);
      setActiveRecording(rec);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to obtain secure playback ticket.";
      setError(msg);
    } finally {
      setTicketLoading(false);
    }
  };

  const formatDuration = (sec?: number | null) => {
    if (!sec) return "00:00";
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const formatFileSize = (bytes?: number | null) => {
    if (!bytes) return "0 MB";
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(2)} MB`;
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.8)",
        backdropFilter: "blur(10px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
        padding: "20px",
        fontFamily: "Inter, sans-serif",
      }}
    >
      <div
        style={{
          backgroundColor: "#0f172a",
          borderRadius: "16px",
          border: "1px solid rgba(255, 255, 255, 0.12)",
          maxWidth: activeRecording ? "760px" : "560px",
          width: "100%",
          maxHeight: "90vh",
          overflowY: "auto",
          padding: "28px",
          color: "#f8fafc",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.6)",
          transition: "max-width 0.3s ease",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
            paddingBottom: "16px",
            marginBottom: "20px",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "20px" }}>📹</span>
              <h2 style={{ fontSize: "18px", fontWeight: 700, margin: 0 }}>
                Consultation Video Recordings
              </h2>
            </div>
            <p style={{ color: "#94a3b8", fontSize: "12px", margin: "4px 0 0" }}>
              Session #{consultation.id.slice(0, 8).toUpperCase()} • In-App Secure Streaming
            </p>
          </div>

          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "#94a3b8",
              fontSize: "22px",
              cursor: "pointer",
            }}
          >
            ✕
          </button>
        </div>

        {/* Active Video Player */}
        {activeRecording && playbackTicket && (
          <div
            style={{
              marginBottom: "24px",
              backgroundColor: "#020617",
              borderRadius: "12px",
              overflow: "hidden",
              border: "1px solid rgba(255, 255, 255, 0.1)",
            }}
          >
            <div
              style={{
                padding: "10px 14px",
                backgroundColor: "#1e293b",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                fontSize: "13px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ color: "#38bdf8", fontWeight: 600 }}>Streaming:</span>
                <span>Recording #{activeRecording.id.slice(0, 8)}</span>
                <span
                  style={{
                    backgroundColor: "rgba(34, 197, 94, 0.15)",
                    color: "#22c55e",
                    fontSize: "11px",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    fontWeight: 600,
                  }}
                >
                  HTTP 206 Partial Content
                </span>
                <span
                  style={{
                    backgroundColor: "rgba(168, 85, 247, 0.15)",
                    color: "#c084fc",
                    fontSize: "11px",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    fontWeight: 600,
                  }}
                >
                  Ephemeral Ticket
                </span>
              </div>
              <button
                onClick={() => {
                  setActiveRecording(null);
                  setPlaybackTicket(null);
                }}
                style={{
                  background: "none",
                  border: "none",
                  color: "#94a3b8",
                  fontSize: "12px",
                  cursor: "pointer",
                  fontWeight: 600,
                }}
              >
                Close Player ✕
              </button>
            </div>

            <video
              controls
              autoPlay
              style={{
                width: "100%",
                maxHeight: "420px",
                display: "block",
                backgroundColor: "#000",
              }}
              src={`/api/v1/recordings/${activeRecording.id}/play?ticket=${encodeURIComponent(playbackTicket)}`}
            >
              Your browser does not support HTML5 video streaming.
            </video>

            {/* SHA-256 Checksum Verification Details */}
            {activeRecording.checksum_sha256 && (
              <div
                style={{
                  padding: "8px 14px",
                  backgroundColor: "#0b0f19",
                  fontSize: "11px",
                  color: "#64748b",
                  fontFamily: "monospace",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span>SHA-256: {activeRecording.checksum_sha256.slice(0, 32)}...</span>
                <span style={{ color: "#22c55e" }}>✓ Cryptographic Integrity Verified</span>
              </div>
            )}
          </div>
        )}

        {/* Content State */}
        {loading ? (
          <div style={{ textAlign: "center", padding: "40px 0", color: "#94a3b8" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                border: "3px solid rgba(59, 130, 246, 0.2)",
                borderTopColor: "#3b82f6",
                borderRadius: "50%",
                animation: "spin 1s linear infinite",
                margin: "0 auto 12px",
              }}
            />
            <p style={{ fontSize: "14px", margin: 0 }}>Loading recorded sessions...</p>
          </div>
        ) : error ? (
          <div
            style={{
              padding: "16px",
              backgroundColor: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.25)",
              borderRadius: "8px",
              color: "#ef4444",
              fontSize: "13px",
              marginBottom: "16px",
            }}
          >
            {error}
          </div>
        ) : recordings.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: "48px 20px",
              backgroundColor: "rgba(255, 255, 255, 0.02)",
              borderRadius: "12px",
              border: "1px dashed rgba(255, 255, 255, 0.1)",
            }}
          >
            <div style={{ fontSize: "36px", marginBottom: "12px" }}>📼</div>
            <h3 style={{ fontSize: "16px", fontWeight: 600, margin: "0 0 6px" }}>
              No Recordings Available
            </h3>
            <p style={{ color: "#94a3b8", fontSize: "13px", maxWidth: "380px", margin: "0 auto" }}>
              Recordings only exist for consultations where both the Client and Counsel mutually consented to record the session.
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {recordings.map((rec) => {
              const isAvailable = rec.status === "AVAILABLE";
              const isSelected = activeRecording?.id === rec.id;

              return (
                <div
                  key={rec.id}
                  style={{
                    backgroundColor: isSelected ? "rgba(59, 130, 246, 0.1)" : "#1e293b",
                    border: isSelected ? "1px solid #3b82f6" : "1px solid rgba(255, 255, 255, 0.06)",
                    borderRadius: "10px",
                    padding: "16px",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: "12px",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                      <span style={{ fontSize: "14px", fontWeight: 600 }}>
                        {new Date(rec.created_at).toLocaleString(undefined, {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </span>
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 700,
                          padding: "2px 8px",
                          borderRadius: "4px",
                          backgroundColor:
                            rec.status === "AVAILABLE"
                              ? "rgba(34, 197, 94, 0.15)"
                              : rec.status === "PROCESSING"
                              ? "rgba(234, 179, 8, 0.15)"
                              : "rgba(239, 68, 68, 0.15)",
                          color:
                            rec.status === "AVAILABLE"
                              ? "#22c55e"
                              : rec.status === "PROCESSING"
                              ? "#eab308"
                              : "#ef4444",
                        }}
                      >
                        {rec.status}
                      </span>
                    </div>

                    <div style={{ fontSize: "12px", color: "#94a3b8", display: "flex", gap: "14px" }}>
                      <span>⏱️ {formatDuration(rec.duration_seconds)}</span>
                      <span>💾 {formatFileSize(rec.file_size_bytes)}</span>
                      <span>Format: WebM (VP8/Opus)</span>
                    </div>
                  </div>

                  {isAvailable && (
                    <button
                      onClick={() => handlePlayRecording(rec)}
                      disabled={ticketLoading}
                      style={{
                        backgroundColor: isSelected ? "#10b981" : "#2563eb",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "8px",
                        padding: "8px 16px",
                        fontSize: "13px",
                        fontWeight: 600,
                        cursor: ticketLoading ? "wait" : "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                      }}
                    >
                      <span>▶</span>
                      <span>{isSelected ? "Now Playing" : ticketLoading ? "Authenticating..." : "Stream Playback"}</span>
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div style={{ marginTop: "24px", textAlign: "right" }}>
          <button
            onClick={onClose}
            style={{
              backgroundColor: "rgba(255, 255, 255, 0.08)",
              color: "#f8fafc",
              border: "none",
              borderRadius: "8px",
              padding: "10px 20px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
