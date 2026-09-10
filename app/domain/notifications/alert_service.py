from typing import Any

from sqlalchemy.orm import Session

from app.core.metrics import metrics_collector
from app.models.incident import IncidentSeverity


class ProductionAlert:
    def __init__(
        self,
        alert_id: str,
        name: str,
        severity: IncidentSeverity,
        status: str,
        trigger_condition: str,
        current_value: Any,
        threshold: Any,
        recommended_action: str,
        owner: str,
        runbook_ref: str,
    ):
        self.alert_id = alert_id
        self.name = name
        self.severity = severity
        self.status = status
        self.trigger_condition = trigger_condition
        self.current_value = current_value
        self.threshold = threshold
        self.recommended_action = recommended_action
        self.owner = owner
        self.runbook_ref = runbook_ref

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "severity": self.severity.value,
            "status": self.status,
            "trigger_condition": self.trigger_condition,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "recommended_action": self.recommended_action,
            "owner": self.owner,
            "runbook_ref": self.runbook_ref,
        }


class AlertService:
    """Evaluates real-time operational alert rules against metrics telemetry."""

    def __init__(self, db: Session | None = None):
        self.db = db

    def evaluate_alerts(self) -> list[dict[str, Any]]:
        snapshot = metrics_collector.get_metrics_snapshot()
        alerts = []

        # 1. 5xx Server Error Rate
        total_reqs = snapshot["total_http_requests"]
        err_5xx = sum(
            count for code, count in snapshot["status_distribution"].items() if code.startswith("5")
        )
        rate_5xx = (err_5xx / total_reqs) if total_reqs > 0 else 0.0
        status_5xx = "FIRING" if (total_reqs >= 50 and rate_5xx > 0.005) else "HEALTHY"
        alerts.append(
            ProductionAlert(
                alert_id="ALERT-HTTP-5XX-SPIKE",
                name="Sustained HTTP 5xx Error Spike",
                severity=IncidentSeverity.SEV1_CRITICAL if rate_5xx > 0.05 else IncidentSeverity.SEV2_HIGH,
                status=status_5xx,
                trigger_condition="5xx error rate > 0.5% with >= 50 requests",
                current_value=f"{rate_5xx * 100:.2f}%",
                threshold="0.50%",
                recommended_action="Inspect application error logs, database connection pool, and upstream dependency timeouts.",
                owner="Platform SRE",
                runbook_ref="docs/24_PRODUCTION_DEPLOYMENT_RUNBOOK.md#incident-response",
            ).to_dict()
        )

        # 2. Evidence Storage Tampering
        tamper_count = snapshot["security_and_reliability"]["tamper_events_total"]
        status_tamper = "FIRING" if tamper_count > 0 else "HEALTHY"
        alerts.append(
            ProductionAlert(
                alert_id="ALERT-EVIDENCE-TAMPERING",
                name="Evidence Locker Cryptographic Hash Mismatch",
                severity=IncidentSeverity.SEV1_CRITICAL,
                status=status_tamper,
                trigger_condition="tamper_events_total > 0",
                current_value=tamper_count,
                threshold=0,
                recommended_action="Execute immediate security freeze on affected evidence, trigger forensic audit of S3 bucket logs.",
                owner="Security Operations (SecOps)",
                runbook_ref="docs/23_INCIDENT_RESPONSE.md#playbook-evidence-tampering",
            ).to_dict()
        )

        # 3. Authentication Attack / Stuffing Spike
        auth_failures = sum(snapshot["security_and_reliability"]["auth_failures"].values())
        status_auth = "FIRING" if auth_failures >= 30 else "HEALTHY"
        alerts.append(
            ProductionAlert(
                alert_id="ALERT-AUTH-ATTACK-SPIKE",
                name="Authentication Failure Anomaly",
                severity=IncidentSeverity.SEV2_HIGH,
                status=status_auth,
                trigger_condition="Total auth failure anomalies >= 30",
                current_value=auth_failures,
                threshold=30,
                recommended_action="Check rate limiting thresholds, inspect offending IP ranges, check for credential stuffing.",
                owner="Security Operations (SecOps)",
                runbook_ref="docs/23_INCIDENT_RESPONSE.md#playbook-account-takeover",
            ).to_dict()
        )

        # 4. Background Job Dead-Letter Backlog
        dlq_jobs = snapshot["queue_and_outbox"]["jobs"].get("DEAD_LETTER", 0)
        status_dlq = "FIRING" if dlq_jobs >= 5 else "HEALTHY"
        alerts.append(
            ProductionAlert(
                alert_id="ALERT-DLQ-BACKLOG",
                name="Background Worker Dead-Letter Queue Growth",
                severity=IncidentSeverity.SEV3_MEDIUM,
                status=status_dlq,
                trigger_condition="Exhausted dead-letter jobs >= 5",
                current_value=dlq_jobs,
                threshold=5,
                recommended_action="Review background job stack traces in /admin/jobs, check downstream API outages.",
                owner="Application Engineering",
                runbook_ref="docs/29_SRE_SLOS_AND_ALERTING.md#dead-letter-backlog",
            ).to_dict()
        )

        # 5. Dependency Outage
        dep_failures = sum(snapshot["security_and_reliability"]["dependency_failures"].values())
        status_dep = "FIRING" if dep_failures >= 10 else "HEALTHY"
        alerts.append(
            ProductionAlert(
                alert_id="ALERT-DEPENDENCY-FAILURE",
                name="External Service or Circuit Breaker Trip",
                severity=IncidentSeverity.SEV2_HIGH,
                status=status_dep,
                trigger_condition="External dependency failure events >= 10",
                current_value=dep_failures,
                threshold=10,
                recommended_action="Inspect Redis, LiveKit SFU, S3, or ClamAV connectivity metrics.",
                owner="Platform SRE",
                runbook_ref="docs/24_PRODUCTION_DEPLOYMENT_RUNBOOK.md#infrastructure-failure",
            ).to_dict()
        )

        return alerts
