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
        if self._initialized:
            return
        self._lock = threading.Lock()
        self.request_counts = defaultdict(int)
        self.status_counts = defaultdict(int)
        self.request_latencies: list[float] = []
        self.max_latency_samples = 1000
        self.start_time = time.time()
        self.ai_requests_count = defaultdict(int)
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
                "ai_operations": dict(self.ai_requests_count),
            }


metrics_collector = MetricsCollector()
