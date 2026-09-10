"""Consultations & Video Domain package."""

import importlib
from typing import Any

__all__ = [
    "ConsultationService",
    "IncomingCallChannelManager",
    "InternalWebRTCMeetingProvider",
    "LiveKitMeetingProvider",
    "LocalRecordingStorageProvider",
    "MockVideoMeetingProvider",
    "PresenceService",
    "RecordingStorageProvider",
    "S3RecordingStorageProvider",
    "VideoMeetingProvider",
    "VideoMeetingService",
    "VideoMetricsRegistry",
    "VideoRecordingService",
    "VideoSignalingManager",
    "VideoTelemetryEvent",
    "VideoTelemetryService",
    "get_recording_storage_provider",
    "get_video_provider",
    "incoming_call_channel_manager",
    "metrics_registry",
    "presence_manager",
    "presence_service",
    "reset_recording_storage_provider",
    "signaling_manager",
]

_MODULE_MAP = {
    "VideoSignalingManager": "video_signaling_manager",
    "signaling_manager": "video_signaling_manager",
    "ConsultationService": "consultation_service",
    "VideoMeetingService": "video_meeting_service",
    "VideoMeetingProvider": "video_meeting_service",
    "InternalWebRTCMeetingProvider": "video_meeting_service",
    "MockVideoMeetingProvider": "video_meeting_service",
    "LiveKitMeetingProvider": "video_meeting_service",
    "get_video_provider": "video_meeting_service",
    "VideoRecordingService": "video_recording_service",
    "RecordingStorageProvider": "recording_storage",
    "LocalRecordingStorageProvider": "recording_storage",
    "S3RecordingStorageProvider": "recording_storage",
    "reset_recording_storage_provider": "recording_storage",
    "get_recording_storage_provider": "recording_storage",
    "VideoTelemetryService": "video_telemetry_service",
    "VideoTelemetryEvent": "video_telemetry_service",
    "VideoMetricsRegistry": "video_telemetry_service",
    "metrics_registry": "video_telemetry_service",
    "PresenceService": "presence_service",
    "presence_service": "presence_service",
    "presence_manager": "presence_service",
    "IncomingCallChannelManager": "lawyer_call_channel",
    "incoming_call_channel_manager": "lawyer_call_channel",
}


def __getattr__(name: str) -> Any:
    mod_name = _MODULE_MAP.get(name)
    if mod_name:
        mod = importlib.import_module(f"app.domain.consultations.{mod_name}")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
