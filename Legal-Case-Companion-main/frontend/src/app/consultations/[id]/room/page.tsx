"use client";

import React, { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiClient } from "@/api/client";

interface VideoJoinInfo {
  consultation_id: string;
  meeting_id: string;
  room_id: string;
  provider: string;
  status: string;
  participant_user_id: string;
  participant_name: string;
  participant_role: string;
  scheduled_start: string;
  scheduled_end: string;
  token: string;
  ice_servers: Array<{ urls: string | string[] }>;
  is_live: boolean;
}

interface CaseOption {
  id: string;
  title: string;
  status: string;
}

export default function VideoConsultationRoomPage() {
  const params = useParams();
  const router = useRouter();
  const consultationId = params.id as string;

  const [joinInfo, setJoinInfo] = useState<VideoJoinInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Audio / Video Controls
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  const [isScreenSharing, setIsScreenSharing] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<
    "connecting" | "connected" | "reconnecting" | "ended"
  >("connecting");

  // Timer
  const [secondsElapsed, setSecondsElapsed] = useState(0);
  const [isCallActive, setIsCallActive] = useState(false);

  // Post-call dialog state
  const [showPostCallModal, setShowPostCallModal] = useState(false);
  const [notesSummary, setNotesSummary] = useState("");
  const [actionItemInput, setActionItemInput] = useState("");
  const [actionItems, setActionItems] = useState<string[]>([]);
  const [submittingNotes, setSubmittingNotes] = useState(false);
  const [noteSaved, setNoteSaved] = useState(false);

  // Case creation / linking state
  const [postCallAction, setPostCallAction] = useState<"none" | "create" | "link">("none");
  const [newCaseTitle, setNewCaseTitle] = useState("");
  const [newCaseDesc, setNewCaseDesc] = useState("");
  const [newCasePracticeArea, setNewCasePracticeArea] = useState("");
  const [existingCases, setExistingCases] = useState<CaseOption[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [submittingCase, setSubmittingCase] = useState(false);
  const [caseSuccessMsg, setCaseSuccessMsg] = useState<string | null>(null);

  // Media refs
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement>(null);
  const remoteStreamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const [remotePeerActive, setRemotePeerActive] = useState(false);

  // 1. Fetch join information and initialize
  useEffect(() => {
    let mounted = true;

    async function initSession() {
      try {
        setLoading(true);
        setError(null);

        // Fetch join info with cryptographic tokens
        const info = (await apiClient.get(
          `/api/v1/consultations/${consultationId}/video/join`
        )) as VideoJoinInfo;

        if (!mounted) return;
        setJoinInfo(info);

        // Automatically start meeting
        await apiClient.post(
          `/api/v1/consultations/${consultationId}/video/start`,
          {}
        );

        setIsCallActive(true);
        setConnectionStatus("connected");

        // Fetch client's existing cases in case they want to link afterwards
        try {
          const casesRes = (await apiClient.get("/api/v1/cases")) as {
            items: CaseOption[];
          };
          if (mounted && casesRes?.items) {
            setExistingCases(casesRes.items.filter((c) => c.status !== "CLOSED"));
          }
        } catch {
          // Non-blocking
        }

        // Initialize local camera and mic
        let userMediaStream: MediaStream | null = null;
        try {
          userMediaStream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: true,
          });
          if (mounted) {
            localStreamRef.current = userMediaStream;
            if (localVideoRef.current) {
              localVideoRef.current.srcObject = userMediaStream;
            }
          }
        } catch (mediaErr) {
          console.warn("Could not access camera/microphone:", mediaErr);
        }

        // Connect Real-Time WebRTC WebSocket Signaling
        try {
          const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
          const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/consultations/${consultationId}/video/ws?token=${encodeURIComponent(info.token)}`;
          const ws = new WebSocket(wsUrl);
          wsRef.current = ws;

          const pc = new RTCPeerConnection({
            iceServers: info.ice_servers || [{ urls: "stun:stun.l.google.com:19302" }],
          });
          peerConnectionRef.current = pc;

          pc.onicecandidate = (event) => {
            if (event.candidate && ws.readyState === WebSocket.OPEN) {
              ws.send(
                JSON.stringify({
                  type: "ice-candidate",
                  candidate: event.candidate.candidate,
                  sdpMid: event.candidate.sdpMid,
                  sdpMLineIndex: event.candidate.sdpMLineIndex,
                })
              );
            }
          };

          pc.ontrack = (event) => {
            if (event.streams && event.streams[0]) {
              remoteStreamRef.current = event.streams[0];
              if (remoteVideoRef.current) {
                remoteVideoRef.current.srcObject = event.streams[0];
              }
              if (mounted) setRemotePeerActive(true);
            }
          };

          if (userMediaStream) {
            userMediaStream.getTracks().forEach((track) => {
              pc.addTrack(track, userMediaStream!);
            });
          }

          ws.onmessage = async (ev) => {
            try {
              const msg = JSON.parse(ev.data);
              if (msg.type === "peer-joined") {
                if (mounted) setRemotePeerActive(true);
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                if (ws.readyState === WebSocket.OPEN) {
                  ws.send(JSON.stringify({ type: "offer", sdp: offer.sdp }));
                }
              } else if (msg.type === "offer" && msg.sdp) {
                await pc.setRemoteDescription(new RTCSessionDescription({ type: "offer", sdp: msg.sdp }));
                const answer = await pc.createAnswer();
                await pc.setLocalDescription(answer);
                if (ws.readyState === WebSocket.OPEN) {
                  ws.send(JSON.stringify({ type: "answer", sdp: answer.sdp }));
                }
              } else if (msg.type === "answer" && msg.sdp) {
                await pc.setRemoteDescription(new RTCSessionDescription({ type: "answer", sdp: msg.sdp }));
              } else if (msg.type === "ice-candidate" && msg.candidate) {
                await pc.addIceCandidate(
                  new RTCIceCandidate({
                    candidate: msg.candidate,
                    sdpMid: msg.sdpMid,
                    sdpMLineIndex: msg.sdpMLineIndex,
                  })
                );
              } else if (msg.type === "peer-left") {
                if (mounted) setRemotePeerActive(false);
                if (remoteVideoRef.current) {
                  remoteVideoRef.current.srcObject = null;
                }
              }
            } catch (signalingErr) {
              console.warn("Signaling message handling error:", signalingErr);
            }
          };

          ws.onclose = () => {
            if (mounted) {
              setConnectionStatus((prev) => (prev === "ended" ? "ended" : "reconnecting"));
            }
          };
        } catch (wsErr) {
          console.warn("WebSocket signaling skipped:", wsErr);
        }
      } catch (err: any) {
        if (!mounted) return;
        setError(err.message || "Failed to enter video consultation room.");
        setConnectionStatus("ended");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    if (consultationId) {
      initSession();
    }

    return () => {
      mounted = false;
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (peerConnectionRef.current) {
        peerConnectionRef.current.close();
      }
      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, [consultationId]);

  // 2. Call elapsed timer
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isCallActive) {
      timer = setInterval(() => {
        setSecondsElapsed((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isCallActive]);

  // Toggle Mute
  const toggleMute = () => {
    if (localStreamRef.current) {
      const audioTracks = localStreamRef.current.getAudioTracks();
      audioTracks.forEach((t) => {
        t.enabled = isMuted;
      });
      setIsMuted(!isMuted);
    }
  };

  // Toggle Video
  const toggleVideo = () => {
    if (localStreamRef.current) {
      const videoTracks = localStreamRef.current.getVideoTracks();
      videoTracks.forEach((t) => {
        t.enabled = isVideoOff;
      });
      setIsVideoOff(!isVideoOff);
    }
  };

  // Toggle Screen Share
  const toggleScreenShare = async () => {
    if (!isScreenSharing) {
      try {
        const screenStream = await navigator.mediaDevices.getDisplayMedia({
          video: true,
        });
        if (localVideoRef.current) {
          localVideoRef.current.srcObject = screenStream;
        }
        setIsScreenSharing(true);
        screenStream.getVideoTracks()[0].onended = () => {
          if (localVideoRef.current && localStreamRef.current) {
            localVideoRef.current.srcObject = localStreamRef.current;
          }
          setIsScreenSharing(false);
        };
      } catch (err) {
        console.warn("Screen sharing cancelled or unavailable", err);
      }
    } else {
      if (localVideoRef.current && localStreamRef.current) {
        localVideoRef.current.srcObject = localStreamRef.current;
      }
      setIsScreenSharing(false);
    }
  };

  // Conclude Call
  const handleEndCall = async () => {
    if (confirm("Are you sure you want to conclude this video consultation?")) {
      try {
        setIsCallActive(false);
        setConnectionStatus("ended");
        if (localStreamRef.current) {
          localStreamRef.current.getTracks().forEach((t) => t.stop());
        }

        await apiClient.post(
          `/api/v1/consultations/${consultationId}/video/end`,
          {}
        );

        setShowPostCallModal(true);
      } catch (err: any) {
        alert(err.message || "Failed to conclude meeting.");
      }
    }
  };

  // Add Action Item
  const handleAddActionItem = () => {
    if (actionItemInput.trim()) {
      setActionItems([...actionItems, actionItemInput.trim()]);
      setActionItemInput("");
    }
  };

  // Save Consultation Notes
  const handleSaveNotes = async () => {
    if (!notesSummary.trim()) {
      alert("Please provide a summary of the advice and consultation.");
      return;
    }
    setSubmittingNotes(true);
    try {
      await apiClient.post(`/api/v1/consultations/${consultationId}/notes`, {
        summary: notesSummary,
        action_items: actionItems,
        client_shared: true,
      });
      setNoteSaved(true);
    } catch (err: any) {
      alert(err.message || "Failed to save consultation notes.");
    } finally {
      setSubmittingNotes(false);
    }
  };

  // Establish New Case
  const handleCreateCase = async () => {
    if (!newCaseTitle.trim()) {
      alert("Please enter a case title.");
      return;
    }
    setSubmittingCase(true);
    try {
      const res = (await apiClient.post(
        `/api/v1/consultations/${consultationId}/create-case`,
        {
          title: newCaseTitle,
          description: newCaseDesc || "Matter created following consultation.",
          practice_area: newCasePracticeArea || undefined,
        }
      )) as { id: string };

      setCaseSuccessMsg("New case matter created and counsel assigned!");
      setTimeout(() => {
        router.push(`/cases/${res.id}`);
      }, 1500);
    } catch (err: any) {
      alert(err.message || "Failed to create case.");
    } finally {
      setSubmittingCase(false);
    }
  };

  // Link to Existing Case
  const handleLinkCase = async () => {
    if (!selectedCaseId) {
      alert("Please select an existing case matter.");
      return;
    }
    setSubmittingCase(true);
    try {
      await apiClient.post(
        `/api/v1/consultations/${consultationId}/link-case`,
        {
          case_id: selectedCaseId,
          assign_lawyer: true,
        }
      );
      setCaseSuccessMsg("Consultation successfully linked to case matter!");
      setTimeout(() => {
        router.push(`/cases/${selectedCaseId}`);
      }, 1500);
    } catch (err: any) {
      alert(err.message || "Failed to link consultation to case.");
    } finally {
      setSubmittingCase(false);
    }
  };

  // Format timer seconds into MM:SS
  const formatTimer = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          backgroundColor: "#090d16",
          color: "#f8fafc",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "Inter, sans-serif",
        }}
      >
        <div
          style={{
            width: "48px",
            height: "48px",
            border: "4px solid rgba(255, 255, 255, 0.1)",
            borderTopColor: "#3b82f6",
            borderRadius: "50%",
            animation: "spin 1s linear infinite",
            marginBottom: "16px",
          }}
        />
        <h2 style={{ fontSize: "18px", fontWeight: 600 }}>
          Authenticating & Entering Secure Video Room...
        </h2>
        <p style={{ color: "#94a3b8", fontSize: "14px", marginTop: "8px" }}>
          Establishing encrypted peer-to-peer connection for consultation #{consultationId.slice(0, 8)}
        </p>
        <style jsx>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          minHeight: "100vh",
          backgroundColor: "#090d16",
          color: "#f8fafc",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "24px",
          fontFamily: "Inter, sans-serif",
        }}
      >
        <div
          style={{
            maxWidth: "480px",
            width: "100%",
            backgroundColor: "#111827",
            borderRadius: "16px",
            padding: "32px",
            border: "1px solid #1f2937",
            textAlign: "center",
          }}
        >
          <div
            style={{
              width: "56px",
              height: "56px",
              backgroundColor: "rgba(239, 68, 68, 0.1)",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 16px",
              color: "#ef4444",
              fontSize: "24px",
            }}
          >
            ✕
          </div>
          <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px" }}>
            Access Restricted
          </h2>
          <p style={{ color: "#94a3b8", fontSize: "14px", lineHeight: 1.5, marginBottom: "24px" }}>
            {error}
          </p>
          <button
            onClick={() => router.push("/dashboard")}
            style={{
              backgroundColor: "#2563eb",
              color: "#ffffff",
              padding: "10px 20px",
              borderRadius: "8px",
              border: "none",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        height: "100vh",
        backgroundColor: "#090d16",
        color: "#f8fafc",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        overflow: "hidden",
      }}
    >
      {/* 1. Header Bar */}
      <header
        style={{
          padding: "12px 24px",
          backgroundColor: "#0d1322",
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          zIndex: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div
              style={{
                width: "10px",
                height: "10px",
                borderRadius: "50%",
                backgroundColor: connectionStatus === "connected" ? "#22c55e" : "#eab308",
                boxShadow:
                  connectionStatus === "connected"
                    ? "0 0 8px rgba(34, 197, 94, 0.6)"
                    : "none",
              }}
            />
            <span style={{ fontWeight: 700, fontSize: "15px", letterSpacing: "0.2px" }}>
              LCC Consultation Room
            </span>
          </div>

          <span
            style={{
              backgroundColor: "rgba(59, 130, 246, 0.12)",
              color: "#60a5fa",
              fontSize: "12px",
              fontWeight: 600,
              padding: "4px 10px",
              borderRadius: "100px",
              border: "1px solid rgba(59, 130, 246, 0.25)",
            }}
          >
            End-to-End Encrypted
          </span>
        </div>

        {/* Center Session Timer */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            padding: "6px 16px",
            borderRadius: "8px",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            fontFamily: "monospace",
            fontSize: "16px",
            fontWeight: 700,
            color: "#38bdf8",
          }}
        >
          <span>⏱</span>
          <span>{formatTimer(secondsElapsed)}</span>
        </div>

        {/* Right Info & End Call */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{ textAlign: "right", fontSize: "12px" }}>
            <div style={{ color: "#f8fafc", fontWeight: 600 }}>
              {joinInfo?.participant_name}
            </div>
            <div style={{ color: "#94a3b8" }}>
              Role: <span style={{ color: "#38bdf8" }}>{joinInfo?.participant_role}</span>
            </div>
          </div>

          <button
            onClick={handleEndCall}
            style={{
              backgroundColor: "#dc2626",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              padding: "8px 16px",
              fontWeight: 600,
              fontSize: "13px",
              cursor: "pointer",
              transition: "background-color 0.2s",
            }}
            onMouseOver={(e) => (e.currentTarget.style.backgroundColor = "#b91c1c")}
            onMouseOut={(e) => (e.currentTarget.style.backgroundColor = "#dc2626")}
          >
            End Call
          </button>
        </div>
      </header>

      {/* 2. Main Video Consultation Stage */}
      <main
        style={{
          flex: 1,
          padding: "20px",
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "20px",
          position: "relative",
          backgroundColor: "#050811",
        }}
      >
        {/* Remote Participant Panel */}
        <div
          style={{
            backgroundColor: "#0d1322",
            borderRadius: "16px",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            position: "relative",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
          }}
        >
          <video
            ref={remoteVideoRef}
            autoPlay
            playsInline
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              position: "absolute",
              inset: 0,
              display: remotePeerActive ? "block" : "none",
            }}
          />

          {!remotePeerActive && (
            <>
              <div
                style={{
                  width: "120px",
                  height: "120px",
                  borderRadius: "50%",
                  backgroundColor: "#1e293b",
                  border: "3px solid #3b82f6",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "44px",
                  fontWeight: 700,
                  color: "#ffffff",
                  marginBottom: "16px",
                }}
              >
                {joinInfo?.participant_role === "CLIENT" ? "⚖️" : "👤"}
              </div>

              <h3 style={{ fontSize: "18px", fontWeight: 600, margin: 0 }}>
                {joinInfo?.participant_role === "CLIENT" ? "Counsel / Advocate" : "Client"}
              </h3>
              <p style={{ color: "#64748b", fontSize: "13px", marginTop: "4px" }}>
                Waiting for remote participant to connect via WebRTC...
              </p>
            </>
          )}

          <div
            style={{
              position: "absolute",
              bottom: "16px",
              left: "16px",
              backgroundColor: "rgba(0, 0, 0, 0.6)",
              backdropFilter: "blur(8px)",
              padding: "6px 12px",
              borderRadius: "8px",
              fontSize: "12px",
              fontWeight: 500,
              display: "flex",
              alignItems: "center",
              gap: "6px",
              zIndex: 2,
            }}
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor: remotePeerActive ? "#22c55e" : "#f59e0b",
              }}
            />
            <span>{remotePeerActive ? "Connected (Live Video Feed)" : "Waiting for Peer"}</span>
          </div>
        </div>

        {/* Local Participant Preview Panel */}
        <div
          style={{
            backgroundColor: "#0d1322",
            borderRadius: "16px",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            position: "relative",
            overflow: "hidden",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
          }}
        >
          {isVideoOff ? (
            <div style={{ textAlign: "center" }}>
              <div
                style={{
                  width: "100px",
                  height: "100px",
                  borderRadius: "50%",
                  backgroundColor: "#1f2937",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "36px",
                  margin: "0 auto 12px",
                }}
              >
                📷
              </div>
              <p style={{ color: "#94a3b8", fontSize: "14px" }}>Camera is disabled</p>
            </div>
          ) : (
            <video
              ref={localVideoRef}
              autoPlay
              playsInline
              muted
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                transform: isScreenSharing ? "none" : "scaleX(-1)",
              }}
            />
          )}

          <div
            style={{
              position: "absolute",
              bottom: "16px",
              left: "16px",
              backgroundColor: "rgba(0, 0, 0, 0.6)",
              backdropFilter: "blur(8px)",
              padding: "6px 12px",
              borderRadius: "8px",
              fontSize: "12px",
              fontWeight: 500,
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span>You ({joinInfo?.participant_name})</span>
            {isMuted && <span style={{ color: "#ef4444" }}>[Muted]</span>}
          </div>
        </div>
      </main>

      {/* 3. Bottom HUD Controller Bar */}
      <footer
        style={{
          padding: "16px 24px",
          backgroundColor: "#0d1322",
          borderTop: "1px solid rgba(255, 255, 255, 0.08)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "16px",
          zIndex: 10,
        }}
      >
        {/* Mute / Unmute */}
        <button
          onClick={toggleMute}
          style={{
            backgroundColor: isMuted ? "#ef4444" : "rgba(255, 255, 255, 0.1)",
            color: "#ffffff",
            border: "none",
            borderRadius: "50%",
            width: "50px",
            height: "50px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            fontSize: "18px",
            transition: "all 0.2s",
          }}
          title={isMuted ? "Unmute Microphone" : "Mute Microphone"}
        >
          {isMuted ? "🔇" : "🎙️"}
        </button>

        {/* Video On / Off */}
        <button
          onClick={toggleVideo}
          style={{
            backgroundColor: isVideoOff ? "#ef4444" : "rgba(255, 255, 255, 0.1)",
            color: "#ffffff",
            border: "none",
            borderRadius: "50%",
            width: "50px",
            height: "50px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            fontSize: "18px",
            transition: "all 0.2s",
          }}
          title={isVideoOff ? "Turn Camera On" : "Turn Camera Off"}
        >
          {isVideoOff ? "🚫" : "📹"}
        </button>

        {/* Screen Share */}
        <button
          onClick={toggleScreenShare}
          style={{
            backgroundColor: isScreenSharing ? "#2563eb" : "rgba(255, 255, 255, 0.1)",
            color: "#ffffff",
            border: "none",
            borderRadius: "50%",
            width: "50px",
            height: "50px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            fontSize: "18px",
            transition: "all 0.2s",
          }}
          title={isScreenSharing ? "Stop Sharing Screen" : "Share Screen"}
        >
          🖥️
        </button>
      </footer>

      {/* 4. Post-Consultation Workflow Modal */}
      {showPostCallModal && (
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
          }}
        >
          <div
            style={{
              backgroundColor: "#111827",
              borderRadius: "20px",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              maxWidth: "600px",
              width: "100%",
              maxHeight: "90vh",
              overflowY: "auto",
              padding: "32px",
              color: "#f8fafc",
            }}
          >
            <div style={{ textAlign: "center", marginBottom: "24px" }}>
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "50%",
                  backgroundColor: "rgba(34, 197, 94, 0.15)",
                  color: "#22c55e",
                  fontSize: "28px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 12px",
                }}
              >
                ✓
              </div>
              <h2 style={{ fontSize: "22px", fontWeight: 700, margin: "0 0 6px" }}>
                Consultation Concluded
              </h2>
              <p style={{ color: "#94a3b8", fontSize: "14px", margin: 0 }}>
                Duration: {formatTimer(secondsElapsed)} • Meeting Record Saved
              </p>
            </div>

            {/* Section A: Notes & Advice */}
            <div
              style={{
                backgroundColor: "#1e293b",
                borderRadius: "12px",
                padding: "20px",
                marginBottom: "20px",
              }}
            >
              <h3 style={{ fontSize: "15px", fontWeight: 600, margin: "0 0 12px" }}>
                📝 Legal Advice & Notes
              </h3>

              <textarea
                value={notesSummary}
                onChange={(e) => setNotesSummary(e.target.value)}
                placeholder="Enter summary of legal advice, statutes referenced, or preliminary assessment..."
                rows={3}
                style={{
                  width: "100%",
                  backgroundColor: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  color: "#f8fafc",
                  padding: "10px",
                  fontSize: "13px",
                  resize: "vertical",
                  marginBottom: "12px",
                }}
              />

              {/* Action items list */}
              <div style={{ marginBottom: "12px" }}>
                <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
                  <input
                    type="text"
                    value={actionItemInput}
                    onChange={(e) => setActionItemInput(e.target.value)}
                    placeholder="Add recommended next action item..."
                    onKeyDown={(e) => e.key === "Enter" && handleAddActionItem()}
                    style={{
                      flex: 1,
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      padding: "8px 12px",
                      fontSize: "13px",
                    }}
                  />
                  <button
                    onClick={handleAddActionItem}
                    style={{
                      backgroundColor: "#3b82f6",
                      color: "#fff",
                      border: "none",
                      borderRadius: "6px",
                      padding: "0 14px",
                      fontWeight: 600,
                      fontSize: "13px",
                      cursor: "pointer",
                    }}
                  >
                    Add
                  </button>
                </div>

                {actionItems.map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      fontSize: "13px",
                      color: "#cbd5e1",
                      backgroundColor: "rgba(255, 255, 255, 0.04)",
                      padding: "6px 10px",
                      borderRadius: "6px",
                      marginBottom: "4px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <span>• {item}</span>
                    <button
                      onClick={() => setActionItems(actionItems.filter((_, i) => i !== idx))}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#ef4444",
                        cursor: "pointer",
                        fontSize: "12px",
                      }}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>

              <button
                onClick={handleSaveNotes}
                disabled={submittingNotes || noteSaved}
                style={{
                  backgroundColor: noteSaved ? "#10b981" : "#2563eb",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  padding: "8px 16px",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: noteSaved ? "default" : "pointer",
                  width: "100%",
                }}
              >
                {noteSaved ? "✓ Notes Saved" : submittingNotes ? "Saving..." : "Save Notes"}
              </button>
            </div>

            {/* Section B: Next Steps / Case Conversion */}
            <div
              style={{
                backgroundColor: "#1e293b",
                borderRadius: "12px",
                padding: "20px",
                marginBottom: "20px",
              }}
            >
              <h3 style={{ fontSize: "15px", fontWeight: 600, margin: "0 0 8px" }}>
                ⚖️ Legal Case Conversion
              </h3>
              <p style={{ color: "#94a3b8", fontSize: "13px", margin: "0 0 14px" }}>
                Would you like to formalize this matter into a tracked legal case?
              </p>

              <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
                <button
                  onClick={() => setPostCallAction("create")}
                  style={{
                    flex: 1,
                    padding: "10px",
                    borderRadius: "8px",
                    border:
                      postCallAction === "create" ? "2px solid #3b82f6" : "1px solid #334155",
                    backgroundColor:
                      postCallAction === "create" ? "rgba(59, 130, 246, 0.15)" : "#0f172a",
                    color: "#f8fafc",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Create New Case
                </button>
                <button
                  onClick={() => setPostCallAction("link")}
                  style={{
                    flex: 1,
                    padding: "10px",
                    borderRadius: "8px",
                    border:
                      postCallAction === "link" ? "2px solid #3b82f6" : "1px solid #334155",
                    backgroundColor:
                      postCallAction === "link" ? "rgba(59, 130, 246, 0.15)" : "#0f172a",
                    color: "#f8fafc",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Link to Existing Case
                </button>
              </div>

              {/* Sub-form: Create Case */}
              {postCallAction === "create" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  <input
                    type="text"
                    value={newCaseTitle}
                    onChange={(e) => setNewCaseTitle(e.target.value)}
                    placeholder="Case Title e.g. Property Boundary Dispute"
                    style={{
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      padding: "8px 12px",
                      fontSize: "13px",
                    }}
                  />
                  <input
                    type="text"
                    value={newCasePracticeArea}
                    onChange={(e) => setNewCasePracticeArea(e.target.value)}
                    placeholder="Practice Area e.g. Civil Law, Criminal Defense"
                    style={{
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      padding: "8px 12px",
                      fontSize: "13px",
                    }}
                  />
                  <textarea
                    value={newCaseDesc}
                    onChange={(e) => setNewCaseDesc(e.target.value)}
                    placeholder="Brief description of the matter..."
                    rows={2}
                    style={{
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      padding: "8px 12px",
                      fontSize: "13px",
                    }}
                  />
                  <button
                    onClick={handleCreateCase}
                    disabled={submittingCase}
                    style={{
                      backgroundColor: "#2563eb",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: "6px",
                      padding: "10px",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    {submittingCase ? "Creating Case..." : "Establish Case Matter"}
                  </button>
                </div>
              )}

              {/* Sub-form: Link Existing Case */}
              {postCallAction === "link" && (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  <select
                    value={selectedCaseId}
                    onChange={(e) => setSelectedCaseId(e.target.value)}
                    style={{
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      padding: "8px 12px",
                      fontSize: "13px",
                    }}
                  >
                    <option value="">Select an ongoing case matter...</option>
                    {existingCases.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.title} ({c.status})
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={handleLinkCase}
                    disabled={submittingCase}
                    style={{
                      backgroundColor: "#2563eb",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: "6px",
                      padding: "10px",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    {submittingCase ? "Linking..." : "Link to Selected Case"}
                  </button>
                </div>
              )}

              {caseSuccessMsg && (
                <div
                  style={{
                    color: "#22c55e",
                    fontSize: "13px",
                    marginTop: "10px",
                    fontWeight: 600,
                  }}
                >
                  ✓ {caseSuccessMsg}
                </div>
              )}
            </div>

            {/* Exit to dashboard */}
            <div style={{ textAlign: "center" }}>
              <button
                onClick={() => router.push("/dashboard")}
                style={{
                  backgroundColor: "transparent",
                  color: "#94a3b8",
                  border: "none",
                  fontSize: "14px",
                  cursor: "pointer",
                  textDecoration: "underline",
                }}
              >
                Back to Dashboard
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
