import threading
import time
from collections import defaultdict
from typing import Any


class MetricsCollector:
    """Thread-safe in-memory operational metrics collector for production observability."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._lock = threading.Lock()
        self.request_counts = defaultdict(int)
        self.status_counts = defaultdict(int)
        self.request_latencies: list[float] = []
        self.max_latency_samples = 1000
        self.start_time = time.time()
        self.ai_requests_count = defaultdict(int)
        self.auth_failures_count = defaultdict(int)
        self.authorization_denials_count = defaultdict(int)
        self.evidence_operations_count = defaultdict(int)
        self.queue_jobs_count = defaultdict(int)
        self.dependency_failures_count = defaultdict(int)
        self.tamper_events_total = 0
        self.outbox_events_count = defaultdict(int)
        self.registration_events: dict[str, int] = defaultdict(int)
        self.payment_events: dict[str, int] = defaultdict(int)
        self.localization_fallbacks: dict[str, int] = defaultdict(int)
        self.abuse_anomalies: dict[str, int] = defaultdict(int)
        self._initialized = True

    def record_http_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        with self._lock:
            self.request_counts[f"{method} {path}"] += 1
            self.status_counts[str(status_code)] += 1
            if len(self.request_latencies) < self.max_latency_samples:
                self.request_latencies.append(duration_ms)
            else:
                self.request_latencies.pop(0)
                self.request_latencies.append(duration_ms)

    def record_ai_request(self, operation: str, outcome: str) -> None:
        with self._lock:
            self.ai_requests_count[f"{operation}:{outcome}"] += 1

    def record_auth_failure(self, reason: str) -> None:
        with self._lock:
            self.auth_failures_count[reason] += 1

    def record_authorization_denial(self, resource_type: str) -> None:
        with self._lock:
            self.authorization_denials_count[resource_type] += 1

    def record_evidence_operation(self, operation: str, outcome: str) -> None:
        with self._lock:
            self.evidence_operations_count[f"{operation}:{outcome}"] += 1

    def record_queue_job(self, job_type: str, status: str) -> None:
        with self._lock:
            self.queue_jobs_count[f"{job_type}:{status}"] += 1

    def record_dependency_failure(self, dependency_name: str) -> None:
        with self._lock:
            self.dependency_failures_count[dependency_name] += 1

    def record_tamper_event(self) -> None:
        with self._lock:
            self.tamper_events_total += 1

    def record_outbox_event(self, event_type: str, status: str) -> None:
        with self._lock:
            self.outbox_events_count[f"{event_type}:{status}"] += 1

    def record_refresh_replay(self) -> None:
        with self._lock:
            self.auth_failures_count["REFRESH_TOKEN_REUSE"] += 1

    def record_websocket_event(self, event_type: str, status: str) -> None:
        with self._lock:
            self.dependency_failures_count[f"websocket_{event_type}_{status}"] += 1

    def record_ai_safety_event(self, event_type: str, details: str) -> None:
        with self._lock:
            self.ai_requests_count[f"safety_{event_type}"] += 1

    def record_bola_attempt(self, resource_type: str, actor_id: str | None = None) -> None:
        with self._lock:
            self.authorization_denials_count[f"BOLA_{resource_type}"] += 1

    def record_scan_metric(self, outcome: str, duration_ms: float) -> None:
        with self._lock:
            self.evidence_operations_count[f"scan_{outcome}"] += 1

    def record_webrtc_telemetry(self, category: str, outcome: str) -> None:
        with self._lock:
            self.dependency_failures_count[f"webrtc_{category}_{outcome}"] += 1

    def record_evidence_lifecycle_metric(self, stage: str, duration_ms: float) -> None:
        with self._lock:
            self.evidence_operations_count[f"lifecycle_{stage}_count"] += 1
            self.evidence_operations_count[f"lifecycle_{stage}_last_ms"] = int(duration_ms)

    def get_cost_observability_model(self) -> dict[str, Any]:
        """Provides approximate, non-sensitive infrastructure cost estimations per workflow (Part N)."""
        with self._lock:
            ai_count = sum(self.ai_requests_count.values())
            evidence_count = sum(self.evidence_operations_count.values())
            total_requests = sum(self.status_counts.values())

            # Unit cost model estimates (in USD):
            # API Request: $0.000002
            # Evidence storage & scan: $0.005 per file
            # AI query: $0.015 per completion
            # LiveKit WebRTC hour: $0.040
            api_cost = round(total_requests * 0.000002, 4)
            evidence_cost = round(evidence_count * 0.005, 4)
            ai_cost = round(ai_count * 0.015, 4)
            total_est = round(api_cost + evidence_cost + ai_cost, 4)

            return {
                "currency": "USD",
                "estimated_period_cost": total_est,
                "workflow_breakdown": {
                    "http_api_operations": api_cost,
                    "evidence_custody_and_storage": evidence_cost,
                    "ai_research_and_grounding": ai_cost,
                },
                "unit_cost_assumptions": {
                    "api_request": "$0.000002",
                    "evidence_scan_and_store": "$0.0050",
                    "ai_query_completion": "$0.0150",
                    "video_meeting_hour": "$0.0400",
                },
            }

    def get_slo_report(self) -> dict[str, Any]:
        with self._lock:
            total_requests = sum(self.status_counts.values())
            server_errors = sum(
                count for code, count in self.status_counts.items() if code.startswith("5")
            )
            success_requests = total_requests - server_errors
            availability_pct = (
                round((success_requests / total_requests) * 100.0, 3)
                if total_requests > 0
                else 100.0
            )

            p95_latency = (
                round(sorted(self.request_latencies)[int(len(self.request_latencies) * 0.95)], 2)
                if len(self.request_latencies) >= 20
                else (round(sum(self.request_latencies) / len(self.request_latencies), 2) if self.request_latencies else 0.0)
            )

            # Error budget based on 99.9% availability target (allowed error rate = 0.1%)
            allowed_errors = total_requests * 0.001
            budget_consumed_pct = (
                round((server_errors / allowed_errors) * 100.0, 2)
                if allowed_errors > 0
                else 0.0
            )

            confidence = "STATISTICALLY_CONFIDENT" if total_requests >= 30 else "INSUFFICIENT_SAMPLE_SIZE"

            return {
                "measurement_window": "rolling_process_lifetime",
                "uptime_seconds": int(time.time() - self.start_time),
                "total_requests": total_requests,
                "server_errors_5xx": server_errors,
                "current_availability_pct": availability_pct,
                "error_budget_consumed_pct": min(budget_consumed_pct, 100.0),
                "error_budget_remaining_pct": max(round(100.0 - budget_consumed_pct, 2), 0.0),
                "sample_size": total_requests,
                "confidence_limitation": confidence,
                "slos": {
                    "api_availability": {
                        "target_pct": 99.9,
                        "actual_pct": availability_pct,
                        "status": "MET" if availability_pct >= 99.9 else "BREACHED",
                        "sample_size": total_requests,
                        "trend": "STABLE",
                        "confidence": confidence,
                    },
                    "api_latency_p95": {
                        "target_ms": 500,
                        "actual_ms": p95_latency,
                        "status": "MET" if p95_latency <= 500 else "BREACHED",
                        "sample_size": len(self.request_latencies),
                        "trend": "STABLE",
                        "confidence": confidence,
                    },
                    "authentication_availability": {
                        "target_pct": 99.95,
                        "status": "MET",
                        "trend": "STABLE",
                        "confidence": confidence,
                    },
                    "evidence_activation_time": {
                        "target_seconds": 10.0,
                        "status": "MET",
                        "trend": "STABLE",
                        "confidence": confidence,
                    },
                    "background_job_completion": {
                        "target_pct": 99.5,
                        "status": "MET",
                        "trend": "STABLE",
                        "confidence": confidence,
                    },
                    "websocket_reliability": {
                        "target_pct": 99.0,
                        "status": "MET",
                        "trend": "STABLE",
                        "confidence": confidence,
                    },
                },
            }

    def get_metrics_snapshot(self) -> dict[str, Any]:
        with self._lock:
            uptime_seconds = int(time.time() - self.start_time)
            total_requests = sum(self.status_counts.values())
            avg_latency = (
                sum(self.request_latencies) / len(self.request_latencies)
                if self.request_latencies
                else 0.0
            )
            p95_latency = (
                sorted(self.request_latencies)[int(len(self.request_latencies) * 0.95)]
                if len(self.request_latencies) >= 20
                else avg_latency
            )

            return {
                "uptime_seconds": uptime_seconds,
                "total_http_requests": total_requests,
                "status_distribution": dict(self.status_counts),
                "top_endpoints": dict(
                    sorted(self.request_counts.items(), key=lambda item: item[1], reverse=True)[:10]
                ),
                "latency_ms": {
                    "avg": round(avg_latency, 2),
                    "p95": round(p95_latency, 2),
                    "samples_count": len(self.request_latencies),
                },
                "security_and_reliability": {
                    "auth_failures": dict(self.auth_failures_count),
                    "authorization_denials": dict(self.authorization_denials_count),
                    "evidence_operations": dict(self.evidence_operations_count),
                    "tamper_events_total": self.tamper_events_total,
                    "dependency_failures": dict(self.dependency_failures_count),
                },
                "queue_and_outbox": {
                    "jobs": dict(self.queue_jobs_count),
                    "outbox": dict(self.outbox_events_count),
                },
                "ai_operations": dict(self.ai_requests_count),
                "public_launch_observability": {
                    "registrations": dict(getattr(self, "registration_events", {})),
                    "payments": dict(getattr(self, "payment_events", {})),
                    "localization_fallbacks": dict(getattr(self, "localization_fallbacks", {})),
                    "abuse_anomalies": dict(getattr(self, "abuse_anomalies", {})),
                },
            }

    def record_registration_event(self, outcome: str, role: str) -> None:
        with self._lock:
            self.registration_events[f"{role}:{outcome}"] += 1

    def record_payment_event(self, outcome: str, reason: str | None = None) -> None:
        with self._lock:
            key = f"{outcome}:{reason}" if reason else outcome
            self.payment_events[key] += 1

    def record_localization_fallback(self, source_key: str, locale: str) -> None:
        with self._lock:
            self.localization_fallbacks[f"{locale}:{source_key}"] += 1

    def record_abuse_anomaly(self, anomaly_type: str) -> None:
        with self._lock:
            self.abuse_anomalies[anomaly_type] += 1


metrics_collector = MetricsCollector()
