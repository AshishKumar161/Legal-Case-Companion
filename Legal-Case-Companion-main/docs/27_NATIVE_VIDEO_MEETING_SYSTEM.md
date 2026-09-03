# LCC Native In-App Meeting System Architecture & Specification

## 1. Executive Summary & Design Principles

Legal Case Companion (LCC) implements a **native in-app video meeting system** designed for confidential Indian legal consultations.

### Critical Requirement: Zero External Redirects
The platform strictly forbids redirecting users to external services such as Google Meet, Zoom, Microsoft Teams, or externally hosted Jitsi instances. The entire consultation lifecycle—scheduling, pre-call lobby, media negotiation, video conferencing, real-time consultation chat, dual-consent recording, and post-session playback—occurs exclusively inside the authenticated LCC application.

---

## 2. Multi-Tier Security & Authorization Architecture

Video infrastructure is never the source of authorization. LCC enforces a strict four-layer access control hierarchy:

```
[ LCC Identity Auth (JWT Bearer / Cookie) ]
                   │
                   ▼
[ Consultation Authorization (Participant BOLA Check) ]
                   │
                   ▼
[ Video Meeting Token (Room & Role-Scoped HMAC-SHA256 / JWT) ]
                   │
                   ▼
[ Native Room / LiveKit SFU Media Tracks ]
```

### 2.1 BOLA / IDOR Defense
Every API route handling video meetings, signaling, recordings, and playback enforces strict Object-Level Authorization:
- If a user is not the designated `CLIENT` or `LAWYER` on the specific consultation, the system returns **HTTP 404 (ResourceNotFoundError)** instead of HTTP 403. This prevents malicious actors from enumerating valid consultation IDs or probing recording existence.
- Verification tokens are strictly bound to `(consultation_id, user_id, role, room_id, expiration)`.

### 2.2 Dual-Consent Recording Policy
In compliance with Indian legal privilege and privacy best practices, recording a legal consultation requires **explicit, independent consent from both parties**:
1. Both the Client and Counsel must grant consent via `POST /api/v1/consultations/{id}/video/recording/consent`.
2. The recording cannot be initiated (`POST /api/v1/consultations/{id}/video/recording/start`) if either participant has withheld consent (returns HTTP 400 / 422).
3. If either participant revokes consent during a session, active recording immediately terminates.
4. Consent statuses are reflected in real-time to both peers over WebSocket signaling (`recording-status` events).

---

## 3. Production Provider Policy & Topology

LCC provides a pluggable meeting provider abstraction via `VideoMeetingProvider`:

```
                    ┌────────────────────────┐
                    │   VideoMeetingService  │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│   LiveKitMeetingProvider (SFU)  │   │  InternalWebRTCMeetingProvider  │
│  - Multi-party Scalability      │   │  - Zero-infra P2P direct mesh   │
│  - Adaptive Bitrate / Simulcast │   │  - WebSocket Signaling Relay    │
│  - MANDATORY in Production      │   │  - Allowed in Dev / Test only   │
└─────────────────────────────────┘   └─────────────────────────────────┘
```

### 3.1 Deterministic Production Provider Policy
- **Production Environment (`ENVIRONMENT=production`)**: LiveKit SFU is **strictly required**. `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` must all be configured. If any credential is missing, `get_video_provider()` immediately raises a `ConfigurationError` (HTTP 500). **Silent fallback to P2P in production is strictly forbidden.**
- **Development / Test Environment**: If LiveKit credentials are absent, the system safely falls back to `InternalWebRTCMeetingProvider` using LCC's native WebSocket signaling hub and Coturn STUN/TURN servers.

### 3.2 Token Issuance & Scoping Protocol
- **LiveKit SFU**: Generates standards-compliant JWTs containing `video.room`, `video.roomJoin`, `sub` (participant ID), `role`, and expiration (1-hour TTL).
- **Internal WebRTC**: Generates HMAC-SHA256 signed session tokens encoding room ID, user ID, role, consultation ID, and expiration.
- **Cross-Room & Impersonation Prevention**: Tokens for consultation A are rejected if presented to join consultation B; tokens issued for a Client cannot impersonate a Lawyer.

---

## 4. WebSocket Signaling & In-Meeting Messaging

**Endpoint**: `GET /api/v1/consultations/{id}/video/ws?token={video_token}`

The signaling channel provides low-latency bidirectional state management between participants:

