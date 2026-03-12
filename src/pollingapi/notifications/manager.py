"""NotificationManager — dispatches pipeline run results to all active backends.

Adding a new notification service is a one-liner::

    manager.register(MyNewNotifier(...))

All registered notifiers are called in order.  A failing notifier does not
prevent the others from running — each BaseNotifier.notify() is responsible
for its own error handling.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pollingapi.logging_config import get_logger

from .base import BaseNotifier

if TYPE_CHECKING:
    from .base import PipelineRunResult

logger = get_logger(__name__)


class NotificationManager:
    """Holds a collection of :class:`BaseNotifier` instances and fans out notifications.

    Args:
        notifiers: Optional list of notifiers to register immediately.
    """

    def __init__(self, notifiers: list[BaseNotifier] | None = None) -> None:
        self._notifiers: list[BaseNotifier] = []
        for n in notifiers or []:
            self.register(n)

    def register(self, notifier: BaseNotifier) -> None:
        """Add a notifier to the dispatch list.

        Only registers the notifier if it reports itself as configured.

        Args:
            notifier: A :class:`BaseNotifier` subclass instance.
        """
        if notifier.is_configured():
            self._notifiers.append(notifier)
            logger.debug(f"NotificationManager: registered {type(notifier).__name__}")
        else:
            logger.debug(f"NotificationManager: skipped {type(notifier).__name__} (not configured)")

    def notify(self, result: PipelineRunResult) -> None:
        """Fan out the run result to all registered notifiers.

        Args:
            result: The completed :class:`~pollingapi.notifications.base.PipelineRunResult`.
        """
        if not self._notifiers:
            logger.debug("NotificationManager: no notifiers registered, skipping")
            return

        for notifier in self._notifiers:
            try:
                notifier.notify(result)
            except Exception as exc:  # noqa: BLE001
                # Belt-and-suspenders: BaseNotifier.notify() should already catch,
                # but we guard here too so one broken notifier never affects others.
                logger.warning(
                    f"NotificationManager: {type(notifier).__name__}.notify() raised — {exc}"
                )

    @property
    def notifier_count(self) -> int:
        """Number of active notifiers."""
        return len(self._notifiers)
