"""Observability / notification layer for pollingAPI.

Public API
----------
- :class:`PipelineRunResult` — dataclass holding all stats for one pipeline run
- :class:`BaseNotifier` — abstract base for notification backends
- :class:`NotificationManager` — fan-out dispatcher
- :class:`NtfyNotifier` — ntfy.sh push notification backend
- :func:`create_notification_manager` — factory that builds a configured manager

Example
-------
::

    from pollingapi.notifications import create_notification_manager, PipelineRunResult

    manager = create_notification_manager()
    result = PipelineRunResult(success=True, ...)
    manager.notify(result)
"""

from __future__ import annotations

from .base import BaseNotifier, PipelineRunResult, ScraperRunResult
from .manager import NotificationManager
from .ntfy import NtfyNotifier
from .slack import SlackNotifier


def create_notification_manager() -> NotificationManager:
    """Build a :class:`NotificationManager` from the current application settings.

    Automatically registers active backends:

    - :class:`NtfyNotifier` if ``NTFY_URL`` is set in the environment / ``.env``.
    - :class:`SlackNotifier` if ``SLACK_WEBHOOK_URL`` is set.

    Returns:
        A ready-to-use :class:`NotificationManager`.
    """
    # Import here to avoid a circular import at module load time
    from pollingapi.core import settings

    manager = NotificationManager()

    if settings.ntfy_url:
        manager.register(
            NtfyNotifier(
                ntfy_url=settings.ntfy_url,
                title_prefix=settings.ntfy_topic_title,
            )
        )

    if settings.slack_webhook_url:
        manager.register(SlackNotifier(webhook_url=settings.slack_webhook_url))

    return manager


__all__ = [
    "BaseNotifier",
    "NtfyNotifier",
    "SlackNotifier",
    "NotificationManager",
    "PipelineRunResult",
    "ScraperRunResult",
    "create_notification_manager",
]