| Message Type | Direction | Payload | Purpose | Persistence |
| :--- | :--- | :--- | :--- | :--- |
| `offer` | Client ⇄ Lawyer | `{ sdp: string }` | WebRTC session description exchange | Ephemeral (RAM) |
| `answer` | Client ⇄ Lawyer | `{ sdp: string }` | WebRTC session answer exchange | Ephemeral (RAM) |
| `ice-candidate` | Client ⇄ Lawyer | `{ candidate: string }` | NAT traversal candidate exchange | Ephemeral (RAM) |
| `chat` | Client ⇄ Lawyer | `{ content, sender_name, timestamp }` | In-meeting confidential text chat | Ephemeral (RAM) |
| `media-status` | Client ⇄ Lawyer | `{ is_muted, is_video_off, is_screen_sharing }` | Remote mute / video / share indicators | Ephemeral (RAM) |
| `recording-status`| Client ⇄ Lawyer | `{ status: "RECORDING" \| "IDLE" \| "UPLOADING" }` | Real-time recording state banner sync | Ephemeral (RAM) |
| `peer-joined` | Server ➔ Peer | `{ user_id, role, peer_count }` | Peer arrival notification | Ephemeral (RAM) |
| `peer-left` | Server ➔ Peer | `{ user_id, role }` | Peer departure notification | Ephemeral (RAM) |

*Note on In-Meeting Chat: Chat messages are intentionally ephemeral (in-memory relay only) to safeguard legal privilege, unless explicitly formalized into consultation notes.*

---

## 5. Storage, Integrity & Streaming Playback Pipeline

```
[ In-Meeting MediaRecorder with Web Audio Mixed Tracks ]
                   │
                   ▼ (POST /video/recording/upload)
[ VideoRecordingService (SHA-256 Checksum Calculation) ]
                   │
                   ▼
[ Local Disk: storage/recordings/consultations/{id}/{rec_id}.webm ]
                   │
                   ▼ (POST /api/v1/recordings/{id}/playback-ticket)
[ Ephemeral 60s Single-Purpose Media Ticket ]
                   │
                   ▼ (GET /api/v1/recordings/{id}/play?ticket=...)
[ HTTP 206 Partial Content Streaming Engine with Security Headers ]
                   │
                   ▼
[ In-App HTML5 Video Player with Range Seeking ]
```

### 5.1 Multi-Party Audio & Video Capture
- The client-side in-app recorder combines the active video track with a mixed audio destination via Web Audio API (`AudioContext.createMediaStreamDestination()`).
- Captures local microphone audio and remote participant audio into a synchronized WebM container.
- When screen sharing is active, the screen capture video stream is routed into the recorded track.

### 5.2 Cryptographic Integrity Verification (SHA-256)
- Raw binary uploads are hashed on ingestion via SHA-256 and cataloged on `VideoRecording.checksum_sha256`.
- **Integrity Verification on Playback**: Before streaming, `get_recording_for_playback` verifies the physical file's SHA-256 against the database record. If the file on disk has been corrupted or modified, playback is rejected with a `ValidationError`.
- SHA-256 is strictly documented as **cryptographic integrity verification** (detecting file modification or storage corruption), not tamper-proofing.

### 5.3 Removal of Bearer Access Tokens from URLs & Ephemeral Playback Tickets
- **Query Parameter Token Rejection**: Passing normal application access tokens via `?token=<access_token>` to the playback endpoint is **strictly rejected with HTTP 401**.
- **Ephemeral Ticket Exchange**:
  1. Frontend calls authenticated `POST /api/v1/recordings/{recording_id}/playback-ticket` with standard `Authorization: Bearer <access_token>`.
  2. Backend validates BOLA, user active status, and recording availability, issuing a cryptographically signed 60-second ticket (`mpt_...`) bound to `(user_id, recording_id)`.
  3. Frontend player streams via `GET /api/v1/recordings/{recording_id}/play?ticket=<ticket>`.
- Standard `Authorization: Bearer` headers remain supported for direct API/backend playback.

### 5.4 Playback Security & Anti-Caching Headers
To protect client-attorney confidentiality, all playback streams return strict non-caching headers:
```http
Cache-Control: private, no-cache, no-store, must-revalidate
Pragma: no-cache
Expires: 0
Content-Disposition: inline; filename="consultation_recording_*.webm"
X-Content-Type-Options: nosniff
```

---

## 6. Frontend Consultation Suite UI

The video consultation suite (`frontend/src/app/consultations/[id]/room/page.tsx`) delivers an interface comparable in capability to Google Meet / Zoom:

1. **Header & Context Bar**:
   - Session identifier and confidential advocate / client badges.
   - Encrypted call timer and real-time network latency indicator.
   - **Continuous `🔴 RECORDING` Indicator**: Prominently displayed in both the top context bar and as a persistent floating badge inside the main viewport canvas, continuously visible across screenshare, mute, camera toggle, and reconnection.
2. **Media Viewport**:
   - Primary video feed (active speaker or remote participant).
   - Local picture-in-picture video preview with camera toggle status.
   - Screen sharing display mode.
   - Audio visualizer waveforms indicating microphone input.
3. **Floating Control Dock**:
   - Mic mute / unmute toggle.
   - Video camera enable / disable toggle.
   - Screen sharing initiation.
   - Dual-consent recording request / start / stop button.
   - End Call with post-session matter transition modal.
