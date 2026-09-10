"""Asynchronous Background Jobs, Outbox & Maintenance Domain package."""

import importlib
from typing import Any

__all__ = ['ChangeFeedService', 'JobScheduler', 'JobService', 'JobWorker', 'OutboxService']

_MODULE_MAP = {
    "JobService": "job_service",
    "OutboxService": "outbox_service",
    "JobScheduler": "job_scheduler",
    "JobWorker": "job_worker",
    "ChangeFeedService": "change_feed_service",
}


def __getattr__(name: str) -> Any:
    mod_name = _MODULE_MAP.get(name)
    if mod_name:
        mod = importlib.import_module(f"app.domain.jobs.{mod_name}")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
