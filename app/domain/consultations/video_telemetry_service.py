"""Structured telemetry and observability service for video consultations and recording lifecycles.

Tracks real-time meeting and recording events, aggregates operational reliability metrics,
and enforces strict sanitization to prevent leaking JWTs, credentials, or private legal evidence.
"""

import enum
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger("lcc.telemetry.video")


class VideoTelemetryEvent(str, enum.Enum):
    ROOM_CREATED = "room_created"
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"
    CONNECTION_LOST = "connection_lost"
    RECONNECT_ATTEMPTED = "reconnect_attempted"
    RECONNECT_SUCCEEDED = "reconnect_succeeded"
    RECONNECT_FAILED = "reconnect_failed"
    CONSULTATION_STARTED = "consultation_started"
    CONSULTATION_ENDED = "consultation_ended"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    RECORDING_PROCESSING = "recording_processing"
    RECORDING_UPLOAD_STARTED = "recording_upload_started"
    RECORDING_UPLOAD_COMPLETED = "recording_upload_completed"
    RECORDING_UPLOAD_FAILED = "recording_upload_failed"
    RECORDING_AVAILABLE = "recording_available"
    PROVIDER_FAILURE = "provider_failure"


class VideoMetricsRegistry:
    """In-memory operational metric counters and latency histograms for video infrastructure."""

    def __init__(self):
        self._counters: dict[str, int] = {
            "video_room_creation_failures": 0,
            "video_join_failures": 0,
            "reconnect_attempts": 0,
            "reconnect_successes": 0,
            "reconnect_failures": 0,
            "recording_start_failures": 0,
            "recording_stop_failures": 0,
            "recording_upload_failures": 0,
            "orphaned_recordings": 0,
            "stale_active_rooms": 0,
            "provider_error_count": 0,
        }
        self._latencies: dict[str, list[float]] = {
            "recording_upload_latency": [],
            "recording_processing_latency": [],
        }

    def increment(self, metric_name: str, value: int = 1) -> None:
        if metric_name in self._counters:
            self._counters[metric_name] += value
        else:
            self._counters[metric_name] = value

    def observe_latency(self, metric_name: str, seconds: float) -> None:
        if metric_name not in self._latencies:
            self._latencies[metric_name] = []
        self._latencies[metric_name].append(seconds)
        # Keep sliding window of last 500 observations
        if len(self._latencies[metric_name]) > 500:
            self._latencies[metric_name].pop(0)

    def get_metrics_snapshot(self) -> dict[str, Any]:
        snapshot: dict[str, Any] = dict(self._counters)
        reconnect_attempts = self._counters.get("reconnect_attempts", 0)
        reconnect_successes = self._counters.get("reconnect_successes", 0)
        reconnect_success_rate = (
            (reconnect_successes / reconnect_attempts * 100.0)
            if reconnect_attempts > 0
            else 100.0
        )
        snapshot["reconnect_success_rate"] = round(reconnect_success_rate, 2)

        for metric, vals in self._latencies.items():
            if vals:
                snapshot[f"{metric}_avg_seconds"] = round(sum(vals) / len(vals), 4)
                snapshot[f"{metric}_p95_seconds"] = round(sorted(vals)[int(len(vals) * 0.95)], 4)
            else:
                snapshot[f"{metric}_avg_seconds"] = 0.0
                snapshot[f"{metric}_p95_seconds"] = 0.0

        return snapshot

    def reset(self) -> None:
        """Reset all metrics (primarily for test isolation)."""
        for k in self._counters:
            self._counters[k] = 0
        for k in self._latencies:
            self._latencies[k].clear()


# Global singleton registry
metrics_registry = VideoMetricsRegistry()


class VideoTelemetryService:
    """Emits structured correlation events and aggregates production telemetry."""

    FORBIDDEN_KEYS: set[str] = {
        "password",
        "secret",
        "token",
        "jwt",
        "authorization",
        "api_key",
        "private_key",
        "credential",
        "access_token",
        "refresh_token",
        "raw_evidence",
    }

    @classmethod
    def sanitize_metadata(cls, metadata: dict[str, Any]) -> dict[str, Any]:
        """Redacts sensitive credentials, tokens, or private legal evidence from telemetry logs."""
        clean: dict[str, Any] = {}
        for k, v in metadata.items():
            key_lower = k.lower()
            if any(forbidden in key_lower for forbidden in cls.FORBIDDEN_KEYS):
                clean[k] = "[REDACTED]"
            elif isinstance(v, dict):
                clean[k] = cls.sanitize_metadata(v)
            else:
                clean[k] = v
        return clean

    @classmethod
    def record_event(
        cls,
        event: VideoTelemetryEvent | str,
        consultation_id: UUID | str | None = None,
        room_id: str | None = None,
        user_id: UUID | str | None = None,
        role: str | None = None,
        recording_id: UUID | str | None = None,
        provider: str | None = None,
        result: str = "SUCCESS",
        failure_code: str | None = None,
        duration_seconds: float | None = None,
        file_size_bytes: int | None = None,
        request_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event_name = event.value if isinstance(event, VideoTelemetryEvent) else str(event)
        now_iso = datetime.now(UTC).isoformat()

        payload: dict[str, Any] = {
            "timestamp": now_iso,
            "event_type": event_name,
            "consultation_id": str(consultation_id) if consultation_id else None,
            "room_id": room_id,
            "user_id": str(user_id) if user_id else None,
            "role": role,
            "recording_id": str(recording_id) if recording_id else None,
            "provider": provider,
            "result": result,
            "failure_code": failure_code,
            "request_id": request_id,
        }

        if duration_seconds is not None:
            payload["duration_seconds"] = round(float(duration_seconds), 3)
        if file_size_bytes is not None:
            payload["file_size_bytes"] = int(file_size_bytes)
        if extra:
            payload["extra"] = cls.sanitize_metadata(extra)

        # Update metrics registry based on event semantics
        if event_name == VideoTelemetryEvent.RECONNECT_ATTEMPTED.value:
            metrics_registry.increment("reconnect_attempts")
        elif event_name == VideoTelemetryEvent.RECONNECT_SUCCEEDED.value:
            metrics_registry.increment("reconnect_successes")
        elif event_name == VideoTelemetryEvent.RECONNECT_FAILED.value:
            metrics_registry.increment("reconnect_failures")
        elif event_name == VideoTelemetryEvent.RECORDING_UPLOAD_FAILED.value:
            metrics_registry.increment("recording_upload_failures")
        elif event_name == VideoTelemetryEvent.PROVIDER_FAILURE.value:
            metrics_registry.increment("provider_error_count")

        if duration_seconds is not None and event_name == VideoTelemetryEvent.RECORDING_UPLOAD_COMPLETED.value:
            metrics_registry.observe_latency("recording_upload_latency", duration_seconds)

        # Structured log emission
        if result == "SUCCESS":
            logger.info("VIDEO_TELEMETRY: %s", payload)
        else:
            logger.warning("VIDEO_TELEMETRY_FAILURE: %s", payload)

        return payload