4. **Side Drawer Workspace**:
   - **In-Meeting Chat**: Encrypted, session-scoped messaging between client and advocate.
   - **Participants**: Roster with verified Bar Council credentials and microphone/video states.
   - **Active Matter / Notes**: Real-time reference panel displaying linked case summaries, documents, and consultation note taking.
5. **Post-Consultation Recordings Modal**:
   - Accessible from `frontend/src/app/consultations/page.tsx`.
   - Displays all recorded sessions with duration, size, and SHA-256 verification hash.
   - In-app streaming video player with native pause, scrub, seek, and fullscreen support powered by ephemeral tickets.

### 6.1 Local Camera Preview Lifecycle, Rendering & Resilient Fallback

To ensure the user's face is immediately visible and remains stable across camera toggling, on-demand acquisition, and screen sharing:
1. **Callback Ref & Lifecycle Timing**:
   - The consultation room initial loading state displays a connecting screen. Because the DOM `<video>` element is not mounted until `loading === false`, direct assignment during `getUserMedia()` cannot reach the unmounted DOM node.
   - A callback ref (`setLocalVideoNode`) automatically binds `node.srcObject = activeStream`, sets DOM properties `node.muted = true` and `node.defaultMuted = true` to satisfy browser autoplay requirements, and invokes `node.play()` the exact moment the element mounts into the DOM.
   - A reactive synchronization effect watches `[loading, localStream, isVideoOff, isScreenSharing]` to ensure `srcObject` remains bound across all state transitions.
2. **Permanent DOM Mounting with CSS Visibility / Opacity Toggling (No `display: none`)**:
   - The `<video>` element is permanently retained in the active layout tree (`display: block; position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover`).
   - Using `display: none` is strictly avoided because removing the video element from the CSS box tree halts media frame sinks, drops dimensions (`width=0, height=0`), and causes `play()` calls to abort or reject in Chromium/WebKit.
   - Toggling the camera OFF disables video tracks (`track.enabled = false`), transitions `visibility: hidden; opacity: 0; pointer-events: none;`, and displays the "Camera Off" placeholder overlay (`z-index: 2`).
   - Toggling the camera back ON re-enables tracks (`track.enabled = true`), transitions `visibility: visible; opacity: 1;`, and immediately resumes rendering frames without layout reflow or decoder reinitialization.
3. **P2P vs LiveKit Rendering Paths & On-Demand Camera Acquisition**:
   - **Internal P2P Path (Development / Test)**: Direct `MediaStream` attachment via `video.srcObject = stream` combined with `pc.addTrack(track, stream)`.
   - **LiveKit SFU Path (Production)**: Participant video track publication via `Room.localParticipant.publishTrack(track)` rendered through LiveKit's video element binding.
   - **On-Demand Camera Toggle**: If consultation entry occurred audio-only (e.g. initial camera denial or unavailable hardware), toggling camera ON triggers on-demand `getUserMedia({ video: true })`, updates `localStreamRef.current`, creates a fresh `MediaStream` reference to refresh the video sink, immediately re-binds `localVideoRef.current.srcObject`, calls `play()`, and renegotiates the video sender over WebRTC signaling.
4. **Resilient Error Handling & Audio-Only Fallback**:
   - If camera access is rejected (`NotAllowedError`) or no camera is detected (`NotFoundError`), the system traps the specific error and surfaces a non-blocking diagnostic banner (`cameraError`).
   - It automatically attempts an audio-only fallback (`getUserMedia({ audio: true, video: false })`), allowing the user to seamlessly participate in the legal consultation with audio even if video is unavailable.
5. **Screen Share Track Swapping**:
   - Screen sharing swaps the video sender on `RTCPeerConnection` and temporarily displays the screen stream in the local preview.
   - When screen sharing terminates (either via browser UI or the in-app button), screen tracks are terminated and `localStreamRef.current` is restored with playback resumed.

---

## 7. Verification & Integration Test Coverage

The native video consultation system is validated by comprehensive integration test suites:

- `test_dual_consent_enforcement_and_recording_lifecycle`: Mutual consent requirement, recording state flow, SHA-256 checksum computation, cataloging.
- `test_http_206_partial_content_playback_and_token_query`: HTTP 200, HTTP 206 byte ranges, range seeking, query token rejection, ticket-based playback, security headers.
- `test_file_tamper_checksum_mismatch_fails_playback`: Detects physical file modification on disk and rejects playback with integrity verification error.
- `test_production_provider_policy_no_silent_fallback`: Validates `ConfigurationError` when in production without LiveKit credentials; validates P2P in development.
- `test_livekit_token_cross_room_and_impersonation_rejection`: Cross-room and cross-role token isolation defense.
- `test_concurrency_recording_guards`: Duplicate recording start, stop, and finalize concurrency protections.
- `test_recording_and_video_bola_unauthorized_isolation`: Strict HTTP 404 anti-enumeration IDOR protection across video join, recording list, and streaming.
- `test_websocket_signaling_chat_and_media_status_relay`: WebSocket message relay for chat, media toggles, and recording status.
