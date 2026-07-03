"""Slack incoming webhook notification backend.

Sends a pipeline run summary to a Slack channel via an Incoming Webhook URL.

Usage
-----
Set ``SLACK_WEBHOOK_URL`` in your ``.env`` file, e.g.::

    SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...

The notifier is automatically skipped (no-op) when the variable is not set.

Slack incoming webhooks reference:
https://api.slack.com/messaging/webhooks
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from pollingapi.logging_config import get_logger

from .base import BaseNotifier

if TYPE_CHECKING:
    from .base import PipelineRunResult

logger = get_logger(__name__)


def _format_blocks(result: PipelineRunResult) -> list[dict]:
    """Build a Slack Block Kit message for the pipeline run result."""
    validation_alert = result.validation_status in {"warn", "fail"}
    status_emoji = ":white_check_mark:" if result.success else ":rotating_light:"
    status_label = "SUCCESS" if result.success else "FAILURE"
    if result.success and validation_alert:
        status_emoji = ":warning:"
        status_label = "WARNING"

    header_text = f"{status_emoji} pollingAPI Pipeline — {status_label}"

    fields = [
        {"type": "mrkdwn", "text": f"*Run ID*\n`{result.run_id}`"},
        {
            "type": "mrkdwn",
            "text": f"*Started*\n{result.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        },
        {"type": "mrkdwn", "text": f"*Duration*\n{result.duration_human}"},
        {
            "type": "mrkdwn",
            "text": (
                f"*Scrapers*\n{result.scrapers_succeeded} OK"
                f" / {result.scrapers_failed} failed"
                f" ({result.total_scraped_polls} new polls)"
            ),
        },
        {
            "type": "mrkdwn",
            "text": (
                f"*ETL*\n"
                f"created {result.etl_created}"
                f" | updated {result.etl_updated}"
                f" | errors {result.etl_errors}"
            ),
        },
        {
            "type": "mrkdwn",
            "text": (
                f"*Export*\n"
                f"{result.export_polls} polls"
                f" / {result.export_poll_results} results"
                f" / {result.export_raw_polls} raw"
            ),
        },
    ]
    if result.validation_status:
        valid_share = (
            f"{result.validation_valid_share:.1%}"
            if result.validation_valid_share is not None
            else "n/a"
        )
        fields.append(
            {
                "type": "mrkdwn",
                "text": (
                    f"*Validation*\n{result.validation_status.upper()}"
                    f" | valid {valid_share}"
                    f" | invalid {result.validation_invalid_polls}"
                ),
            }
        )

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text, "emoji": True},
        },
        {"type": "section", "fields": fields},
    ]

    if result.error:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *Error*\n```{result.error}```",
                },
            }
        )

    if result.scraper_errors:
        failed_lines = "\n".join(
            f"• *{worker}*: {err}" for worker, err in result.scraper_errors.items()
        )
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":x: *Failed scrapers*\n{failed_lines}",
                },
            }
        )

    if result.validation_top_failures:
        failed_lines = "\n".join(
            f"• *{item['check']}*: {item['failed']}" for item in result.validation_top_failures
        )
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: *Validation top failures*\n{failed_lines}",
                },
            }
        )

    if result.archive_created and result.archive_size_mb is not None:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":floppy_disk: Archive uploaded ({result.archive_size_mb:.1f} MB)",
                    }
                ],
            }
        )

    return blocks


class SlackNotifier(BaseNotifier):
    """Send pipeline run summaries to a Slack channel via Incoming Webhook.

    Args:
        webhook_url: Slack Incoming Webhook URL.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(self, webhook_url: str, timeout: int = 10) -> None:
        self._url = webhook_url.strip()
        self._timeout = timeout

    def is_configured(self) -> bool:
        return bool(self._url)

    def notify(self, result: PipelineRunResult) -> None:
        """POST a Block Kit message to the configured Slack webhook.

        Failures are logged but never re-raised so a notification error never
        disrupts the pipeline itself.
        """
        if not self.is_configured():
            logger.debug("SlackNotifier: no webhook URL configured, skipping")
            return

        payload = {"blocks": _format_blocks(result)}

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(self._url, data=data, method="POST")
            req.add_header("Content-Type", "application/json; charset=utf-8")

            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                status_code = resp.status
                if status_code >= 400:
                    logger.warning(f"SlackNotifier: server returned HTTP {status_code}")
                else:
                    logger.info(f"SlackNotifier: notification sent (HTTP {status_code})")

        except urllib.error.URLError as exc:
            logger.warning(f"SlackNotifier: failed to send notification — {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"SlackNotifier: unexpected error — {exc}")
