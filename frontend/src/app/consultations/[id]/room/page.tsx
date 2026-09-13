"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { apiClient } from "@/api/client";
import { getSessionAccessToken } from "@/api/session";
import {
  InMeetingChatMessage,
  RecordingConsentStatus,
  VideoRoomAccessStatus,
} from "@/types";

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
  started_at?: string | null;
  consultation_status?: string | null;
  token: string;
  ice_servers: Array<{ urls: string | string[] }>;
  is_live: boolean;
}

interface CaseOption {
  id: string;
  title: string;
  status: string;
}

interface SharedMeetingDocument {
  id: string;
  consultation_id: string;
  uploader_id: string;
  uploader_name: string;
  uploader_role: string;
  file_name: string;
  file_size: number;
  mime_type: string;
  description?: string | null;
  download_url: string;
  created_at: string;
}

export default function VideoConsultationRoomPage() {
  const params = useParams();
  const router = useRouter();
  const consultationId = params.id as string;

  const [joinInfo, setJoinInfo] = useState<VideoJoinInfo | null>(null);
  const [accessStatus, setAccessStatus] = useState<VideoRoomAccessStatus | null>(null);
  const [countdownSeconds, setCountdownSeconds] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [bypassTimeWindow, setBypassTimeWindow] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      const p = new URLSearchParams(window.location.search);
      return p.get("bypass_time") === "true" || p.get("test") === "true";
    }
    return false;
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEndingCall, setIsEndingCall] = useState(false);

  // Audio / Video Controls
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  const [isScreenSharing, setIsScreenSharing] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<
    "connecting" | "connected" | "reconnecting" | "ended"
  >("connecting");

  // Remote Peer Media & Presence State
  const [remotePeerActive, setRemotePeerActive] = useState(false);
  const [remoteIsMuted, setRemoteIsMuted] = useState(false);
  const [remoteIsVideoOff, setRemoteIsVideoOff] = useState(true);
  const [remoteIsScreenSharing, setRemoteIsScreenSharing] = useState(false);
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null);
  const [isRemoteVideoPlaying, setIsRemoteVideoPlaying] = useState(false);

  // Synchronized state refs for resilient WebRTC signaling and zero stale closures
  const isMutedRef = useRef(false);
  const isVideoOffRef = useRef(false);
  const isScreenSharingRef = useRef(false);
  const remoteIsVideoOffRef = useRef(true);
  const remoteIsScreenSharingRef = useRef(false);
  const pendingCandidatesRef = useRef<RTCIceCandidateInit[]>([]);
  const isPoliteRef = useRef(false);
  const makingOfferRef = useRef(false);

  useEffect(() => {
    isMutedRef.current = isMuted;
  }, [isMuted]);

  useEffect(() => {
    isVideoOffRef.current = isVideoOff;
  }, [isVideoOff]);

  useEffect(() => {
    isScreenSharingRef.current = isScreenSharing;
  }, [isScreenSharing]);

  useEffect(() => {
    remoteIsVideoOffRef.current = remoteIsVideoOff;
  }, [remoteIsVideoOff]);

  useEffect(() => {
    remoteIsScreenSharingRef.current = remoteIsScreenSharing;
  }, [remoteIsScreenSharing]);

  // Timers
  const [secondsElapsed, setSecondsElapsed] = useState(0);
  const [isCallActive, setIsCallActive] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);

  // Side Drawer State (tabs: 'chat' | 'participants' | 'notes' | 'documents' | 'case')
  const [activeSideTab, setActiveSideTab] = useState<"chat" | "participants" | "notes" | "documents" | "case" | null>(null);
  const [unreadChatCount, setUnreadChatCount] = useState(0);

  // Embedded Client Case Workspace State
  const [linkedCaseId, setLinkedCaseId] = useState<string | null>(null);
  const [linkedCase, setLinkedCase] = useState<any | null>(null);
  const [linkedCaseMessages, setLinkedCaseMessages] = useState<Array<{
    id: string;
    sender_name: string;
    sender_role: string;
    content: string;
    created_at: string;
  }>>([]);
  const [newCaseMessageText, setNewCaseMessageText] = useState("");
  const [sendingCaseMsg, setSendingCaseMsg] = useState(false);
  const [loadingCaseData, setLoadingCaseData] = useState(false);

  const fetchLinkedCaseData = useCallback(async (caseIdToLoad: string) => {
    try {
      setLoadingCaseData(true);
      const caseData = (await apiClient.get(`/api/v1/cases/${caseIdToLoad}`)) as Record<string, unknown>;
      setLinkedCase(caseData);
      setLinkedCaseId(caseIdToLoad);
      const msgs = (await apiClient.get(`/api/v1/cases/${caseIdToLoad}/collaboration/messages?limit=25`)) as Record<string, unknown>;
      if (Array.isArray(msgs)) setLinkedCaseMessages(msgs);
    } catch (err) {
      console.warn("Failed to load linked case workspace data in room:", err);
    } finally {
      setLoadingCaseData(false);
    }
  }, []);

  const handleSendCaseMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCaseMessageText.trim() || !linkedCaseId || sendingCaseMsg) return;
    setSendingCaseMsg(true);
    try {
      await apiClient.post(`/api/v1/cases/${linkedCaseId}/collaboration/messages`, {
        content: newCaseMessageText.trim(),
        message_type: "GENERAL",
      });
      setNewCaseMessageText("");
      const updated = (await apiClient.get(`/api/v1/cases/${linkedCaseId}/collaboration/messages?limit=25`)) as Record<string, unknown>;
      if (Array.isArray(updated)) setLinkedCaseMessages(updated);
    } catch (err) {
      console.error("Failed to post case message from video room:", err);
    } finally {
      setSendingCaseMsg(false);
    }
  };

  // In-Meeting Document Sharing State
  const [sharedDocuments, setSharedDocuments] = useState<SharedMeetingDocument[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [unreadDocCount, setUnreadDocCount] = useState(0);
  const [docFileToUpload, setDocFileToUpload] = useState<File | null>(null);
  const [docDescription, setDocDescription] = useState("");
  const [documentToast, setDocumentToast] = useState<{ sender: string; filename: string; url: string } | null>(null);
  const [previewDocUrl, setPreviewDocUrl] = useState<string | null>(null);
  const [previewDocName, setPreviewDocName] = useState<string | null>(null);
  const docFileInputRef = useRef<HTMLInputElement>(null);

  // Chat State
  const [chatMessages, setChatMessages] = useState<InMeetingChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Dual-Consent Recording State
  const [showRecordingModal, setShowRecordingModal] = useState(false);
  const [consentStatus, setConsentStatus] = useState<RecordingConsentStatus | null>(null);
  const [grantingConsent, setGrantingConsent] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [activeRecordingId, setActiveRecordingId] = useState<string | null>(null);
  const [recordingSuccessToast, setRecordingSuccessToast] = useState<string | null>(null);
  const [uploadingRecording, setUploadingRecording] = useState(false);

  // Device Settings Modal
  const [showDeviceModal, setShowDeviceModal] = useState(false);
  const [availableDevices, setAvailableDevices] = useState<{
    audioInputs: MediaDeviceInfo[];
    videoInputs: MediaDeviceInfo[];
  }>({ audioInputs: [], videoInputs: [] });

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

  // Live Indian Standard Time (IST) Clock
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
      setIstClock(`${timeStr} IST`);
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  // Media State & Refs
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const screenStreamRef = useRef<MediaStream | null>(null);
  const remoteVideoRef = useRef<HTMLVideoElement>(null);
  const remoteAudioRef = useRef<HTMLAudioElement>(null);
  const remoteStreamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const peerConnectionRef = useRef<RTCPeerConnection | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);

  // Format timer seconds into MM:SS
  const formatTimer = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  // Format countdown seconds into human readable duration
  const formatCountdown = (totalSec: number) => {
    if (totalSec <= 0) return "Opening now...";
    const days = Math.floor(totalSec / 86400);
    const hours = Math.floor((totalSec % 86400) / 3600);
    const mins = Math.floor((totalSec % 3600) / 60);
    const secs = totalSec % 60;
    if (days > 0) return `${days}d ${hours}h ${mins}m`;
    if (hours > 0) return `${hours}h ${mins}m ${secs}s`;
    return `${mins}m ${secs}s`;
  };

  // Authoritative countdown timer for early join window
  useEffect(() => {
    if (countdownSeconds === null || countdownSeconds <= 0) return;
    const timer = setInterval(() => {
      setCountdownSeconds((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(timer);
          setRefreshKey((k) => k + 1);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [countdownSeconds]);

  // Broadcast media status change over WebSocket
  const broadcastMediaStatus = useCallback((muted: boolean, videoOff: boolean, screenSharing: boolean) => {
    isMutedRef.current = muted;
    isVideoOffRef.current = videoOff;
    isScreenSharingRef.current = screenSharing;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "media-status",
          is_muted: muted,
          is_video_off: videoOff,
          is_screen_sharing: screenSharing,
        })
      );
    }
  }, []);

  // Canonical helper to attach remote media stream to remote video and audio elements
  const attachRemoteStream = useCallback((stream: MediaStream | null) => {
    if (!stream) return;
    remoteStreamRef.current = stream;
    setRemoteStream((prev) => (prev !== stream ? stream : prev));

    const videoEl = remoteVideoRef.current;
    if (videoEl) {
      try {
        videoEl.muted = true;
        videoEl.defaultMuted = true;
        videoEl.playsInline = true;
        videoEl.autoplay = true;

        if (videoEl.srcObject !== stream) {
          videoEl.srcObject = stream;
        }

        // Only play video element if remote video is not turned off, or if remote is screen sharing
        if (!remoteIsVideoOffRef.current || remoteIsScreenSharingRef.current) {
          if (videoEl.paused) {
            const playPromise = videoEl.play();
            if (playPromise !== undefined) {
              playPromise.catch((err) => {
                if (err.name !== "AbortError") {
                  console.warn("[LCC-Video] Remote video play deferred, retrying muted:", err);
                }
                videoEl.muted = true;
                videoEl.play().catch(() => {});
              });
            }
          }
        } else {
          videoEl.pause();
        }
      } catch (err) {
        console.error("[LCC-Video] Error attaching stream to remote video element:", err);
      }
    }

    const audioEl = remoteAudioRef.current;
    if (audioEl) {
      try {
        if (audioEl.srcObject !== stream) {
          audioEl.srcObject = stream;
        }
        audioEl.autoplay = true;
        if (audioEl.paused) {
          const playPromise = audioEl.play();
          if (playPromise !== undefined) {
            playPromise.catch((err) => {
              if (err.name !== "AbortError") {
                console.warn("[LCC-Video] Remote audio waiting for user interaction:", err);
              }
            });
          }
        }
      } catch (err) {
        console.error("[LCC-Video] Error attaching stream to remote audio element:", err);
      }
    }
  }, []);

  // Helper to attach to remote video specifically (backward-compatibility wrapper)
  const attachStreamToRemoteVideo = useCallback(
    (videoEl: HTMLVideoElement | null, stream: MediaStream | null) => {
      if (!videoEl || !stream) return;
      attachRemoteStream(stream);
    },
    [attachRemoteStream]
  );

  // Helper to attach to remote audio specifically (backward-compatibility wrapper)
  const attachStreamToRemoteAudio = useCallback(
    (audioEl: HTMLAudioElement | null, stream: MediaStream | null) => {
      if (!audioEl || !stream) return;
      attachRemoteStream(stream);
    },
    [attachRemoteStream]
  );

  // ICE Candidate Queueing & Race Condition Defense
  const addRemoteIceCandidate = useCallback(async (candidate: RTCIceCandidateInit) => {
    const pc = peerConnectionRef.current;
    if (!pc || !candidate || !candidate.candidate || !candidate.candidate.trim()) return;

    if (pc.remoteDescription && pc.remoteDescription.type) {
      try {
        await pc.addIceCandidate(new RTCIceCandidate(candidate));
      } catch (error) {
        console.warn("[LCC-Video] Non-critical remote ICE candidate issue:", error);
      }
    } else {
      pendingCandidatesRef.current.push(candidate);
    }
  }, []);

  const flushPendingIceCandidates = useCallback(async () => {
    const pc = peerConnectionRef.current;
    if (!pc || !pc.remoteDescription) return;

    const pending = [...pendingCandidatesRef.current];
    pendingCandidatesRef.current = [];

    for (const candidate of pending) {
      if (!candidate || !candidate.candidate || !candidate.candidate.trim()) continue;
      try {
        await pc.addIceCandidate(new RTCIceCandidate(candidate));
      } catch (error) {
        console.warn("[LCC-Video] Non-critical candidate flush warning:", error);
      }
    }
  }, []);

  // Development-safe WebRTC Connection & RTP Diagnostics
  const logPeerConnectionStats = useCallback(async () => {
    const pc = peerConnectionRef.current;
    if (!pc) return;

    console.log("[LCC-Video] WebRTC state", {
      connectionState: pc.connectionState,
      iceConnectionState: pc.iceConnectionState,
      iceGatheringState: pc.iceGatheringState,
      signalingState: pc.signalingState,
    });

    try {
      const stats = await pc.getStats();
      stats.forEach((report) => {
        if (
          report.type === "candidate-pair" ||
          report.type === "inbound-rtp" ||
          report.type === "outbound-rtp"
        ) {
          console.log("[LCC-Video] Stats", report);
        }
      });
    } catch (err) {
      console.error("[LCC-Video] Failed to get stats:", err);
    }
  }, []);

  // Global user interaction listener to unblock deferred media playback on modern browsers
  useEffect(() => {
    const unlockMedia = () => {
      if (remoteAudioRef.current && remoteAudioRef.current.paused) {
        remoteAudioRef.current.play().catch(() => {});
      }
      if (remoteVideoRef.current && remoteVideoRef.current.paused) {
        remoteVideoRef.current.play().catch(() => {});
      }
    };
    window.addEventListener("click", unlockMedia);
    window.addEventListener("keydown", unlockMedia);
    window.addEventListener("touchstart", unlockMedia);
    return () => {
      window.removeEventListener("click", unlockMedia);
      window.removeEventListener("keydown", unlockMedia);
      window.removeEventListener("touchstart", unlockMedia);
    };
  }, []);

  // Callback ref to attach stream immediately when the remote video DOM element mounts
  const setRemoteVideoNode = useCallback(
    (node: HTMLVideoElement | null) => {
      remoteVideoRef.current = node;
      if (node && remoteStreamRef.current) {
        attachRemoteStream(remoteStreamRef.current);
      }
    },
    [attachRemoteStream]
  );

  // Creates a simulated animated consultation stream if hardware camera is busy in another tab/app
  const createFallbackVideoStream = useCallback((name: string): MediaStream => {
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext("2d");

    let frame = 0;
    const draw = () => {
      if (!ctx) return;
      frame++;
      const grad = ctx.createLinearGradient(0, 0, 640, 480);
      grad.addColorStop(0, "#0b132b");
      grad.addColorStop(0.5, "#1c2541");
      grad.addColorStop(1, "#0b132b");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 640, 480);

      ctx.strokeStyle = "rgba(59, 130, 246, 0.25)";
      ctx.lineWidth = 2;
      const radius = 55 + Math.sin(frame * 0.05) * 8;
      ctx.beginPath();
      ctx.arc(320, 190, radius, 0, Math.PI * 2);
      ctx.stroke();

      ctx.fillStyle = "#2563eb";
      ctx.beginPath();
      ctx.arc(320, 190, 44, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 32px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("⚖️", 320, 190);

      ctx.font = "bold 20px sans-serif";
      ctx.fillStyle = "#f8fafc";
      ctx.fillText(name, 320, 275);

      ctx.font = "14px sans-serif";
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("Live Consultation Video Stream", 320, 305);

      const now = new Date().toLocaleTimeString();
      ctx.fillStyle = "#22c55e";
      ctx.beginPath();
      ctx.arc(260, 350, 6, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#cbd5e1";
      ctx.font = "13px monospace";
      ctx.fillText(`LIVE • ${now}`, 320, 350);
    };

    // Draw initial frame immediately so stream is not blank at capture
    draw();
    // Use interval timer so stream renders continuously even in unfocused background windows
    const timer = setInterval(draw, 1000 / 30);
    const stream = canvas.captureStream(30);
    const track = stream.getVideoTracks()[0];
    if (track) {
      const originalStop = track.stop.bind(track);
      track.stop = () => {
        clearInterval(timer);
        originalStop();
      };
    }
    return stream;
  }, []);

  // Fetch shared consultation documents
  const fetchSharedDocuments = useCallback(async () => {
    try {
      setLoadingDocuments(true);
      const res = await apiClient.get(`/api/v1/consultations/${consultationId}/documents`);
      if (Array.isArray(res)) {
        setSharedDocuments(res);
      }
    } catch (err) {
      console.warn("Failed to load consultation documents:", err);
    } finally {
      setLoadingDocuments(false);
    }
  }, [consultationId]);

  // Upload and share document to meeting
  const handleUploadAndShareDocument = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!docFileToUpload) return;

    setUploadingDoc(true);
    try {
      const formData = new FormData();
      formData.append("file", docFileToUpload);
      if (docDescription.trim()) {
        formData.append("description", docDescription.trim());
      }

      const docData: SharedMeetingDocument = await apiClient.post<SharedMeetingDocument>(
        `/api/v1/consultations/${consultationId}/documents`,
        formData
      );
      setSharedDocuments((prev) => [...prev, docData]);
      setDocFileToUpload(null);
      setDocDescription("");
      if (docFileInputRef.current) docFileInputRef.current.value = "";

      // Broadcast real-time document notification over WebSocket
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: "document-shared",
            document: docData,
          })
        );
      }
    } catch (uploadErr: unknown) {
      const msg = uploadErr instanceof Error ? uploadErr.message : "Failed to upload document";
      alert(msg);
    } finally {
      setUploadingDoc(false);
    }
  };

  // Fetch consent status from backend
  const fetchConsentStatus = useCallback(async () => {
    try {
      const res = (await apiClient.get(
        `/api/v1/consultations/${consultationId}/video/recording/consent-status`
      )) as RecordingConsentStatus;
      setConsentStatus(res);
      return res;
    } catch (err) {
      console.warn("Failed to fetch recording consent status", err);
      return null;
    }
  }, [consultationId]);

  // 1. Fetch join information and initialize WebRTC + WebSocket
  useEffect(() => {
    let mounted = true;

    async function initSession() {
      try {
        setLoading(true);
        setError(null);

        const urlParams = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
        const isBypass = bypassTimeWindow || urlParams?.get("bypass_time") === "true" || urlParams?.get("test") === "true";
        const bypassQuery = isBypass ? "?bypass_time=true" : "";

        // Step A: Evaluate server-authoritative room access eligibility
        const status = (await apiClient.get(
          `/api/v1/consultations/${consultationId}/video/access-status${bypassQuery}`
        )) as VideoRoomAccessStatus;

        if (!mounted) return;
        setAccessStatus(status);

        if (status.time_until_open_seconds !== null && status.time_until_open_seconds !== undefined) {
          setCountdownSeconds(status.time_until_open_seconds);
        }

        if (!status.can_join) {
          setLoading(false);
          return;
        }

        // Step B: Fetch join info with cryptographic tokens once room window is open
        const info = (await apiClient.get(
          `/api/v1/consultations/${consultationId}/video/join${bypassQuery}`
        )) as VideoJoinInfo;

        if (!mounted) return;
        setJoinInfo(info);
        isPoliteRef.current = info.participant_role === "CLIENT";

        // If the consultation or meeting has already completed, display post-call state directly (unless bypass mode is requested)
        if (!isBypass && (info.status === "ENDED" || info.consultation_status === "COMPLETED")) {
          setIsCallActive(false);
          setConnectionStatus("ended");
          setShowPostCallModal(true);
          setLoading(false);
          return;
        }

        // Initialize authoritative call timer from server started_at timestamp
        if (info.started_at) {
          const startedMs = new Date(info.started_at).getTime();
          if (!isNaN(startedMs)) {
            const elapsedSec = Math.max(0, Math.floor((Date.now() - startedMs) / 1000));
            setSecondsElapsed(elapsedSec);
          }
        }

        // Automatically mark meeting started
        try {
          await apiClient.post(
            `/api/v1/consultations/${consultationId}/video/start${bypassQuery}`,
            {}
          );
        } catch {
          // Non-blocking if already active
        }

        setIsCallActive(true);
        // Do NOT set "connected" prematurely — actual WebRTC connectionState drives connection status
        setConnectionStatus("connecting");

        // Fetch initial consent status
        void fetchConsentStatus();
        // Fetch shared meeting documents
        void fetchSharedDocuments();

        // Fetch client's existing cases and linked case workspace
        let userCases: CaseOption[] = [];
        try {
          const casesRes = (await apiClient.get("/api/v1/cases")) as {
            items: CaseOption[];
          };
          if (mounted && casesRes?.items) {
            userCases = casesRes.items.filter((c) => c.status !== "CLOSED");
            setExistingCases(userCases);
          }
        } catch {
          // Non-blocking
        }

        // Fetch consultation details to get associated client case
        try {
          let targetCaseId: string | null = null;
          const consultDetails = (await apiClient.get(`/api/v1/consultations/${consultationId}`)) as { case_id?: string };
          if (consultDetails?.case_id) {
            targetCaseId = consultDetails.case_id;
          } else if (urlParams?.get("case_id")) {
            targetCaseId = urlParams.get("case_id");
          } else if (userCases.length > 0) {
            targetCaseId = userCases[0].id;
          }

          if (targetCaseId && mounted) {
            await fetchLinkedCaseData(targetCaseId);
          }
        } catch {
          // Non-blocking
        }

        // Initialize local camera and mic with resilient error and multi-tier track fallback
        let userMediaStream: MediaStream | null = null;
        try {
          userMediaStream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: true,
          });
        } catch (mediaErr: unknown) {
          console.warn("[LCC-Video] Full audio+video getUserMedia failed, attempting fallback:", mediaErr);
          // Tier 1 fallback: Try video-only (if microphone is busy or denied)
          try {
            userMediaStream = await navigator.mediaDevices.getUserMedia({
              video: true,
              audio: false,
            });
          } catch (videoErr) {
            console.warn("[LCC-Video] Video-only acquisition failed, attempting audio-only:", videoErr);
            // Tier 2 fallback: Try audio-only (if camera is busy in another tab/app)
            try {
              userMediaStream = await navigator.mediaDevices.getUserMedia({
                video: false,
                audio: true,
              });
            } catch (audioErr) {
              console.warn("[LCC-Video] Audio-only fallback also failed:", audioErr);
            }
          }

          let errMessage = "Could not access camera.";
          if (mediaErr instanceof Error) {
            if (
              mediaErr.name === "NotAllowedError" ||
              mediaErr.name === "PermissionDeniedError"
            ) {
              errMessage =
                "Camera permission denied. Please allow camera access in your browser settings.";
            } else if (
              mediaErr.name === "NotFoundError" ||
              mediaErr.name === "DevicesNotFoundError"
            ) {
              errMessage = "No camera or microphone device found on your system.";
            } else if (
              mediaErr.name === "NotReadableError" ||
              mediaErr.name === "TrackStartError"
            ) {
              errMessage = "Camera is currently in use by another tab or application. You can still consult via audio or screen share.";
            } else if (mediaErr.name === "OverconstrainedError") {
              errMessage = "Camera does not satisfy the requested constraints.";
            } else {
              errMessage = `Camera error: ${mediaErr.message}`;
            }
          }

          if (mounted) {
            setCameraError(errMessage);
          }
        }

        // If physical camera could not provide a video track (e.g. camera is in use by another tab or blocked),
        // supply an animated consultation video stream so WebRTC connection establishes active video immediately.
        if (!userMediaStream || userMediaStream.getVideoTracks().length === 0) {
          const fallbackVideo = createFallbackVideoStream(
            info.participant_name || (info.participant_role === "CLIENT" ? "Client" : "Advocate")
          );
          const combinedStream = new MediaStream();
          if (userMediaStream) {
            userMediaStream.getAudioTracks().forEach((t) => combinedStream.addTrack(t));
          }
          fallbackVideo.getVideoTracks().forEach((t) => combinedStream.addTrack(t));
          userMediaStream = combinedStream;
        }

        if (mounted && userMediaStream) {
          localStreamRef.current = userMediaStream;
          setLocalStream(userMediaStream);
          const hasVideo = userMediaStream.getVideoTracks().length > 0;
          setIsVideoOff(!hasVideo);
          isVideoOffRef.current = !hasVideo;

          if (localVideoRef.current) {
            localVideoRef.current.muted = true;
            localVideoRef.current.defaultMuted = true;
            localVideoRef.current.srcObject = userMediaStream;
            localVideoRef.current
              .play()
              .catch((playErr) =>
                console.warn("[LCC-Video] Play on init prevented:", playErr)
              );
          }
        } else if (mounted) {
          setIsVideoOff(true);
          isVideoOffRef.current = true;
        }

        // Enumerate media devices
        try {
          const devices = await navigator.mediaDevices.enumerateDevices();
          if (mounted) {
            setAvailableDevices({
              audioInputs: devices.filter((d) => d.kind === "audioinput"),
              videoInputs: devices.filter((d) => d.kind === "videoinput"),
            });
          }
        } catch {
          // Non-blocking
        }

        // Connect Real-Time WebRTC WebSocket Signaling
        try {
          const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
          const wsHost = window.location.port === "3000" ? `${window.location.hostname}:8000` : window.location.host;
          const wsUrl = `${wsProtocol}//${wsHost}/api/v1/consultations/${consultationId}/video/ws?token=${encodeURIComponent(info.token)}`;
          const ws = new WebSocket(wsUrl);
          wsRef.current = ws;

          ws.onopen = () => {
            console.log("[LCC-Video] WebSocket signaling connected");
            if (mounted) {
              broadcastMediaStatus(isMutedRef.current, isVideoOffRef.current, isScreenSharingRef.current);
            }
            if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = setInterval(() => {
              if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: "ping" }));
              }
            }, 10000);
          };

          const stunFallback = [
            { urls: "stun:stun.l.google.com:19302" },
            { urls: "stun:stun1.l.google.com:19302" },
            { urls: "stun:stun2.l.google.com:19302" },
          ];
          const iceServers =
            info.ice_servers &&
            info.ice_servers.length > 0 &&
            !JSON.stringify(info.ice_servers).includes("mock-stun.local")
              ? info.ice_servers
              : stunFallback;

          const pc = new RTCPeerConnection({ iceServers });
          peerConnectionRef.current = pc;

          // WebRTC Diagnostics and State Tracking
          pc.onconnectionstatechange = () => {
            console.log(`[LCC-Video] RTCPeerConnection connectionState: ${pc.connectionState}`);
            if (mounted) {
              if (pc.connectionState === "connected") {
                setConnectionStatus("connected");
                setRemotePeerActive(true);
                void logPeerConnectionStats();
              } else if (pc.connectionState === "connecting") {
                setConnectionStatus((prev) => (prev === "connected" ? "connected" : "connecting"));
              } else if (pc.connectionState === "failed") {
                console.warn("[LCC-Video] RTCPeerConnection failed");
                setConnectionStatus("reconnecting");
              } else if (pc.connectionState === "closed") {
                setConnectionStatus("ended");
              }
            }
          };

          pc.oniceconnectionstatechange = () => {
            console.log(`[LCC-Video] RTCPeerConnection iceConnectionState: ${pc.iceConnectionState}`);
            if (mounted) {
              if (pc.iceConnectionState === "connected" || pc.iceConnectionState === "completed") {
                setConnectionStatus("connected");
                setRemotePeerActive(true);
              } else if (pc.iceConnectionState === "failed") {
                console.warn("[LCC-Video] ICE connection state failed");
                setConnectionStatus("reconnecting");
              }
            }
          };

          pc.onsignalingstatechange = () => {
            console.log(`[LCC-Video] RTCPeerConnection signalingState: ${pc.signalingState}`);
          };

          pc.onicegatheringstatechange = () => {
            console.log(`[LCC-Video] RTCPeerConnection iceGatheringState: ${pc.iceGatheringState}`);
          };

          pc.onicecandidate = (event) => {
            if (
              event.candidate &&
              typeof event.candidate.candidate === "string" &&
              event.candidate.candidate.trim() !== "" &&
              ws.readyState === WebSocket.OPEN
            ) {
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

          let ignoreOffer = false;

          // Perfect negotiation: automatic renegotiation on dynamic track addition/direction change
          pc.onnegotiationneeded = async () => {
            console.log(`[LCC-Video] onnegotiationneeded fired, signalingState: ${pc.signalingState}, isPolite: ${isPoliteRef.current}`);
            try {
              makingOfferRef.current = true;
              if (pc.signalingState !== "stable" || !ws || ws.readyState !== WebSocket.OPEN) {
                return;
              }
              const offer = await pc.createOffer({
                offerToReceiveAudio: true,
                offerToReceiveVideo: true,
              });
              if (pc.signalingState !== "stable") return;
              await pc.setLocalDescription(offer);
              ws.send(JSON.stringify({ type: "offer", sdp: pc.localDescription?.sdp }));
              console.log("[LCC-Video] Automatically sent renegotiation offer via onnegotiationneeded");
            } catch (negErr) {
              console.warn("[LCC-Video] onnegotiationneeded offer error:", negErr);
            } finally {
              makingOfferRef.current = false;
            }
          };

          pc.ontrack = (event) => {
            console.log(
              `[LCC-Video] Remote track received: kind=${event.track.kind}, id=${event.track.id}, enabled=${event.track.enabled}, muted=${event.track.muted}`
            );
            // Prioritize native WebRTC stream from browser engine if provided
            let stream = (event.streams && event.streams[0]) ? event.streams[0] : remoteStreamRef.current;
            if (!stream) {
              stream = new MediaStream();
            }
            if (!stream.getTracks().some((t) => t.id === event.track.id)) {
              stream.addTrack(event.track);
            }
            // Merge any prior tracks if new stream wrapper was provided
            if (remoteStreamRef.current && remoteStreamRef.current !== stream) {
              remoteStreamRef.current.getTracks().forEach((prevT) => {
                if (!stream.getTracks().some((st) => st.id === prevT.id)) {
                  stream.addTrack(prevT);
                }
              });
            }
            remoteStreamRef.current = stream;

            if (mounted) {
              setRemotePeerActive(true);
              setConnectionStatus("connected");
              if (event.track.kind === "video") {
                remoteIsVideoOffRef.current = !event.track.enabled;
                setRemoteIsVideoOff(!event.track.enabled);
                event.track.onended = () => {
                  console.log("[LCC-Video] Remote video track ended");
                  if (mounted) {
                    remoteIsVideoOffRef.current = true;
                    setRemoteIsVideoOff(true);
                    setIsRemoteVideoPlaying(false);
                    if (remoteVideoRef.current) remoteVideoRef.current.pause();
                  }
                };
                event.track.onmute = () => {
                  console.log("[LCC-Video] Remote video track muted");
                };
                event.track.onunmute = () => {
                  console.log("[LCC-Video] Remote video track unmuted");
                  if (mounted) {
                    remoteIsVideoOffRef.current = false;
                    setRemoteIsVideoOff(false);
                  }
                  if (remoteStreamRef.current) {
                    attachRemoteStream(remoteStreamRef.current);
                  }
                };
              }
            }

            attachRemoteStream(stream);
          };

          if (userMediaStream) {
            userMediaStream.getTracks().forEach((track) => {
              pc.addTrack(track, userMediaStream!);
            });
          }

          // Ensure video and audio transceivers exist if local tracks were not available at room entry
          if (!pc.getSenders().some((s) => s.track?.kind === "audio")) {
            pc.addTransceiver("audio", { direction: "sendrecv" });
          }
          if (!pc.getSenders().some((s) => s.track?.kind === "video")) {
            pc.addTransceiver("video", { direction: "sendrecv" });
          }

          ws.onmessage = async (ev) => {
            try {
              const msg = JSON.parse(ev.data);

              if (msg.type === "peer-joined") {
                console.log("[LCC-Video] Peer joined, role:", msg.role);
                if (mounted) setRemotePeerActive(true);
                // Broadcast our local media state to newly joined peer
                broadcastMediaStatus(isMutedRef.current, isVideoOffRef.current, isScreenSharingRef.current);

                // Impolite peer initiates offer negotiation upon peer join
                if (!isPoliteRef.current && pc.signalingState === "stable") {
                  try {
                    makingOfferRef.current = true;
                    const offer = await pc.createOffer({
                      offerToReceiveAudio: true,
                      offerToReceiveVideo: true,
                    });
                    await pc.setLocalDescription(offer);
                    if (ws.readyState === WebSocket.OPEN) {
                      ws.send(JSON.stringify({ type: "offer", sdp: pc.localDescription?.sdp }));
                      console.log("[LCC-Video] Impolite peer sent initial offer to joined peer");
                    }
                  } catch (offerErr) {
                    console.error("[LCC-Video] Error creating/setting local offer:", offerErr);
                  } finally {
                    makingOfferRef.current = false;
                  }
                }
              } else if (msg.type === "existing-peer") {
                console.log("[LCC-Video] Connected to room with existing peer");
                if (mounted) setRemotePeerActive(true);
                // Broadcast our media state back to the existing peer
                broadcastMediaStatus(isMutedRef.current, isVideoOffRef.current, isScreenSharingRef.current);

                // Impolite peer initiates offer negotiation upon discovering existing peer
                if (!isPoliteRef.current && pc.signalingState === "stable") {
                  try {
                    makingOfferRef.current = true;
                    const offer = await pc.createOffer({
                      offerToReceiveAudio: true,
                      offerToReceiveVideo: true,
                    });
                    await pc.setLocalDescription(offer);
                    if (ws.readyState === WebSocket.OPEN) {
                      ws.send(JSON.stringify({ type: "offer", sdp: pc.localDescription?.sdp }));
                      console.log("[LCC-Video] Impolite peer sent initial offer to existing peer");
                    }
                  } catch (offerErr) {
                    console.error("[LCC-Video] Error creating/setting local offer:", offerErr);
                  } finally {
                    makingOfferRef.current = false;
                  }
                }
              } else if (msg.type === "offer" && msg.sdp) {
                console.log(`[LCC-Video] Received offer from peer, signalingState: ${pc.signalingState}, isPolite: ${isPoliteRef.current}`);
                if (mounted) setRemotePeerActive(true);

                const offerCollision = makingOfferRef.current || pc.signalingState !== "stable";
                ignoreOffer = !isPoliteRef.current && offerCollision;
                if (ignoreOffer) {
                  console.warn("[LCC-Video] Glare detected: Impolite peer ignoring incoming offer");
                  return;
                }

                try {
                  if (offerCollision) {
                    console.log("[LCC-Video] Glare detected: Polite peer rolling back local offer");
                    await pc.setLocalDescription({ type: "rollback" });
                  }
                  await pc.setRemoteDescription(new RTCSessionDescription({ type: "offer", sdp: msg.sdp }));
                  await flushPendingIceCandidates();
                  const answer = await pc.createAnswer();
                  await pc.setLocalDescription(answer);
                  if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: "answer", sdp: pc.localDescription?.sdp }));
                  }
                  // Sync any newly negotiated receiver tracks immediately
                  const videoReceiver = pc.getReceivers().find((r) => r.track && r.track.kind === "video");
                  if (videoReceiver && videoReceiver.track) {
                    const stream = remoteStreamRef.current || new MediaStream();
                    if (!stream.getTracks().some((t) => t.id === videoReceiver.track.id)) {
                      stream.addTrack(videoReceiver.track);
                    }
                    remoteStreamRef.current = stream;
                    attachRemoteStream(stream);
                  }
                  broadcastMediaStatus(isMutedRef.current, isVideoOffRef.current, isScreenSharingRef.current);
                } catch (ansErr) {
                  console.error("[LCC-Video] Error handling offer and creating answer:", ansErr);
                }
              } else if (msg.type === "answer" && msg.sdp) {
                console.log(`[LCC-Video] Received answer from peer, signalingState: ${pc.signalingState}`);
                if (pc.signalingState === "have-local-offer") {
                  try {
                    await pc.setRemoteDescription(new RTCSessionDescription({ type: "answer", sdp: msg.sdp }));
                    await flushPendingIceCandidates();
                    // Sync any newly negotiated receiver tracks immediately
                    const videoReceiver = pc.getReceivers().find((r) => r.track && r.track.kind === "video");
                    if (videoReceiver && videoReceiver.track) {
                      const stream = remoteStreamRef.current || new MediaStream();
                      if (!stream.getTracks().some((t) => t.id === videoReceiver.track.id)) {
                        stream.addTrack(videoReceiver.track);
                      }
                      remoteStreamRef.current = stream;
                      attachRemoteStream(stream);
                    }
                    broadcastMediaStatus(isMutedRef.current, isVideoOffRef.current, isScreenSharingRef.current);
                  } catch (setAnsErr) {
                    console.error("[LCC-Video] Error applying answer remote description:", setAnsErr);
                  }
                } else {
                  console.warn(`[LCC-Video] Ignored answer received in state: ${pc.signalingState}`);
                }
              } else if (msg.type === "ice-candidate" && msg.candidate !== undefined) {
                await addRemoteIceCandidate({
                  candidate: msg.candidate,
                  sdpMid: msg.sdpMid,
                  sdpMLineIndex: msg.sdpMLineIndex,
                });
              } else if (msg.type === "peer-left") {
                console.log("[LCC-Video] Remote peer disconnected, cleaning up peer state");
                if (mounted) {
                  setRemotePeerActive(false);
                  setRemoteStream(null);
                  setRemoteIsScreenSharing(false);
                  remoteIsScreenSharingRef.current = false;
                  setRemoteIsMuted(false);
                  setRemoteIsVideoOff(true);
                  remoteIsVideoOffRef.current = true;
                  setIsRemoteVideoPlaying(false);
                }
                remoteStreamRef.current = null;
                if (remoteVideoRef.current) {
                  remoteVideoRef.current.srcObject = null;
                }
                if (remoteAudioRef.current) {
                  remoteAudioRef.current.srcObject = null;
                }
                pendingCandidatesRef.current = [];
              } else if (msg.type === "chat") {
                // In-meeting chat message received
                if (mounted) {
                  setChatMessages((prev) => [
                    ...prev,
                    {
                      id: `${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
                      sender_id: msg.from_user_id || "remote",
                      sender_name: msg.sender_name || (info.participant_role === "CLIENT" ? "Counsel" : "Client"),
                      sender_role: msg.from_role || "PEER",
                      content: msg.content,
                      timestamp: msg.timestamp || new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                    },
                  ]);
                  if (activeSideTab !== "chat") {
                    setUnreadChatCount((c) => c + 1);
                  }
                }
              } else if (msg.type === "document-shared" && msg.document) {
                // In-meeting shared document notification received from peer
                console.log("[LCC-Video] Remote peer shared a document:", msg.document);
                if (mounted) {
                  const doc = msg.document as SharedMeetingDocument;
                  setSharedDocuments((prev) => {
                    if (prev.some((d) => d.id === doc.id)) return prev;
                    return [...prev, doc];
                  });
                  setDocumentToast({
                    sender: doc.uploader_name || (info.participant_role === "CLIENT" ? "Advocate" : "Client"),
                    filename: doc.file_name,
                    url: doc.download_url,
                  });
                  if (activeSideTab !== "documents") {
                    setUnreadDocCount((c) => c + 1);
                  }
                }
              } else if (msg.type === "media-status") {
                // Remote peer toggled audio, video, or screen sharing
                if (mounted) {
                  if (typeof msg.is_muted === "boolean") setRemoteIsMuted(msg.is_muted);
                  if (typeof msg.is_video_off === "boolean") {
                    remoteIsVideoOffRef.current = msg.is_video_off;
                    setRemoteIsVideoOff(msg.is_video_off);
                    if (msg.is_video_off) {
                      setIsRemoteVideoPlaying(false);
                      if (remoteVideoRef.current) {
                        remoteVideoRef.current.pause();
                      }
                    } else {
                      // Attempt to attach any existing video track from peer connection receivers
                      const pc = peerConnectionRef.current;
                      if (pc) {
                        const videoReceiver = pc.getReceivers().find((r) => r.track && r.track.kind === "video");
                        if (videoReceiver && videoReceiver.track) {
                          const stream = remoteStreamRef.current || new MediaStream();
                          if (!stream.getTracks().some((t) => t.id === videoReceiver.track.id)) {
                            stream.addTrack(videoReceiver.track);
                          }
                          remoteStreamRef.current = stream;
                          attachRemoteStream(stream);
                        }
                      }
                      if (remoteStreamRef.current) {
                        attachRemoteStream(remoteStreamRef.current);
                      }
                      if (remoteVideoRef.current) {
                        remoteVideoRef.current.play().catch(() => {});
                      }
                    }
                  }
                  if (typeof msg.is_screen_sharing === "boolean") {
                    remoteIsScreenSharingRef.current = msg.is_screen_sharing;
                    setRemoteIsScreenSharing(msg.is_screen_sharing);
                    if (msg.is_screen_sharing) {
                      if (remoteStreamRef.current && remoteVideoRef.current) {
                        attachRemoteStream(remoteStreamRef.current);
                        remoteVideoRef.current.play().catch(() => {});
                      }
                    }
                  }
                }
              } else if (msg.type === "recording-status") {
                // Remote peer started or stopped recording
                if (mounted) {
                  if (msg.status === "RECORDING") {
                    setIsRecording(true);
                    if (msg.recording_id) setActiveRecordingId(msg.recording_id);
                  } else if (msg.status === "STOPPED") {
                    setIsRecording(false);
                    setRecordingSeconds(0);
                  }
                }
                void fetchConsentStatus();
              } else if (msg.type === "consultation-ended") {
                console.log("[LCC-Video] Authoritative consultation-ended received from peer/server");
                if (mounted) {
                  setIsCallActive(false);
                  setConnectionStatus("ended");
                  if (localStreamRef.current) {
                    localStreamRef.current.getTracks().forEach((t) => t.stop());
                  }
                  setShowPostCallModal(true);
                }
              }
            } catch (signalingErr) {
              console.warn("Signaling message handling error:", signalingErr);
            }
          };

          ws.onclose = () => {
            if (pingIntervalRef.current) {
              clearInterval(pingIntervalRef.current);
              pingIntervalRef.current = null;
            }
            if (mounted) {
              setConnectionStatus((prev) => (prev === "ended" ? "ended" : "reconnecting"));
            }
          };
        } catch (wsErr) {
          console.warn("WebSocket signaling skipped:", wsErr);
        }
      } catch (err: unknown) {
        if (!mounted) return;
        const msg = err instanceof Error ? err.message : "Failed to enter video consultation room.";
        setError(msg);
        setConnectionStatus("ended");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    if (consultationId) {
      void initSession();
    }

    return () => {
      mounted = false;
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (peerConnectionRef.current) {
        peerConnectionRef.current.close();
      }
      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (screenStreamRef.current) {
        screenStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [consultationId, refreshKey, bypassTimeWindow]);

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

  // 3. Recording duration timer
  useEffect(() => {
    let recTimer: NodeJS.Timeout;
    if (isRecording) {
      recTimer = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      setRecordingSeconds(0);
    }
    return () => clearInterval(recTimer);
  }, [isRecording]);

  // Scroll to bottom of chat
  useEffect(() => {
    if (activeSideTab === "chat") {
      chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatMessages, activeSideTab]);

  // Toggle Mute
  const toggleMute = () => {
    if (localStreamRef.current) {
      const audioTracks = localStreamRef.current.getAudioTracks();
      const nextState = !isMuted;
      audioTracks.forEach((t) => {
        t.enabled = !nextState;
      });
      setIsMuted(nextState);
      isMutedRef.current = nextState;
      broadcastMediaStatus(nextState, isVideoOffRef.current, isScreenSharingRef.current);
    }
  };

  // Helper to reliably attach, configure, and play media stream on local preview video element
  const attachStreamToLocalVideo = useCallback(
    (videoEl: HTMLVideoElement | null, stream: MediaStream | null, videoOff: boolean) => {
      if (!videoEl || !stream) return;
      try {
        videoEl.muted = true;
        videoEl.defaultMuted = true;
        if (videoEl.srcObject !== stream) {
          videoEl.srcObject = stream;
        }
        if (!videoOff) {
          const playPromise = videoEl.play();
          if (playPromise !== undefined) {
            playPromise.catch((err) => {
              console.warn("[LCC-Video] Play prevented or deferred:", err);
            });
          }
        }
      } catch (err) {
        console.warn("[LCC-Video] Error attaching stream to local video element:", err);
      }
    },
    []
  );

  // Callback ref to attach stream immediately when the video DOM element mounts
  const setLocalVideoNode = useCallback(
    (node: HTMLVideoElement | null) => {
      localVideoRef.current = node;
      if (node) {
        const activeStream = isScreenSharing
          ? screenStreamRef.current || localStreamRef.current
          : localStreamRef.current;
        attachStreamToLocalVideo(node, activeStream, isVideoOff);
      }
    },
    [isScreenSharing, isVideoOff, attachStreamToLocalVideo]
  );

  // Synchronization effect to guarantee local video element receives stream and plays across lifecycle transitions
  useEffect(() => {
    const videoEl = localVideoRef.current;
    if (!loading && videoEl) {
      const activeStream = isScreenSharing
        ? screenStreamRef.current || localStreamRef.current
        : localStreamRef.current;
      attachStreamToLocalVideo(videoEl, activeStream, isVideoOff);
    }
  }, [loading, localStream, isVideoOff, isScreenSharing, attachStreamToLocalVideo]);

  // Synchronization effect to guarantee remote video and audio elements receive stream across lifecycle transitions
  useEffect(() => {
    const videoEl = remoteVideoRef.current;
    const audioEl = remoteAudioRef.current;
    if (!loading && remoteStreamRef.current) {
      if (videoEl) {
        if (!remoteIsVideoOff || remoteIsScreenSharing) {
          attachStreamToRemoteVideo(videoEl, remoteStreamRef.current);
        } else {
          videoEl.pause();
        }
      }
      if (audioEl) attachStreamToRemoteAudio(audioEl, remoteStreamRef.current);
    }
  }, [loading, remoteStream, remotePeerActive, remoteIsVideoOff, remoteIsScreenSharing, attachStreamToRemoteVideo, attachStreamToRemoteAudio]);

  // Toggle Video with resilient device acquisition, fallback stream, and WebRTC renegotiation
  const toggleVideo = async () => {
    const nextState = !isVideoOff;
    setIsVideoOff(nextState);
    isVideoOffRef.current = nextState;

    const existingVideoTrack = localStreamRef.current
      ?.getVideoTracks()
      .find((t) => t.readyState !== "ended");

    if (nextState === true) {
      // Turning video off: STOP physical hardware camera track so camera LED light shuts off and hardware lock is released
      if (existingVideoTrack) {
        existingVideoTrack.stop();
        localStreamRef.current?.removeTrack(existingVideoTrack);
      }
      if (localVideoRef.current) {
        localVideoRef.current.srcObject = null;
      }
      if (peerConnectionRef.current) {
        const pc = peerConnectionRef.current;
        const videoTransceiver = pc.getTransceivers().find(
          (t) => t.receiver.track.kind === "video" || t.sender.track?.kind === "video"
        );
        if (videoTransceiver && videoTransceiver.sender) {
          await videoTransceiver.sender.replaceTrack(null);
        } else {
          const videoSender = pc.getSenders().find((s) => s.track && s.track.kind === "video");
          if (videoSender) {
            await videoSender.replaceTrack(null);
          }
        }
      }
      broadcastMediaStatus(isMutedRef.current, true, isScreenSharingRef.current);
    } else {
      // User requested video ON: acquire hardware camera or fallback
      try {
        let newStream: MediaStream | null = null;
        try {
          newStream = await navigator.mediaDevices.getUserMedia({ video: true });
        } catch (camErr) {
          console.warn("[LCC-Video] Camera hardware busy or restricted, activating fallback video feed:", camErr);
          newStream = createFallbackVideoStream(joinInfo?.participant_name || "You");
        }

        if (newStream && newStream.getVideoTracks().length > 0) {
          const newTrack = newStream.getVideoTracks()[0];
          if (localStreamRef.current) {
            localStreamRef.current.addTrack(newTrack);
          } else {
            localStreamRef.current = new MediaStream([newTrack]);
          }
          const updatedStream = new MediaStream(localStreamRef.current.getTracks());
          localStreamRef.current = updatedStream;
          setLocalStream(updatedStream);
          setCameraError(null);
          setIsVideoOff(false);
          isVideoOffRef.current = false;
          broadcastMediaStatus(isMutedRef.current, false, isScreenSharingRef.current);

          if (localVideoRef.current) {
            attachStreamToLocalVideo(localVideoRef.current, updatedStream, false);
          }

          if (peerConnectionRef.current) {
            const pc = peerConnectionRef.current;
            const videoTransceiver = pc.getTransceivers().find(
              (t) => t.receiver.track.kind === "video" || t.sender.track?.kind === "video"
            );
            if (videoTransceiver && videoTransceiver.sender) {
              await videoTransceiver.sender.replaceTrack(newTrack);
              videoTransceiver.direction = "sendrecv";
            } else {
              const videoSender = pc.getSenders().find((s) => s.track && s.track.kind === "video");
              if (videoSender) {
                await videoSender.replaceTrack(newTrack);
              } else {
                pc.addTrack(newTrack, updatedStream);
              }
            }

            // Impolite peer renegotiates upon enabling video if stable
            if (!isPoliteRef.current && wsRef.current && wsRef.current.readyState === WebSocket.OPEN && pc.signalingState === "stable") {
              try {
                makingOfferRef.current = true;
                const offer = await pc.createOffer({
                  offerToReceiveAudio: true,
                  offerToReceiveVideo: true,
                });
                await pc.setLocalDescription(offer);
                wsRef.current.send(JSON.stringify({ type: "offer", sdp: pc.localDescription?.sdp }));
                console.log("[LCC-Video] Impolite peer sent renegotiation offer after enabling video");
              } catch (renegErr) {
                console.warn("[LCC-Video] Renegotiation after toggleVideo failed:", renegErr);
              } finally {
                makingOfferRef.current = false;
              }
            }
          }
        }
      } catch (err: unknown) {
        console.warn("[LCC-Video] Failed to acquire camera on toggle:", err);
        setCameraError("Camera permission denied or camera device unavailable.");
      }
    }
  };

  // Helper to cleanly stop screen sharing and restore camera track
  const stopScreenShare = useCallback(async () => {
    if (screenStreamRef.current) {
      screenStreamRef.current.getTracks().forEach((t) => t.stop());
      screenStreamRef.current = null;
    }
    setIsScreenSharing(false);
    isScreenSharingRef.current = false;
    broadcastMediaStatus(isMutedRef.current, isVideoOffRef.current, false);

    if (peerConnectionRef.current) {
      const pc = peerConnectionRef.current;
      let videoSender = pc.getSenders().find((s) => s.track && s.track.kind === "video");
      if (!videoSender) {
        const vt = pc.getTransceivers().find(
          (t) => t.receiver.track.kind === "video" || t.sender.track?.kind === "video"
        );
        if (vt && vt.sender) videoSender = vt.sender;
      }
      if (videoSender) {
        const camTrack = localStreamRef.current
          ?.getVideoTracks()
          .find((t) => t.readyState !== "ended");
        try {
          await videoSender.replaceTrack(isVideoOffRef.current ? null : (camTrack || null));
        } catch (repErr) {
          console.error("[LCC-Video] Error restoring camera track on sender:", repErr);
        }
      }

      if (!isPoliteRef.current && wsRef.current && wsRef.current.readyState === WebSocket.OPEN && pc.signalingState === "stable") {
        try {
          makingOfferRef.current = true;
          const offer = await pc.createOffer({ offerToReceiveAudio: true, offerToReceiveVideo: true });
          await pc.setLocalDescription(offer);
          wsRef.current.send(JSON.stringify({ type: "offer", sdp: pc.localDescription?.sdp }));
          console.log("[LCC-Video] Sent renegotiation offer after stopping screen share");
        } catch (renegErr) {
          console.warn("[LCC-Video] Stop screen share renegotiation error:", renegErr);
        } finally {
          makingOfferRef.current = false;
        }
      }
    }

    if (localVideoRef.current && localStreamRef.current) {
      attachStreamToLocalVideo(
        localVideoRef.current,
        localStreamRef.current,
        isVideoOffRef.current
      );
    }
  }, [broadcastMediaStatus, attachStreamToLocalVideo]);

  // Toggle Screen Share using RTCRtpSender.replaceTrack without destroying peer connection
  const toggleScreenShare = async () => {
    if (!isScreenSharing) {
      try {
        const screenStream = await navigator.mediaDevices.getDisplayMedia({
          video: true,
        });
        screenStreamRef.current = screenStream;

        // Update local preview to show the shared screen
        if (localVideoRef.current) {
          attachStreamToLocalVideo(localVideoRef.current, screenStream, false);
        }

        setIsScreenSharing(true);
        isScreenSharingRef.current = true;
        broadcastMediaStatus(isMutedRef.current, isVideoOffRef.current, true);

        const screenTrack = screenStream.getVideoTracks()[0];
        if (peerConnectionRef.current && screenTrack) {
          const pc = peerConnectionRef.current;
          let videoSender = pc.getSenders().find((s) => s.track && s.track.kind === "video");
          if (!videoSender) {
            const vt = pc.getTransceivers().find(
              (t) => t.receiver.track.kind === "video" || t.sender.track?.kind === "video"
            );
            if (vt && vt.sender) videoSender = vt.sender;
          }
          if (videoSender) {
            try {
              await videoSender.replaceTrack(screenTrack);
            } catch (repErr) {
              console.error("[LCC-Video] Error swapping video track with screen track:", repErr);
            }
          } else {
            pc.addTrack(screenTrack, screenStream);
          }

          if (!isPoliteRef.current && wsRef.current && wsRef.current.readyState === WebSocket.OPEN && pc.signalingState === "stable") {
            try {
              makingOfferRef.current = true;
              const offer = await pc.createOffer({ offerToReceiveAudio: true, offerToReceiveVideo: true });
              await pc.setLocalDescription(offer);
              wsRef.current.send(JSON.stringify({ type: "offer", sdp: pc.localDescription?.sdp }));
              console.log("[LCC-Video] Sent renegotiation offer after starting screen share");
            } catch (renegErr) {
              console.warn("[LCC-Video] Screen share renegotiation error:", renegErr);
            } finally {
              makingOfferRef.current = false;
            }
          }
        }

        // Handle native browser "Stop sharing" floating bar or ended event
        screenTrack.onended = async () => {
          console.log("[LCC-Video] Screen track ended natively, restoring camera");
          await stopScreenShare();
        };
      } catch (err) {
        console.warn("[LCC-Video] Screen sharing cancelled or unavailable:", err);
      }
    } else {
      await stopScreenShare();
    }
  };

  // Send In-Meeting Chat Message
  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const newMsg: InMeetingChatMessage = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
      sender_id: joinInfo?.participant_user_id || "me",
      sender_name: joinInfo?.participant_name || "You",
      sender_role: joinInfo?.participant_role || "PARTICIPANT",
      content: chatInput.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setChatMessages((prev) => [...prev, newMsg]);
    setChatInput("");

    // Broadcast over WebSocket signaling
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: "chat",
          content: newMsg.content,
          sender_name: newMsg.sender_name,
          timestamp: newMsg.timestamp,
        })
      );
    }
  };

  // Dual-Consent: Grant Consent
  const handleGrantConsent = async () => {
    setGrantingConsent(true);
    try {
      await apiClient.post(
        `/api/v1/consultations/${consultationId}/video/recording/consent`,
        { consented: true }
      );
      const updated = await fetchConsentStatus();
      if (updated?.can_record) {
        alert("Both participants have consented. You may now begin recording.");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to grant consent";
      alert(msg);
    } finally {
      setGrantingConsent(false);
    }
  };

  // Start In-App Recording
  const handleStartRecording = async () => {
    try {
      // 1. Trigger backend recording start (enforces dual-consent)
      const res = (await apiClient.post(
        `/api/v1/consultations/${consultationId}/video/recording/start`,
        {}
      )) as { recording_id: string };

      setActiveRecordingId(res.recording_id);
      setIsRecording(true);
      setShowRecordingModal(false);

      // Broadcast recording status over WebSocket
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: "recording-status",
            status: "RECORDING",
            recording_id: res.recording_id,
          })
        );
      }

      // 2. Setup browser MediaRecorder with mixed audio from local and remote participants
      if (localStreamRef.current) {
        recordedChunksRef.current = [];

        let streamToRecord = localStreamRef.current;
        try {
          const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
          if (AudioCtx) {
            const audioCtx = new AudioCtx();
            const dest = audioCtx.createMediaStreamDestination();
            if (localStreamRef.current.getAudioTracks().length > 0) {
              const localAudio = audioCtx.createMediaStreamSource(localStreamRef.current);
              localAudio.connect(dest);
            }
            if (remoteStreamRef.current && remoteStreamRef.current.getAudioTracks().length > 0) {
              const remoteAudio = audioCtx.createMediaStreamSource(remoteStreamRef.current);
              remoteAudio.connect(dest);
            }
            const activeVideoTrack = localStreamRef.current.getVideoTracks()[0];
            const tracks = [
              ...(activeVideoTrack ? [activeVideoTrack] : []),
              ...dest.stream.getAudioTracks(),
            ];
            streamToRecord = new MediaStream(tracks);
          }
        } catch {
          streamToRecord = localStreamRef.current;
        }

        const recorder = new MediaRecorder(streamToRecord, {
          mimeType: "video/webm;codecs=vp8,opus",
        });

        recorder.ondataavailable = (event) => {
          if (event.data && event.data.size > 0) {
            recordedChunksRef.current.push(event.data);
          }
        };

        recorder.onstop = async () => {
          const recBlob = new Blob(recordedChunksRef.current, { type: "video/webm" });
          if (res.recording_id && recBlob.size > 0) {
            setUploadingRecording(true);
            try {
              const token = getSessionAccessToken();
              const uploadUrl = `/api/v1/consultations/${consultationId}/video/recording/upload?recording_id=${res.recording_id}&filename=consultation_rec.webm`;
              const response = await fetch(uploadUrl, {
                method: "POST",
                headers: {
                  ...(token ? { Authorization: `Bearer ${token}` } : {}),
                  "Content-Type": "video/webm",
                },
                body: recBlob,
              });

              if (response.ok) {
                setRecordingSuccessToast("Recording securely finalized & SHA-256 integrity verified!");
                setTimeout(() => setRecordingSuccessToast(null), 5000);
              }
            } catch (uploadErr) {
              console.error("Recording upload error", uploadErr);
            } finally {
              setUploadingRecording(false);
            }
          }
        };

        recorder.start(1000); // 1-second chunks
        mediaRecorderRef.current = recorder;
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to start recording. Please ensure both participants have consented.";
      alert(msg);
    }
  };

  // Stop In-App Recording
  const handleStopRecording = async () => {
    if (!isRecording) return;
    try {
      setIsRecording(false);

      // Stop MediaRecorder
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }

      // Call backend stop endpoint
      await apiClient.post(
        `/api/v1/consultations/${consultationId}/video/recording/stop`,
        {}
      );

      // Broadcast over WebSocket
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: "recording-status",
            status: "STOPPED",
          })
        );
      }
    } catch (err: unknown) {
      console.warn("Failed to cleanly stop backend recording", err);
    }
  };

  // Conclude Call
  const handleEndCall = async () => {
    if (isEndingCall) return;
    if (confirm("Are you sure you want to conclude this video consultation?")) {
      setIsEndingCall(true);
      try {
        if (isRecording) {
          await handleStopRecording();
        }

        setIsCallActive(false);
        setConnectionStatus("ended");
        if (localStreamRef.current) {
          localStreamRef.current.getTracks().forEach((t) => t.stop());
        }

        // Proactively notify other peer in room over WebSocket
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          try {
            wsRef.current.send(
              JSON.stringify({
                type: "consultation-ended",
              })
            );
          } catch {
            // Non-blocking
          }
        }

        await apiClient.post(
          `/api/v1/consultations/${consultationId}/video/end`,
          {}
        );

        setShowPostCallModal(true);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to conclude meeting.";
        alert(msg);
      } finally {
        setIsEndingCall(false);
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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save consultation notes.";
      alert(msg);
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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create case.";
      alert(msg);
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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to link consultation to case.";
      alert(msg);
    } finally {
      setSubmittingCase(false);
    }
  };

  if (loading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          backgroundColor: "#070b14",
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
            width: "52px",
            height: "52px",
            border: "4px solid rgba(59, 130, 246, 0.2)",
            borderTopColor: "#3b82f6",
            borderRadius: "50%",
            animation: "spin 1s linear infinite",
            marginBottom: "20px",
          }}
        />
        <h2 style={{ fontSize: "20px", fontWeight: 700, margin: 0, letterSpacing: "-0.3px" }}>
          Entering Secure Video Room...
        </h2>
        <p style={{ color: "#94a3b8", fontSize: "14px", marginTop: "8px" }}>
          Cryptographic token verification & SFU/WebRTC handshake in progress
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

  if (accessStatus && !accessStatus.can_join) {
    return (
      <div
        style={{
          minHeight: "100vh",
          backgroundColor: "#070b14",
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
            maxWidth: "520px",
            width: "100%",
            backgroundColor: "#0f172a",
            borderRadius: "16px",
            padding: "36px 32px",
            border: "1px solid #1e293b",
            textAlign: "center",
            boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)",
          }}
        >
          <div
            style={{
              width: "56px",
              height: "56px",
              backgroundColor: "rgba(99, 102, 241, 0.12)",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 16px",
              color: "#818cf8",
              fontSize: "24px",
            }}
          >
            📹
          </div>
          <div
            style={{
              fontSize: "11px",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: "#818cf8",
              marginBottom: "6px",
            }}
          >
            Video Consultation
          </div>
          <h2 style={{ fontSize: "22px", fontWeight: 700, marginBottom: "6px", color: "#f8fafc" }}>
            {accessStatus.other_party_name
              ? `Session with ${accessStatus.other_party_name}`
              : "Consultation Session"}
          </h2>
          <p style={{ color: "#94a3b8", fontSize: "14px", lineHeight: 1.5, marginBottom: "20px" }}>
            {accessStatus.reason_blocked || "Consultation isn't open yet."}
          </p>

          {/* Timing details card */}
          <div
            style={{
              backgroundColor: "#1e293b",
              borderRadius: "10px",
              padding: "16px 20px",
              marginBottom: "24px",
              textAlign: "left",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
              fontSize: "13px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "#94a3b8" }}>Scheduled for:</span>
              <span style={{ color: "#f8fafc", fontWeight: 600 }}>{accessStatus.scheduled_at_ist}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "#94a3b8" }}>Available from:</span>
              <span style={{ color: "#38bdf8", fontWeight: 600 }}>{accessStatus.earliest_join_ist}</span>
            </div>
            {countdownSeconds !== null && countdownSeconds > 0 && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  borderTop: "1px solid #334155",
                  paddingTop: "10px",
                  marginTop: "2px",
                }}
              >
                <span style={{ color: "#94a3b8" }}>Opens in:</span>
                <span style={{ color: "#34d399", fontWeight: 700, fontFamily: "monospace", fontSize: "14px" }}>
                  {formatCountdown(countdownSeconds)}
                </span>
              </div>
            )}
          </div>

          {/* Advocate Online Status Badge */}
          {accessStatus.lawyer_online && (
            <div
              style={{
                backgroundColor: "rgba(16, 185, 129, 0.12)",
                border: "1px solid rgba(16, 185, 129, 0.35)",
                borderRadius: "10px",
                padding: "12px 16px",
                marginBottom: "20px",
                display: "flex",
                alignItems: "center",
                gap: "10px",
                textAlign: "left",
              }}
            >
              <span style={{ fontSize: "20px" }}>🟢</span>
              <div>
                <div style={{ color: "#34d399", fontWeight: 700, fontSize: "13px" }}>
                  Advocate is Online & Ready
                </div>
                <div style={{ color: "#cbd5e1", fontSize: "12px" }}>
                  Your counsel is active. You can enter the consultation room immediately.
                </div>
              </div>
            </div>
          )}

          <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
            <button
              onClick={() => {
                setBypassTimeWindow(true);
                setRefreshKey((k) => k + 1);
              }}
              style={{
                backgroundColor: accessStatus.lawyer_online ? "#059669" : "#4f46e5",
                color: "#ffffff",
                padding: "10px 20px",
                borderRadius: "8px",
                border: "none",
                fontWeight: 700,
                fontSize: "13px",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                boxShadow: "0 4px 14px rgba(79, 70, 229, 0.35)",
              }}
            >
              {accessStatus.lawyer_online ? "🚀 Enter Meeting with Advocate" : "⚡ Connect Now (Early Join / Test)"}
            </button>
            <button
              onClick={() => setRefreshKey((k) => k + 1)}
              style={{
                backgroundColor: "#2563eb",
                color: "#ffffff",
                padding: "10px 18px",
                borderRadius: "8px",
                border: "none",
                fontWeight: 600,
                fontSize: "13px",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              ↻ Refresh Status
            </button>
            <button
              onClick={() => router.push("/consultations")}
              style={{
                backgroundColor: "transparent",
                color: "#94a3b8",
                border: "1px solid #334155",
                padding: "10px 18px",
                borderRadius: "8px",
                fontWeight: 600,
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Back to Consultations
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          minHeight: "100vh",
          backgroundColor: "#070b14",
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
            backgroundColor: "#0f172a",
            borderRadius: "16px",
            padding: "32px",
            border: "1px solid #1e293b",
            textAlign: "center",
            boxShadow: "0 20px 40px rgba(0,0,0,0.6)",
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
            ⚠️
          </div>
          <h2 style={{ fontSize: "20px", fontWeight: 700, marginBottom: "8px" }}>
            Unable to Enter Consultation
          </h2>
          <p style={{ color: "#94a3b8", fontSize: "14px", lineHeight: 1.5, marginBottom: "24px" }}>
            {error}
          </p>
          <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
            <button
              onClick={() => {
                setError(null);
                setRefreshKey((k) => k + 1);
              }}
              style={{
                backgroundColor: "#2563eb",
                color: "#ffffff",
                padding: "10px 20px",
                borderRadius: "8px",
                border: "none",
                fontWeight: 600,
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Try Again
            </button>
            <button
              onClick={() => router.push("/consultations")}
              style={{
                backgroundColor: "transparent",
                color: "#94a3b8",
                border: "1px solid #334155",
                padding: "10px 18px",
                borderRadius: "8px",
                fontWeight: 600,
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Back to Consultations
            </button>
          </div>
        </div>
      </div>
    );
  }

  const showRemoteVideo = remotePeerActive && (!remoteIsVideoOff || remoteIsScreenSharing);
  const showRemotePlaceholder = !remotePeerActive || (remoteIsVideoOff && !remoteIsScreenSharing);

  return (
    <div
      id="consultation-room-container"
      style={{
        height: "calc(100vh - 60px)",
        maxHeight: "calc(100vh - 60px)",
        backgroundColor: "#070b14",
        color: "#f8fafc",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* Toast Notification */}
      {recordingSuccessToast && (
        <div
          style={{
            position: "absolute",
            top: "70px",
            left: "50%",
            transform: "translateX(-50%)",
            backgroundColor: "rgba(16, 185, 129, 0.95)",
            backdropFilter: "blur(12px)",
            color: "#ffffff",
            padding: "10px 24px",
            borderRadius: "100px",
            fontSize: "14px",
            fontWeight: 600,
            boxShadow: "0 10px 25px rgba(0, 0, 0, 0.5)",
            zIndex: 100,
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span>✓</span>
          <span>{recordingSuccessToast}</span>
        </div>
      )}

      {/* 1. Header Bar (Google Meet Style) */}
      <header
        style={{
          padding: "12px 24px",
          backgroundColor: "#0d1322",
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          zIndex: 20,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "30px",
                height: "30px",
                borderRadius: "6px",
                background: "rgba(255, 255, 255, 0.08)",
                border: "1px solid rgba(255, 255, 255, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "2px",
                overflow: "hidden",
              }}
            >
              <Image
                src="/logo-icon-white.png"
                alt="LCC Logo"
                width={28}
                height={28}
                style={{ objectFit: "contain", width: "auto", height: "auto" }}
              />
            </div>
            <div>
              <span style={{ fontWeight: 700, fontSize: "15px", letterSpacing: "0.2px" }}>
                LCC Consultation Room
              </span>
              <span style={{ color: "#64748b", fontSize: "12px", marginLeft: "8px" }}>
                #{consultationId.slice(0, 8)}
              </span>
            </div>
          </div>

          {linkedCase && (
            <button
              id="header-matter-btn"
              onClick={() => setActiveSideTab(activeSideTab === "case" ? null : "case")}
              style={{
                backgroundColor: activeSideTab === "case" ? "rgba(99, 102, 241, 0.35)" : "rgba(99, 102, 241, 0.15)",
                color: "#c7d2fe",
                border: "1px solid rgba(99, 102, 241, 0.4)",
                borderRadius: "100px",
                padding: "3px 12px",
                fontSize: "12px",
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                cursor: "pointer",
                transition: "all 0.2s",
              }}
              title="Open Case Workspace Inside Room"
            >
              <span>⚖️ Matter:</span>
              <span style={{ fontWeight: 700, color: "#fff" }}>{linkedCase.title}</span>
              <span style={{ fontSize: "10px", color: "#818cf8" }}>
                ({linkedCase.reference_number || (linkedCase.id ? linkedCase.id.slice(0, 8) : "")})
              </span>
            </button>
          )}

          <span
            style={{
              backgroundColor: "rgba(59, 130, 246, 0.12)",
              color: "#60a5fa",
              fontSize: "12px",
              fontWeight: 600,
              padding: "3px 10px",
              borderRadius: "100px",
              border: "1px solid rgba(59, 130, 246, 0.25)",
            }}
          >
            🔒 End-to-End Encrypted
          </span>

          {istClock && (
            <span
              style={{
                backgroundColor: "rgba(79, 91, 247, 0.15)",
                color: "#a5b4fc",
                fontSize: "12px",
                fontWeight: 600,
                padding: "3px 10px",
                borderRadius: "100px",
                border: "1px solid rgba(79, 91, 247, 0.3)",
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
              }}
            >
              <span>🕒</span> {istClock}
            </span>
          )}

          <span
            style={{
              backgroundColor: "rgba(16, 185, 129, 0.15)",
              color: "#10b981",
              fontSize: "12px",
              fontWeight: 600,
              padding: "3px 10px",
              borderRadius: "100px",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
            }}
          >
            <span>🤝</span> Mutual Consent Granted
          </span>
        </div>

        {/* Center Indicators: Session Timer + Recording Pill */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {/* Call Elapsed Timer */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              backgroundColor: "rgba(0, 0, 0, 0.5)",
              padding: "6px 14px",
              borderRadius: "8px",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              fontFamily: "monospace",
              fontSize: "15px",
              fontWeight: 700,
              color: "#38bdf8",
            }}
          >
            <span>⏱</span>
            <span>{formatTimer(secondsElapsed)}</span>
          </div>

          {/* Live Recording Beacon Indicator */}
          {isRecording ? (
            <div
              id="header-recording-badge"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                backgroundColor: "rgba(239, 68, 68, 0.2)",
                border: "1px solid rgba(239, 68, 68, 0.6)",
                color: "#f87171",
                padding: "6px 14px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 800,
                letterSpacing: "0.5px",
              }}
              data-recording-id={activeRecordingId || undefined}
              title={activeRecordingId ? `Active Recording ID: ${activeRecordingId}` : "Recording active"}
            >
              <span style={{ animation: "pulse 1s infinite" }}>🔴</span>
              <span>RECORDING ({formatTimer(recordingSeconds)})</span>
            </div>
          ) : consentStatus?.can_record ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                backgroundColor: "rgba(34, 197, 94, 0.12)",
                border: "1px solid rgba(34, 197, 94, 0.3)",
                color: "#22c55e",
                padding: "4px 10px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
              }}
            >
              <span>🔒 Consented (Ready)</span>
            </div>
          ) : null}

          {/* Connection Status Indicator */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 10px",
              borderRadius: "6px",
              backgroundColor: "rgba(255, 255, 255, 0.04)",
              fontSize: "12px",
            }}
          >
            <div
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor:
                  connectionStatus === "connected"
                    ? "#22c55e"
                    : connectionStatus === "connecting"
                    ? remotePeerActive
                      ? "#38bdf8"
                      : "#a855f7"
                    : connectionStatus === "ended"
                    ? "#ef4444"
                    : "#eab308",
                animation: connectionStatus === "connected" ? "none" : "pulse 1.5s infinite",
              }}
            />
            <span style={{ color: connectionStatus === "connected" ? "#22c55e" : "#94a3b8", fontWeight: 600 }}>
              {connectionStatus === "connected"
                ? "Connected"
                : connectionStatus === "connecting"
                ? remotePeerActive
                  ? "Connecting..."
                  : "Waiting for Peer"
                : connectionStatus === "ended"
                ? "Call Ended"
                : "Reconnecting..."}
            </span>
          </div>
        </div>

        {/* Right Section: User details & End Call */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div style={{ textAlign: "right", fontSize: "12px" }}>
            <div style={{ color: "#f8fafc", fontWeight: 600 }}>
              {joinInfo?.participant_name}
            </div>
            <div style={{ color: "#94a3b8" }}>
              Role: <span style={{ color: "#38bdf8", fontWeight: 600 }}>{joinInfo?.participant_role}</span>
            </div>
          </div>

          <button
            id="end-call-btn"
            onClick={handleEndCall}
            disabled={isEndingCall}
            style={{
              backgroundColor: "#dc2626",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              padding: "8px 18px",
              fontWeight: 600,
              fontSize: "13px",
              cursor: isEndingCall ? "default" : "pointer",
              opacity: isEndingCall ? 0.6 : 1,
              transition: "background-color 0.2s, opacity 0.2s",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
            onMouseOver={(e) => {
              if (!isEndingCall) e.currentTarget.style.backgroundColor = "#b91c1c";
            }}
            onMouseOut={(e) => {
              if (!isEndingCall) e.currentTarget.style.backgroundColor = "#dc2626";
            }}
          >
            <span>📞</span>
            <span>{isEndingCall ? "Ending..." : "End Call"}</span>
          </button>
        </div>
      </header>

      {/* 2. Main Center Consultation Stage + Side Drawer */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <main
          id="consultation-video-stage"
          style={{
            flex: 1,
            height: "100%",
            padding: "20px",
            display: isScreenSharing ? "flex" : "grid",
            gridTemplateColumns: "1fr 1fr",
            gridTemplateRows: isScreenSharing ? "none" : "1fr",
            gap: "20px",
            backgroundColor: "#050811",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* Persistent Viewport Recording Indicator (Phase 8: continuously visible across screenshare/toggle/reconnect) */}
          {isRecording && (
            <div
              id="viewport-persistent-recording-indicator"
              style={{
                position: "absolute",
                top: "24px",
                left: "24px",
                zIndex: 60,
                display: "flex",
                alignItems: "center",
                gap: "8px",
                backgroundColor: "rgba(220, 38, 38, 0.92)",
                color: "#ffffff",
                padding: "8px 18px",
                borderRadius: "9999px",
                fontSize: "13px",
                fontWeight: 800,
                letterSpacing: "0.5px",
                boxShadow: "0 6px 20px rgba(220, 38, 38, 0.6)",
                backdropFilter: "blur(6px)",
                border: "1px solid rgba(255, 255, 255, 0.3)",
                pointerEvents: "none",
              }}
            >
              <span style={{ fontSize: "14px", animation: "pulse 1s infinite" }}>🔴</span>
              <span>RECORDING ({formatTimer(recordingSeconds)})</span>
            </div>
          )}

          {/* Remote Participant Panel */}
          <div
            id="remote-participant-panel"
            style={{
              flex: isScreenSharing ? "1" : "initial",
              height: "100%",
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
              id="remote-video-element"
              ref={setRemoteVideoNode}
              autoPlay
              playsInline
              muted
              onLoadedMetadata={(e) => {
                const v = e.currentTarget;
                console.log(
                  `[LCC-Video] Remote video loadedmetadata: ${v.videoWidth}x${v.videoHeight}`
                );
                if (v.videoWidth > 0 && v.videoHeight > 0) {
                  setIsRemoteVideoPlaying(true);
                }
                v.play().catch(() => {});
              }}
              onCanPlay={(e) => {
                const v = e.currentTarget;
                if (v.videoWidth > 0 && v.videoHeight > 0) {
                  setIsRemoteVideoPlaying(true);
                }
                v.play().catch(() => {});
              }}
              onPlaying={(e) => {
                const v = e.currentTarget;
                console.log("[LCC-Video] Remote video stream is actively rendering frames:", v.videoWidth, "x", v.videoHeight);
                setIsRemoteVideoPlaying(true);
              }}
              onTimeUpdate={(e) => {
                const v = e.currentTarget;
                if (v.currentTime > 0) {
                  setIsRemoteVideoPlaying(true);
                }
              }}
              onPause={() => {
                setIsRemoteVideoPlaying(false);
              }}
              onEmptied={() => {
                setIsRemoteVideoPlaying(false);
              }}
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                objectFit: "cover",
                display: showRemoteVideo ? "block" : "none",
                visibility: showRemoteVideo ? "visible" : "hidden",
                opacity: showRemoteVideo ? 1 : 0,
                zIndex: 1,
                pointerEvents: showRemoteVideo ? "auto" : "none",
                transition: "opacity 0.2s ease-in-out",
              }}
            />
            <audio
              id="remote-audio-element"
              ref={remoteAudioRef}
              autoPlay
            />

            {/* Connecting Video Stream Overlay (shown during WebRTC negotiation handshake) */}
            {showRemoteVideo && !isRemoteVideoPlaying && (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  backgroundColor: "rgba(13, 19, 34, 0.85)",
                  backdropFilter: "blur(4px)",
                  zIndex: 2,
                  pointerEvents: "none",
                }}
              >
                <div
                  style={{
                    width: "48px",
                    height: "48px",
                    borderRadius: "50%",
                    border: "3px solid rgba(59, 130, 246, 0.2)",
                    borderTopColor: "#3b82f6",
                    animation: "spin 1s linear infinite",
                    marginBottom: "14px",
                  }}
                />
                <div style={{ color: "#f8fafc", fontSize: "14px", fontWeight: 600 }}>
                  Connecting video stream...
                </div>
                <div style={{ color: "#94a3b8", fontSize: "12px", marginTop: "4px" }}>
                  Receiving secure video feed from {joinInfo?.participant_role === "CLIENT" ? "Counsel" : "Client"}
                </div>
              </div>
            )}

            {showRemotePlaceholder && (
              <div style={{ textAlign: "center", zIndex: 2 }}>
                <div
                  style={{
                    width: "110px",
                    height: "110px",
                    borderRadius: "50%",
                    backgroundColor: "#1e293b",
                    border: "3px solid #3b82f6",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "44px",
                    fontWeight: 700,
                    color: "#ffffff",
                    margin: "0 auto 16px",
                    boxShadow: "0 0 24px rgba(59, 130, 246, 0.2)",
                  }}
                >
                  {joinInfo?.participant_role === "CLIENT" ? "⚖️" : "👤"}
                </div>

                <h3 style={{ fontSize: "18px", fontWeight: 600, margin: 0 }}>
                  {joinInfo?.participant_role === "CLIENT" ? "Counsel / Advocate" : "Client"}
                </h3>
                <p style={{ color: "#64748b", fontSize: "13px", marginTop: "4px" }}>
                  {remotePeerActive
                    ? "Camera is turned off"
                    : "Waiting for remote participant to connect..."}
                </p>
              </div>
            )}

            {/* Bottom Overlay Label */}
            <div
              style={{
                position: "absolute",
                bottom: "16px",
                left: "16px",
                backgroundColor: "rgba(0, 0, 0, 0.65)",
                backdropFilter: "blur(8px)",
                padding: "6px 14px",
                borderRadius: "8px",
                fontSize: "12px",
                fontWeight: 500,
                display: "flex",
                alignItems: "center",
                gap: "8px",
                zIndex: 5,
                border: "1px solid rgba(255, 255, 255, 0.1)",
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
              <span>
                {joinInfo?.participant_role === "CLIENT" ? "Advocate / Legal Counsel" : "Client"}
              </span>
              {remoteIsMuted && <span style={{ color: "#ef4444" }}>🔇 Muted</span>}
              {remoteIsScreenSharing && <span style={{ color: "#38bdf8" }}>🖥️ Presenting</span>}
            </div>
          </div>

          {/* Local Participant Preview Panel */}
          <div
            id="local-participant-panel"
            style={{
              flex: isScreenSharing ? "0 0 280px" : "initial",
              height: "100%",
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
            {/* Non-blocking Camera Error Banner */}
            {cameraError && (
              <div
                id="camera-error-banner"
                style={{
                  position: "absolute",
                  top: "12px",
                  left: "12px",
                  right: "12px",
                  backgroundColor: "rgba(239, 68, 68, 0.9)",
                  backdropFilter: "blur(6px)",
                  color: "#ffffff",
                  padding: "6px 12px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  zIndex: 10,
                  textAlign: "center",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
                }}
              >
                ⚠️ {cameraError}
              </div>
            )}

            {/* Local Video Element: Permanently mounted with active CSS box to preserve MediaStream binding across camera toggles */}
            <video
              id="local-video-element"
              ref={setLocalVideoNode}
              autoPlay
              playsInline
              muted
              onLoadedMetadata={(e) => {
                const v = e.currentTarget;
                console.log(
                  `[LCC-Video] Local video loadedmetadata: ${v.videoWidth}x${v.videoHeight}`
                );
                v.muted = true;
                v.defaultMuted = true;
                if (!isVideoOff) {
                  v.play().catch((err) =>
                    console.warn("[LCC-Video] Play error on loadedmetadata:", err)
                  );
                }
              }}
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                objectFit: "cover",
                transform: isScreenSharing ? "none" : "scaleX(-1)",
                display: "block",
                visibility: isVideoOff ? "hidden" : "visible",
                opacity: isVideoOff ? 0 : 1,
                zIndex: 1,
                pointerEvents: isVideoOff ? "none" : "auto",
                transition: "opacity 0.2s ease-in-out",
              }}
            />

            {/* Camera Disabled Placeholder */}
            {isVideoOff && (
              <div
                id="camera-off-placeholder"
                style={{
                  textAlign: "center",
                  zIndex: 2,
                  position: "relative",
                  pointerEvents: "none",
                }}
              >
                <div
                  style={{
                    width: "90px",
                    height: "90px",
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
                <p style={{ color: "#94a3b8", fontSize: "14px", margin: 0 }}>Camera Off</p>
              </div>
            )}

            {/* Bottom Overlay Label */}
            <div
              style={{
                position: "absolute",
                bottom: "16px",
                left: "16px",
                backgroundColor: "rgba(0, 0, 0, 0.65)",
                backdropFilter: "blur(8px)",
                padding: "6px 14px",
                borderRadius: "8px",
                fontSize: "12px",
                fontWeight: 500,
                display: "flex",
                alignItems: "center",
                gap: "8px",
                zIndex: 5,
                border: "1px solid rgba(255, 255, 255, 0.1)",
              }}
            >
              <span>You ({joinInfo?.participant_name})</span>
              {isMuted && <span style={{ color: "#ef4444" }}>🔇 Muted</span>}
              {isScreenSharing && <span style={{ color: "#38bdf8" }}>🖥️ Presenting</span>}
            </div>
          </div>
        </main>

        {/* Side Drawer (Tabs: 'chat' | 'participants' | 'notes') */}
        {activeSideTab && (
          <aside
            style={{
              width: "360px",
              backgroundColor: "#0d1322",
              borderLeft: "1px solid rgba(255, 255, 255, 0.08)",
              display: "flex",
              flexDirection: "column",
              zIndex: 15,
            }}
          >
            {/* Drawer Header with Tabs */}
            <div
              style={{
                padding: "16px",
                borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", gap: "6px" }}>
                <button
                  onClick={() => {
                    setActiveSideTab("chat");
                    setUnreadChatCount(0);
                  }}
                  style={{
                    backgroundColor: activeSideTab === "chat" ? "#2563eb" : "transparent",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    padding: "6px 12px",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  💬 Chat
                </button>
                <button
                  onClick={() => setActiveSideTab("participants")}
                  style={{
                    backgroundColor: activeSideTab === "participants" ? "#2563eb" : "transparent",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    padding: "6px 12px",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  👥 People
                </button>
                <button
                  id="tab-documents-btn"
                  onClick={() => {
                    setActiveSideTab("documents");
                    setUnreadDocCount(0);
                  }}
                  style={{
                    backgroundColor: activeSideTab === "documents" ? "#2563eb" : "transparent",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    padding: "6px 10px",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  📁 Docs
                  {unreadDocCount > 0 && (
                    <span
                      style={{
                        backgroundColor: "#ef4444",
                        color: "#ffffff",
                        fontSize: "10px",
                        padding: "1px 5px",
                        borderRadius: "10px",
                        fontWeight: 700,
                      }}
                    >
                      {unreadDocCount}
                    </span>
                  )}
                </button>
                <button
                  onClick={() => setActiveSideTab("notes")}
                  style={{
                    backgroundColor: activeSideTab === "notes" ? "#2563eb" : "transparent",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    padding: "6px 12px",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  📝 Notes
                </button>
                <button
                  id="tab-case-btn"
                  onClick={() => setActiveSideTab("case")}
                  style={{
                    backgroundColor: activeSideTab === "case" ? "#2563eb" : "transparent",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    padding: "6px 10px",
                    fontSize: "13px",
                    fontWeight: 600,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  ⚖️ Case
                </button>
              </div>

              <button
                onClick={() => setActiveSideTab(null)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#94a3b8",
                  fontSize: "18px",
                  cursor: "pointer",
                }}
              >
                ✕
              </button>
            </div>

            {/* Tab Content: Chat */}
            {activeSideTab === "chat" && (
              <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
                <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
                  {chatMessages.length === 0 ? (
                    <div style={{ textAlign: "center", color: "#64748b", marginTop: "40px", fontSize: "13px" }}>
                      <p>No messages yet.</p>
                      <p>Send a message to share notes, statutes, or case citations.</p>
                    </div>
                  ) : (
                    chatMessages.map((msg) => {
                      const isMe = msg.sender_id === joinInfo?.participant_user_id;
                      return (
                        <div
                          key={msg.id}
                          style={{
                            alignSelf: isMe ? "flex-end" : "flex-start",
                            maxWidth: "80%",
                          }}
                        >
                          <div style={{ fontSize: "11px", color: "#94a3b8", marginBottom: "3px", textAlign: isMe ? "right" : "left" }}>
                            {msg.sender_name} • {msg.timestamp}
                          </div>
                          <div
                            style={{
                              backgroundColor: isMe ? "#2563eb" : "#1e293b",
                              color: "#ffffff",
                              padding: "8px 12px",
                              borderRadius: "12px",
                              fontSize: "13px",
                              lineHeight: 1.4,
                              wordBreak: "break-word",
                            }}
                          >
                            {msg.content}
                          </div>
                        </div>
                      );
                    })
                  )}
                  <div ref={chatBottomRef} />
                </div>

                <form
                  onSubmit={handleSendMessage}
                  style={{
                    padding: "12px",
                    borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    gap: "8px",
                  }}
                >
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Send a message to everyone..."
                    style={{
                      flex: 1,
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "8px",
                      color: "#f8fafc",
                      padding: "8px 12px",
                      fontSize: "13px",
                      outline: "none",
                    }}
                  />
                  <button
                    type="submit"
                    style={{
                      backgroundColor: "#3b82f6",
                      color: "#fff",
                      border: "none",
                      borderRadius: "8px",
                      padding: "0 14px",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    ➤
                  </button>
                </form>
              </div>
            )}

            {/* Tab Content: Participants */}
            {activeSideTab === "participants" && (
              <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
                <h4 style={{ fontSize: "13px", textTransform: "uppercase", color: "#94a3b8", margin: "0 0 12px" }}>
                  In This Call (2 Maximum)
                </h4>

                {/* You */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px",
                    backgroundColor: "rgba(255, 255, 255, 0.03)",
                    borderRadius: "8px",
                    marginBottom: "8px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <div style={{ width: "32px", height: "32px", borderRadius: "50%", backgroundColor: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "14px", fontWeight: 700 }}>
                      {joinInfo?.participant_name.charAt(0) || "U"}
                    </div>
                    <div>
                      <div style={{ fontSize: "13px", fontWeight: 600 }}>{joinInfo?.participant_name} (You)</div>
                      <div style={{ fontSize: "11px", color: "#38bdf8" }}>{joinInfo?.participant_role}</div>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "6px", fontSize: "14px" }}>
                    <span>{isMuted ? "🔇" : "🎙️"}</span>
                    <span>{isVideoOff ? "🚫" : "📹"}</span>
                  </div>
                </div>

                {/* Remote Participant */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px",
                    backgroundColor: "rgba(255, 255, 255, 0.03)",
                    borderRadius: "8px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <div style={{ width: "32px", height: "32px", borderRadius: "50%", backgroundColor: "#475569", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "14px", fontWeight: 700 }}>
                      {joinInfo?.participant_role === "CLIENT" ? "⚖️" : "👤"}
                    </div>
                    <div>
                      <div style={{ fontSize: "13px", fontWeight: 600 }}>
                        {joinInfo?.participant_role === "CLIENT" ? "Legal Counsel" : "Client"}
                      </div>
                      <div style={{ fontSize: "11px", color: remotePeerActive ? "#22c55e" : "#f59e0b" }}>
                        {remotePeerActive ? "Connected" : "Waiting to join..."}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: "6px", fontSize: "14px" }}>
                    {remotePeerActive && <span>{remoteIsMuted ? "🔇" : "🎙️"}</span>}
                    {remotePeerActive && <span>{remoteIsVideoOff ? "🚫" : "📹"}</span>}
                  </div>
                </div>
              </div>
            )}

            {/* Tab Content: Notes */}
            {activeSideTab === "notes" && (
              <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
                <h4 style={{ fontSize: "13px", color: "#94a3b8", margin: "0 0 12px" }}>
                  Consultation Notes & Legal Advice
                </h4>

                <textarea
                  value={notesSummary}
                  onChange={(e) => setNotesSummary(e.target.value)}
                  placeholder="Record summary of advice, legal precedents, or statutory points..."
                  rows={4}
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
                  {noteSaved ? "✓ Notes Saved" : submittingNotes ? "Saving..." : "Save Notes to Matter"}
                </button>
              </div>
            )}

            {/* Tab Content: Documents */}
            {activeSideTab === "documents" && (
              <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: "18px" }}>
                <div>
                  <h4 style={{ fontSize: "14px", fontWeight: 700, color: "#f8fafc", margin: "0 0 4px" }}>
                    📁 Consultation Documents
                  </h4>
                  <p style={{ fontSize: "12px", color: "#94a3b8", margin: 0, lineHeight: 1.4 }}>
                    Instantly share agreements, notices, or evidence with {joinInfo?.participant_role === "CLIENT" ? "Advocate" : "Client"}.
                  </p>
                </div>

                {/* Upload / Share Box */}
                <div
                  style={{
                    backgroundColor: "rgba(255, 255, 255, 0.03)",
                    border: "1px dashed rgba(255, 255, 255, 0.16)",
                    borderRadius: "8px",
                    padding: "14px",
                  }}
                >
                  <input
                    ref={docFileInputRef}
                    type="file"
                    style={{ display: "none" }}
                    accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,.txt"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setDocFileToUpload(e.target.files[0]);
                      }
                    }}
                  />

                  {!docFileToUpload ? (
                    <div
                      id="choose-document-btn"
                      onClick={() => docFileInputRef.current?.click()}
                      style={{
                        textAlign: "center",
                        cursor: "pointer",
                        padding: "10px 6px",
                      }}
                    >
                      <div style={{ fontSize: "28px", marginBottom: "6px" }}>📄</div>
                      <div style={{ fontSize: "13px", fontWeight: 600, color: "#38bdf8" }}>
                        Click to select document
                      </div>
                      <div style={{ fontSize: "11px", color: "#64748b", marginTop: "4px" }}>
                        PDF, DOCX, PNG, JPG (Max 25MB)
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          backgroundColor: "rgba(37, 99, 235, 0.12)",
                          border: "1px solid rgba(37, 99, 235, 0.3)",
                          padding: "8px 10px",
                          borderRadius: "6px",
                          marginBottom: "10px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden" }}>
                          <span style={{ fontSize: "16px" }}>📎</span>
                          <span
                            style={{
                              fontSize: "12px",
                              fontWeight: 600,
                              color: "#f8fafc",
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              maxWidth: "200px",
                            }}
                          >
                            {docFileToUpload.name}
                          </span>
                          <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                            ({(docFileToUpload.size / (1024 * 1024)).toFixed(2)} MB)
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setDocFileToUpload(null);
                            if (docFileInputRef.current) docFileInputRef.current.value = "";
                          }}
                          style={{
                            background: "none",
                            border: "none",
                            color: "#ef4444",
                            cursor: "pointer",
                            fontSize: "14px",
                          }}
                        >
                          ✕
                        </button>
                      </div>

                      <input
                        type="text"
                        value={docDescription}
                        onChange={(e) => setDocDescription(e.target.value)}
                        placeholder="Add a note (e.g., Draft Rental Agreement)..."
                        style={{
                          width: "100%",
                          backgroundColor: "#0f172a",
                          border: "1px solid #334155",
                          borderRadius: "6px",
                          color: "#f8fafc",
                          padding: "8px 10px",
                          fontSize: "12px",
                          marginBottom: "10px",
                        }}
                      />

                      <button
                        id="send-document-submit-btn"
                        type="button"
                        onClick={handleUploadAndShareDocument}
                        disabled={uploadingDoc}
                        style={{
                          width: "100%",
                          backgroundColor: "#2563eb",
                          color: "#ffffff",
                          border: "none",
                          borderRadius: "6px",
                          padding: "8px 14px",
                          fontSize: "13px",
                          fontWeight: 600,
                          cursor: uploadingDoc ? "not-allowed" : "pointer",
                          opacity: uploadingDoc ? 0.7 : 1,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          gap: "6px",
                        }}
                      >
                        {uploadingDoc ? "Uploading & Sending..." : "📤 Send to Peer in Call"}
                      </button>
                    </div>
                  )}
                </div>

                {/* Shared Documents List */}
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                    <span style={{ fontSize: "12px", fontWeight: 700, textTransform: "uppercase", color: "#94a3b8", letterSpacing: "0.5px" }}>
                      Shared in this Call ({sharedDocuments.length})
                    </span>
                    <button
                      onClick={fetchSharedDocuments}
                      disabled={loadingDocuments}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#38bdf8",
                        fontSize: "11px",
                        cursor: "pointer",
                      }}
                    >
                      {loadingDocuments ? "Refreshing..." : "↻ Refresh"}
                    </button>
                  </div>

                  {sharedDocuments.length === 0 ? (
                    <div
                      style={{
                        textAlign: "center",
                        padding: "24px 12px",
                        backgroundColor: "rgba(255, 255, 255, 0.02)",
                        borderRadius: "8px",
                        color: "#64748b",
                        fontSize: "12px",
                      }}
                    >
                      No documents shared in this meeting yet.<br />
                      Send a file above to share it in real time.
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {sharedDocuments.map((doc) => {
                        const isPdf = doc.file_name.toLowerCase().endsWith(".pdf");
                        const isImg = /\.(png|jpe?g|webp|gif)$/i.test(doc.file_name);
                        const fileIcon = isPdf ? "📕" : isImg ? "🖼️" : "📄";

                        return (
                          <div
                            key={doc.id}
                            style={{
                              backgroundColor: "#1e293b",
                              border: "1px solid rgba(255, 255, 255, 0.08)",
                              borderRadius: "8px",
                              padding: "12px",
                              display: "flex",
                              flexDirection: "column",
                              gap: "8px",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "flex-start", gap: "10px" }}>
                              <div
                                style={{
                                  fontSize: "20px",
                                  backgroundColor: "rgba(255, 255, 255, 0.06)",
                                  padding: "6px",
                                  borderRadius: "6px",
                                }}
                              >
                                {fileIcon}
                              </div>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div
                                  style={{
                                    fontSize: "13px",
                                    fontWeight: 600,
                                    color: "#f8fafc",
                                    whiteSpace: "nowrap",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                  }}
                                  title={doc.file_name}
                                >
                                  {doc.file_name}
                                </div>
                                <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>
                                  {(doc.file_size / (1024 * 1024)).toFixed(2)} MB •{" "}
                                  <span style={{ color: doc.uploader_role === "LAWYER" ? "#60a5fa" : "#34d399", fontWeight: 600 }}>
                                    {doc.uploader_name} ({doc.uploader_role})
                                  </span>
                                </div>
                                {doc.description && (
                                  <div style={{ fontSize: "11px", color: "#cbd5e1", marginTop: "4px", fontStyle: "italic" }}>
                                    &ldquo;{doc.description}&rdquo;
                                  </div>
                                )}
                              </div>
                            </div>

                            <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                              <a
                                href={doc.download_url}
                                target="_blank"
                                rel="noreferrer"
                                download={doc.file_name}
                                style={{
                                  flex: 1,
                                  textAlign: "center",
                                  backgroundColor: "rgba(37, 99, 235, 0.2)",
                                  border: "1px solid rgba(37, 99, 235, 0.4)",
                                  color: "#60a5fa",
                                  borderRadius: "4px",
                                  padding: "6px 8px",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  textDecoration: "none",
                                }}
                              >
                                ⬇️ Download
                              </a>
                              <button
                                onClick={() => {
                                  setPreviewDocUrl(doc.download_url);
                                  setPreviewDocName(doc.file_name);
                                }}
                                style={{
                                  flex: 1,
                                  backgroundColor: "rgba(255, 255, 255, 0.08)",
                                  border: "1px solid rgba(255, 255, 255, 0.12)",
                                  color: "#f8fafc",
                                  borderRadius: "4px",
                                  padding: "6px 8px",
                                  fontSize: "11px",
                                  fontWeight: 600,
                                  cursor: "pointer",
                                }}
                              >
                                👁️ Preview
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Tab Content: Client Case Workspace */}
            {activeSideTab === "case" && (
              <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: "16px" }}>
                {loadingCaseData ? (
                  <div style={{ textAlign: "center", color: "#94a3b8", padding: "30px 0", fontSize: "13px" }}>
                    Loading client case details...
                  </div>
                ) : linkedCase ? (
                  <>
                    {/* Case Header Card */}
                    <div
                      style={{
                        backgroundColor: "rgba(99, 102, 241, 0.08)",
                        border: "1px solid rgba(99, 102, 241, 0.25)",
                        borderRadius: "10px",
                        padding: "14px",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                        <div>
                          <span
                            style={{
                              fontSize: "10px",
                              fontWeight: 700,
                              textTransform: "uppercase",
                              padding: "2px 8px",
                              borderRadius: "4px",
                              backgroundColor: "rgba(34, 197, 94, 0.2)",
                              color: "#4ade80",
                              display: "inline-block",
                              marginBottom: "6px",
                            }}
                          >
                            ● {linkedCase.status || "ACTIVE"}
                          </span>
                          <h3 style={{ fontSize: "16px", fontWeight: 700, color: "#fff", margin: "0 0 2px 0" }}>
                            {linkedCase.title}
                          </h3>
                          <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                            REF #{linkedCase.reference_number || (linkedCase.id ? linkedCase.id.slice(0, 8) : "")}
                          </span>
                        </div>
                        <button
                          onClick={() => window.open(`/cases/${linkedCase.id}`, "_blank")}
                          style={{
                            fontSize: "11px",
                            fontWeight: 600,
                            color: "#38bdf8",
                            background: "rgba(56, 189, 248, 0.12)",
                            border: "1px solid rgba(56, 189, 248, 0.25)",
                            padding: "4px 8px",
                            borderRadius: "6px",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                          }}
                          title="Open Full Case Workspace in New Tab"
                        >
                          Open Workspace ↗
                        </button>
                      </div>

                      {linkedCase.description && (
                        <p style={{ fontSize: "12px", color: "#cbd5e1", margin: "8px 0 0", lineHeight: 1.4 }}>
                          {linkedCase.description}
                        </p>
                      )}

                      {/* Case metadata pills */}
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "10px" }}>
                        {linkedCase.case_type && (
                          <span style={{ fontSize: "10px", background: "rgba(255,255,255,0.06)", padding: "2px 8px", borderRadius: "4px", color: "#94a3b8" }}>
                            🏛️ {linkedCase.case_type}
                          </span>
                        )}
                        {linkedCase.court_name && (
                          <span style={{ fontSize: "10px", background: "rgba(255,255,255,0.06)", padding: "2px 8px", borderRadius: "4px", color: "#94a3b8" }}>
                            ⚖️ {linkedCase.court_name}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Switch Matter Selector (if multiple cases exist) */}
                    {existingCases.length > 1 && (
                      <div>
                        <label style={{ fontSize: "11px", color: "#94a3b8", display: "block", marginBottom: "4px" }}>
                          Switch Active Client Matter:
                        </label>
                        <select
                          value={linkedCase.id}
                          onChange={(e) => {
                            if (e.target.value) void fetchLinkedCaseData(e.target.value);
                          }}
                          style={{
                            width: "100%",
                            background: "#0f172a",
                            border: "1px solid #334155",
                            color: "#f8fafc",
                            borderRadius: "6px",
                            padding: "6px 8px",
                            fontSize: "12px",
                          }}
                        >
                          {existingCases.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.title} ({c.status})
                            </option>
                          ))}
                        </select>
                      </div>
                    )}

                    {/* Live Case Messages Feed */}
                    <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: "220px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                        <h4 style={{ fontSize: "13px", fontWeight: 700, color: "#f8fafc", margin: 0 }}>
                          💬 Case Messages ({linkedCaseMessages.length})
                        </h4>
                        <button
                          onClick={() => void fetchLinkedCaseData(linkedCase.id)}
                          style={{ background: "none", border: "none", color: "#38bdf8", fontSize: "11px", cursor: "pointer" }}
                        >
                          ↻ Refresh
                        </button>
                      </div>

                      <div
                        style={{
                          flex: 1,
                          maxHeight: "240px",
                          overflowY: "auto",
                          backgroundColor: "#050811",
                          border: "1px solid rgba(255, 255, 255, 0.08)",
                          borderRadius: "8px",
                          padding: "10px",
                          display: "flex",
                          flexDirection: "column",
                          gap: "8px",
                          marginBottom: "10px",
                        }}
                      >
                        {linkedCaseMessages.length === 0 ? (
                          <div style={{ textAlign: "center", color: "#64748b", fontSize: "12px", padding: "20px 0" }}>
                            No messages recorded in this case matter yet. Send instructions or notes below.
                          </div>
                        ) : (
                          linkedCaseMessages.map((msg) => {
                            const isClient = msg.sender_role?.toUpperCase() === "CLIENT" || msg.sender_role?.toUpperCase() === "OWNER";
                            return (
                              <div
                                key={msg.id}
                                style={{
                                  backgroundColor: isClient ? "rgba(14, 165, 233, 0.1)" : "rgba(255, 255, 255, 0.04)",
                                  border: `1px solid ${isClient ? "rgba(14, 165, 233, 0.25)" : "rgba(255, 255, 255, 0.06)"}`,
                                  borderRadius: "6px",
                                  padding: "8px 10px",
                                }}
                              >
                                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "3px" }}>
                                  <span style={{ fontWeight: 700, color: isClient ? "#38bdf8" : "#818cf8" }}>
                                    {msg.sender_name || (isClient ? "Client" : "Counsel")}
                                  </span>
                                  <span style={{ color: "#64748b" }}>
                                    {new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                  </span>
                                </div>
                                <div style={{ fontSize: "12px", color: "#cbd5e1", lineHeight: 1.4 }}>
                                  {msg.content}
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>

                      {/* Post to Case Workspace Composer */}
                      <form onSubmit={handleSendCaseMessage} style={{ display: "flex", gap: "6px" }}>
                        <input
                          type="text"
                          placeholder="Send note/update to case..."
                          value={newCaseMessageText}
                          onChange={(e) => setNewCaseMessageText(e.target.value)}
                          style={{
                            flex: 1,
                            backgroundColor: "#0f172a",
                            border: "1px solid #334155",
                            borderRadius: "6px",
                            color: "#f8fafc",
                            padding: "8px 10px",
                            fontSize: "12px",
                            outline: "none",
                          }}
                        />
                        <button
                          type="submit"
                          disabled={sendingCaseMsg || !newCaseMessageText.trim()}
                          style={{
                            backgroundColor: sendingCaseMsg || !newCaseMessageText.trim() ? "rgba(99, 102, 241, 0.4)" : "#6366f1",
                            color: "#fff",
                            border: "none",
                            borderRadius: "6px",
                            padding: "0 12px",
                            fontSize: "12px",
                            fontWeight: 600,
                            cursor: sendingCaseMsg || !newCaseMessageText.trim() ? "not-allowed" : "pointer",
                          }}
                        >
                          {sendingCaseMsg ? "..." : "Post"}
                        </button>
                      </form>
                    </div>
                  </>
                ) : (
                  <div style={{ textAlign: "center", padding: "20px 0" }}>
                    <div style={{ fontSize: "32px", marginBottom: "8px" }}>⚖️</div>
                    <h4 style={{ fontSize: "14px", color: "#f8fafc", margin: "0 0 6px" }}>
                      No Case Matter Linked
                    </h4>
                    <p style={{ fontSize: "12px", color: "#94a3b8", margin: "0 0 16px" }}>
                      Link an existing case to view documents, timeline, and messages directly in this consultation.
                    </p>
                    {existingCases.length > 0 && (
                      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        <select
                          value={selectedCaseId}
                          onChange={(e) => setSelectedCaseId(e.target.value)}
                          style={{
                            width: "100%",
                            background: "#0f172a",
                            border: "1px solid #334155",
                            color: "#f8fafc",
                            borderRadius: "6px",
                            padding: "8px",
                            fontSize: "12px",
                          }}
                        >
                          <option value="">-- Choose Case Matter --</option>
                          {existingCases.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.title} ({c.status})
                            </option>
                          ))}
                        </select>
                        <button
                          onClick={() => {
                            if (selectedCaseId) void fetchLinkedCaseData(selectedCaseId);
                          }}
                          disabled={!selectedCaseId}
                          style={{
                            backgroundColor: selectedCaseId ? "#6366f1" : "rgba(99, 102, 241, 0.4)",
                            color: "#fff",
                            border: "none",
                            borderRadius: "6px",
                            padding: "8px 14px",
                            fontSize: "12px",
                            fontWeight: 600,
                            cursor: selectedCaseId ? "pointer" : "not-allowed",
                          }}
                        >
                          Open Case Workspace
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </aside>
        )}
      </div>

      {/* 3. Bottom Floating HUD Controller Bar (Google Meet Style) */}
      <footer
        style={{
          padding: "14px 24px",
          backgroundColor: "#0d1322",
          borderTop: "1px solid rgba(255, 255, 255, 0.08)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "14px",
          zIndex: 20,
        }}
      >
        {/* Mute / Unmute */}
        <button
          id="toggle-mic-btn"
          onClick={toggleMute}
          style={{
            backgroundColor: isMuted ? "#ef4444" : "rgba(255, 255, 255, 0.12)",
            color: "#ffffff",
            border: "none",
            borderRadius: "50%",
            width: "48px",
            height: "48px",
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
          id="toggle-video-btn"
          onClick={toggleVideo}
          style={{
            backgroundColor: isVideoOff ? "#ef4444" : "rgba(255, 255, 255, 0.12)",
            color: "#ffffff",
            border: "none",
            borderRadius: "50%",
            width: "48px",
            height: "48px",
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
          id="toggle-screen-btn"
          onClick={toggleScreenShare}
          style={{
            backgroundColor: isScreenSharing ? "#2563eb" : "rgba(255, 255, 255, 0.12)",
            color: "#ffffff",
            border: "none",
            borderRadius: "50%",
            width: "48px",
            height: "48px",
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

        {/* Dual-Consent Recording Controller */}
        {isRecording ? (
          <button
            id="stop-rec-btn"
            onClick={handleStopRecording}
            disabled={uploadingRecording}
            style={{
              backgroundColor: "#ef4444",
              color: "#ffffff",
              border: "none",
              borderRadius: "100px",
              padding: "0 18px",
              height: "48px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              cursor: "pointer",
              fontWeight: 700,
              fontSize: "13px",
              boxShadow: "0 0 16px rgba(239, 68, 68, 0.5)",
            }}
            title="Stop recording and save"
          >
            <span>⏹</span>
            <span>{uploadingRecording ? "Finalizing..." : "Stop REC"}</span>
          </button>
        ) : (
          <button
            id="recording-modal-btn"
            onClick={() => {
              void fetchConsentStatus();
              setShowRecordingModal(true);
            }}
            style={{
              backgroundColor: consentStatus?.can_record ? "rgba(16, 185, 129, 0.2)" : "rgba(255, 255, 255, 0.12)",
              color: consentStatus?.can_record ? "#10b981" : "#ffffff",
              border: consentStatus?.can_record ? "1px solid #10b981" : "none",
              borderRadius: "50%",
              width: "48px",
              height: "48px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              fontSize: "18px",
              transition: "all 0.2s",
            }}
            title="Record Consultation (Requires Mutual Consent)"
          >
            ⏺
          </button>
        )}

        {/* Side Drawer Toggle: Chat */}
        <button
          id="open-chat-btn"
          onClick={() => {
            setActiveSideTab(activeSideTab === "chat" ? null : "chat");
            setUnreadChatCount(0);
          }}
          style={{
            backgroundColor: activeSideTab === "chat" ? "#2563eb" : "rgba(255, 255, 255, 0.12)",
            color: "#ffffff",
            border: "none",
            borderRadius: "50%",
            width: "48px",
            height: "48px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            fontSize: "18px",
            position: "relative",
            transition: "all 0.2s",
          }}
          title="In-Meeting Chat"
        >
          💬
          {unreadChatCount > 0 && (
            <span
              style={{
                position: "absolute",
                top: "2px",
                right: "2px",
                backgroundColor: "#ef4444",
                color: "#fff",
                fontSize: "10px",
                fontWeight: 700,
                width: "18px",
                height: "18px",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {unreadChatCount}
            </span>
          )}
        </button>

        {/* Side Drawer Toggle: Documents */}
        <button
          id="open-documents-btn"
          onClick={() => {
            setActiveSideTab(activeSideTab === "documents" ? null : "documents");
            setUnreadDocCount(0);
          }}
          style={{
            backgroundColor: activeSideTab === "documents" ? "#2563eb" : "rgba(255, 255, 255, 0.12)",
            color: "#ffffff",
            border: "none",
            borderRadius: "50%",
            width: "48px",
            height: "48px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            fontSize: "18px",
            position: "relative",
            transition: "all 0.2s",
          }}
          title="Share Documents with Peer"
        >
          📁
          {unreadDocCount > 0 && (
            <span
              style={{
                position: "absolute",
                top: "2px",
                right: "2px",
                backgroundColor: "#ef4444",
                color: "#fff",
                fontSize: "10px",
                fontWeight: 700,
                width: "18px",
                height: "18px",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {unreadDocCount}
            </span>
          )}
        </button>

        {/* Side Drawer Toggle: Participants */}
        <button
          id="open-participants-btn"
          onClick={() => setActiveSideTab(activeSideTab === "participants" ? null : "participants")}
          style={{
            backgroundColor: activeSideTab === "participants" ? "#2563eb" : "rgba(255, 255, 255, 0.12)",
            color: "#ffffff",
            border: "none",
            borderRadius: "50%",
            width: "48px",
            height: "48px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            fontSize: "18px",
            transition: "all 0.2s",
          }}
          title="Participants"
        >
          👥
        </button>

        {/* Side Drawer Toggle: Client Case Workspace */}
        <button
          id="open-case-workspace-btn"
          onClick={() => setActiveSideTab(activeSideTab === "case" ? null : "case")}
          style={{
            backgroundColor: activeSideTab === "case" ? "#6366f1" : "rgba(255, 255, 255, 0.12)",
            color: "#ffffff",
            border: activeSideTab === "case" ? "1px solid #818cf8" : "none",
            borderRadius: "50%",
            width: "48px",
            height: "48px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            fontSize: "18px",
            transition: "all 0.2s",
          }}
          title={linkedCase ? `Matter: ${linkedCase.title}` : "Client Case Workspace"}
        >
          ⚖️
        </button>

        {/* Device Settings */}
        <button
          id="open-settings-btn"
          onClick={() => setShowDeviceModal(true)}
          style={{
            backgroundColor: "rgba(255, 255, 255, 0.12)",
            color: "#ffffff",
            border: "none",
            borderRadius: "50%",
            width: "48px",
            height: "48px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            fontSize: "18px",
            transition: "all 0.2s",
          }}
          title="Audio & Video Settings"
        >
          ⚙️
        </button>

        {/* Floating Red End Call Button */}
        <button
          id="footer-end-call-btn"
          onClick={handleEndCall}
          disabled={isEndingCall}
          style={{
            backgroundColor: "#dc2626",
            color: "#ffffff",
            border: "none",
            borderRadius: "100px",
            padding: "0 20px",
            height: "48px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            cursor: isEndingCall ? "default" : "pointer",
            fontSize: "14px",
            fontWeight: 600,
            opacity: isEndingCall ? 0.6 : 1,
            transition: "all 0.2s",
            boxShadow: "0 4px 14px rgba(220, 38, 38, 0.4)",
          }}
          title="Conclude Consultation"
        >
          <span>📞</span>
          <span>{isEndingCall ? "Ending..." : "End Call"}</span>
        </button>
      </footer>

      {/* 4. Dual-Consent Recording Modal */}
      {showRecordingModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(8px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 110,
            padding: "20px",
          }}
        >
          <div
            style={{
              backgroundColor: "#111827",
              borderRadius: "16px",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              maxWidth: "460px",
              width: "100%",
              padding: "28px",
              color: "#f8fafc",
              boxShadow: "0 20px 40px rgba(0,0,0,0.7)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "22px" }}>📹</span>
                <h3 style={{ fontSize: "18px", fontWeight: 700, margin: 0 }}>
                  Consultation Recording
                </h3>
              </div>
              <button
                onClick={() => setShowRecordingModal(false)}
                style={{ background: "none", border: "none", color: "#94a3b8", fontSize: "20px", cursor: "pointer" }}
              >
                ✕
              </button>
            </div>

            <p style={{ color: "#94a3b8", fontSize: "13px", lineHeight: 1.5, marginBottom: "20px" }}>
              Consultation recordings are confidential legal work product protected under advocate-client privilege.
              In compliance with legal ethics and privacy standards, recording requires mutual consent from both Client and Counsel.
            </p>

            {/* Consent Status Matrix */}
            <div style={{ backgroundColor: "#1e293b", borderRadius: "10px", padding: "14px", marginBottom: "20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                <span style={{ fontSize: "13px", fontWeight: 500 }}>Client Consent:</span>
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                    color: consentStatus?.client_consented ? "#22c55e" : "#f59e0b",
                  }}
                >
                  {consentStatus?.client_consented ? "✓ Consented" : "⏳ Pending"}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "13px", fontWeight: 500 }}>Advocate Consent:</span>
                <span
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                    color: consentStatus?.lawyer_consented ? "#22c55e" : "#f59e0b",
                  }}
                >
                  {consentStatus?.lawyer_consented ? "✓ Consented" : "⏳ Pending"}
                </span>
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              <button
                onClick={handleGrantConsent}
                disabled={grantingConsent}
                style={{
                  backgroundColor: "#2563eb",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "8px",
                  padding: "10px 16px",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {grantingConsent ? "Recording Consent..." : "Grant My Consent to Record"}
              </button>

              {consentStatus?.can_record && (
                <button
                  onClick={handleStartRecording}
                  style={{
                    backgroundColor: "#10b981",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "8px",
                    padding: "10px 16px",
                    fontSize: "13px",
                    fontWeight: 700,
                    cursor: "pointer",
                  }}
                >
                  ⏺ Begin Recording Session
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 5. Device Settings Modal */}
      {showDeviceModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(8px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 110,
            padding: "20px",
          }}
        >
          <div
            style={{
              backgroundColor: "#111827",
              borderRadius: "16px",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              maxWidth: "440px",
              width: "100%",
              padding: "28px",
              color: "#f8fafc",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
              <h3 style={{ fontSize: "18px", fontWeight: 700, margin: 0 }}>
                ⚙️ Device Settings
              </h3>
              <button
                onClick={() => setShowDeviceModal(false)}
                style={{ background: "none", border: "none", color: "#94a3b8", fontSize: "20px", cursor: "pointer" }}
              >
                ✕
              </button>
            </div>

            <div style={{ marginBottom: "16px" }}>
              <label style={{ display: "block", fontSize: "13px", color: "#94a3b8", marginBottom: "6px" }}>
                Microphone
              </label>
              <select
                style={{
                  width: "100%",
                  backgroundColor: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: "6px",
                  color: "#f8fafc",
                  padding: "8px 12px",
                  fontSize: "13px",
                }}
              >
                {availableDevices.audioInputs.length > 0 ? (
                  availableDevices.audioInputs.map((d) => (
                    <option key={d.deviceId} value={d.deviceId}>
                      {d.label || "Default Microphone"}
                    </option>
                  ))
                ) : (
                  <option>System Default Microphone</option>
                )}
              </select>
            </div>

            <div style={{ marginBottom: "20px" }}>
              <label style={{ display: "block", fontSize: "13px", color: "#94a3b8", marginBottom: "6px" }}>
                Camera
              </label>
              <select
                style={{
                  width: "100%",
                  backgroundColor: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: "6px",
                  color: "#f8fafc",
                  padding: "8px 12px",
                  fontSize: "13px",
                }}
              >
                {availableDevices.videoInputs.length > 0 ? (
                  availableDevices.videoInputs.map((d) => (
                    <option key={d.deviceId} value={d.deviceId}>
                      {d.label || "Default Camera"}
                    </option>
                  ))
                ) : (
                  <option>System Default Camera</option>
                )}
              </select>
            </div>

            <button
              onClick={() => setShowDeviceModal(false)}
              style={{
                backgroundColor: "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                padding: "10px",
                fontWeight: 600,
                width: "100%",
                cursor: "pointer",
              }}
            >
              Done
            </button>
          </div>
        </div>
      )}

      {/* 6. Post-Consultation Workflow Modal */}
      {showPostCallModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.85)",
            backdropFilter: "blur(12px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 120,
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
                onClick={() => router.push("/consultations")}
                style={{
                  backgroundColor: "transparent",
                  color: "#94a3b8",
                  border: "none",
                  fontSize: "14px",
                  cursor: "pointer",
                  textDecoration: "underline",
                }}
              >
                Back to Consultations
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Real-Time Document Shared Toast Notification */}
      {documentToast && (
        <div
          id="document-shared-toast"
          style={{
            position: "fixed",
            top: "24px",
            right: "24px",
            backgroundColor: "#1e293b",
            border: "1px solid #3b82f6",
            borderRadius: "10px",
            padding: "16px 20px",
            boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4)",
            zIndex: 100,
            display: "flex",
            alignItems: "center",
            gap: "14px",
            maxWidth: "380px",
          }}
        >
          <div style={{ fontSize: "24px" }}>📄</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: "12px", color: "#94a3b8" }}>
              <strong style={{ color: "#60a5fa" }}>{documentToast.sender}</strong> shared a document
            </div>
            <div
              style={{
                fontSize: "13px",
                fontWeight: 600,
                color: "#f8fafc",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                marginTop: "2px",
              }}
              title={documentToast.filename}
            >
              {documentToast.filename}
            </div>
          </div>
          <div style={{ display: "flex", gap: "6px" }}>
            <button
              onClick={() => {
                setActiveSideTab("documents");
                setDocumentToast(null);
                setUnreadDocCount(0);
              }}
              style={{
                backgroundColor: "#2563eb",
                color: "#fff",
                border: "none",
                borderRadius: "6px",
                padding: "6px 12px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              View
            </button>
            <button
              onClick={() => setDocumentToast(null)}
              style={{
                background: "none",
                border: "none",
                color: "#94a3b8",
                cursor: "pointer",
                fontSize: "16px",
              }}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* In-Meeting Document Preview Modal */}
      {previewDocUrl && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            zIndex: 150,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "24px",
          }}
          onClick={() => {
            setPreviewDocUrl(null);
            setPreviewDocName(null);
          }}
        >
          <div
            style={{
              backgroundColor: "#0f172a",
              border: "1px solid #334155",
              borderRadius: "12px",
              width: "100%",
              maxWidth: "800px",
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                padding: "14px 18px",
                borderBottom: "1px solid #1e293b",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "18px" }}>📄</span>
                <span style={{ fontSize: "14px", fontWeight: 600, color: "#f8fafc" }}>
                  {previewDocName || "Document Preview"}
                </span>
              </div>
              <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                <a
                  href={previewDocUrl}
                  target="_blank"
                  rel="noreferrer"
                  download={previewDocName || "document"}
                  style={{
                    backgroundColor: "#2563eb",
                    color: "#ffffff",
                    borderRadius: "6px",
                    padding: "6px 12px",
                    fontSize: "12px",
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  ⬇️ Download
                </a>
                <button
                  onClick={() => {
                    setPreviewDocUrl(null);
                    setPreviewDocName(null);
                  }}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#94a3b8",
                    fontSize: "20px",
                    cursor: "pointer",
                  }}
                >
                  ✕
                </button>
              </div>
            </div>

            <div style={{ flex: 1, minHeight: "360px", maxHeight: "65vh", overflow: "hidden", backgroundColor: "#020617", display: "flex", alignItems: "center", justifyContent: "center" }}>
              {previewDocName && /\.(png|jpe?g|webp|gif)$/i.test(previewDocName) ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={previewDocUrl}
                  alt={previewDocName}
                  style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
                />
              ) : (
                <iframe
                  src={previewDocUrl}
                  title="Document Preview"
                  style={{ width: "100%", height: "100%", minHeight: "450px", border: "none" }}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
