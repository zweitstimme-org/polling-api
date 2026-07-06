"""ntfy.sh notification backend.

Sends a plain-text pipeline summary to an ntfy topic via HTTP POST.

Usage
-----
Configure ``NTFY_URL`` in your ``.env`` file, e.g.::

    NTFY_URL=https://ntfy.sh/your-private-topic

The notifier is automatically skipped (no-op) when ``NTFY_URL`` is not set.

ntfy API reference: https://docs.ntfy.sh/publish/
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from pollingapi.logging_config import get_logger

from .base import BaseNotifier

if TYPE_CHECKING:
    from .base import PipelineRunResult

logger = get_logger(__name__)

# ntfy priority levels (https://docs.ntfy.sh/publish/#message-priority)
_PRIORITY_DEFAULT = "default"
_PRIORITY_HIGH = "high"
_PRIORITY_URGENT = "urgent"


def _format_message(result: PipelineRunResult, title_prefix: str) -> str:
    """Build the plain-text notification body."""
    scraper_alert = bool(result.zero_poll_workers)
    status = "SUCCESS" if result.success else "FAILURE"
    if result.success and scraper_alert:
        status = "WARNING"
    lines: list[str] = [
        f"{'=' * 40}",
        f"  {title_prefix} — {status}",
        f"{'=' * 40}",
        "",
        f"Run ID  : {result.run_id}",
        f"Started : {result.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Duration: {result.duration_human}",
    ]

    if result.error:
        lines += [
            "",
            "ERROR",
            f"  {result.error}",
        ]

    # ------------------------------------------------------------------ scraper
    lines += [
        "",
        "--- Scraper ---",
        f"  Workers  : {result.scrapers_run} run  |  {result.scrapers_succeeded} OK"
        f"  |  {result.scrapers_failed} failed",
        f"  New polls: {result.total_scraped_polls}",
    ]

    if result.scraper_errors:
        lines.append("  Failed workers:")
        for worker, err in result.scraper_errors.items():
            lines.append(f"    • {worker}: {err}")

    if result.zero_poll_workers:
        lines += [
            "  Zero-poll warning:",
            "    Previously working workers found no polls:",
        ]
        for worker in result.zero_poll_workers:
            lines.append(f"    • {worker}")

    # ------------------------------------------------------------------ ETL
    lines += [
        "",
        "--- ETL Cleaner ---",
        f"  Processed: {result.etl_processed}",
        f"  Created  : {result.etl_created}  |  Updated: {result.etl_updated}",
        f"  Skipped  : {result.etl_skipped}  |  Errors : {result.etl_errors}",
    ]

    # ------------------------------------------------------------------ validation
    if result.validation_status:
        valid_share = (
            f"{result.validation_valid_share:.1%}"
            if result.validation_valid_share is not None
            else "n/a"
        )
        lines += [
            "",
            "--- Validation ---",
            f"  Status   : {result.validation_status.upper()}",
            f"  Valid    : {result.validation_valid_polls}/{result.validation_total_polls}"
            f" ({valid_share})",
            f"  Invalid  : {result.validation_invalid_polls}",
            f"  Warnings : {result.validation_warning_polls}",
        ]
        if result.validation_top_failures:
            lines.append("  Top failures:")
            for item in result.validation_top_failures:
                lines.append(f"    • {item['check']}: {item['failed']}")

    # ------------------------------------------------------------------ export
    lines += [
        "",
        "--- Export ---",
        f"  Polls    : {result.export_polls}",
        f"  Results  : {result.export_poll_results}",
        f"  Raw polls: {result.export_raw_polls}",
    ]

    # ------------------------------------------------------------------ archive
    if result.archive_created:
        size_str = f"{result.archive_size_mb:.1f} MB" if result.archive_size_mb is not None else "?"
        lines += [
            "",
            "--- Archive ---",
            f"  Uploaded: yes  ({size_str})",
        ]

    return "\n".join(lines)


class NtfyNotifier(BaseNotifier):
    """Send pipeline run summaries to an ntfy topic.

    Args:
        ntfy_url: Full URL of the ntfy topic, e.g. ``https://ntfy.sh/my-topic``.
        title_prefix: Short string prepended to every notification title.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        ntfy_url: str,
        title_prefix: str = "pollingAPI",
        timeout: int = 10,
    ) -> None:
        self._url = ntfy_url.rstrip("/")
        self._title_prefix = title_prefix
        self._timeout = timeout

    def is_configured(self) -> bool:
        return bool(self._url)

    def notify(self, result: PipelineRunResult) -> None:
        """POST a summary message to the configured ntfy topic.

        Failures are logged but never re-raised so a notification error never
        disrupts the pipeline itself.
        """
        if not self.is_configured():
            logger.debug("NtfyNotifier: no URL configured, skipping")
            return

        scraper_alert = bool(result.zero_poll_workers)
        status = "SUCCESS" if result.success else "FAILURE"
        if result.success and scraper_alert:
            status = "WARNING"
        title = f"[{self._title_prefix}] Pipeline {status}"
        body = _format_message(result, self._title_prefix)
        validation_alert = result.validation_status in {"warn", "fail"}
        if not result.success:
            priority = _PRIORITY_URGENT
        elif validation_alert or scraper_alert:
            priority = _PRIORITY_HIGH
        else:
            priority = _PRIORITY_DEFAULT

        # Tags: white_check_mark on success, rotating_light on failure
        tags = (
            "warning"
            if (validation_alert or scraper_alert) and result.success
            else "white_check_mark"
        )
        if not result.success:
            tags = "rotating_light,skull"

        try:
            data = body.encode("utf-8")
            req = urllib.request.Request(
                self._url,
                data=data,
                method="POST",
            )
            req.add_header("Title", title)
            req.add_header("Priority", priority)
            req.add_header("Tags", tags)
            req.add_header("Content-Type", "text/plain; charset=utf-8")

            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                status_code = resp.status
                if status_code >= 400:
                    logger.warning(
                        f"NtfyNotifier: server returned HTTP {status_code} for {self._url}"
                    )
                else:
                    logger.info(
                        f"NtfyNotifier: notification sent to {self._url} (HTTP {status_code})"
                    )

        except urllib.error.URLError as exc:
            logger.warning(f"NtfyNotifier: failed to send notification — {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"NtfyNotifier: unexpected error — {exc}")
