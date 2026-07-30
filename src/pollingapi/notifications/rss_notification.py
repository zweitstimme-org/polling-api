"""RSS notification backend.

Writes pipeline run summaries to a local RSS XML file. This is useful when the
pipeline should publish notification history without sending push messages.
"""

from __future__ import annotations

from datetime import UTC
from email.utils import format_datetime
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from pollingapi.logging_config import get_logger

from .base import BaseNotifier
from .ntfy import _format_message

if TYPE_CHECKING:
    from .base import PipelineRunResult

logger = get_logger(__name__)


class RssNotifier(BaseNotifier):
    """Write pipeline run summaries to an RSS feed file."""

    def __init__(
        self,
        feed_path: str | Path,
        title_prefix: str = "pollingAPI",
        feed_link: str = "/v2/pipeline-notifications.rss",
        max_items: int = 50,
    ) -> None:
        self._feed_path = Path(feed_path)
        self._title_prefix = title_prefix
        self._feed_link = feed_link
        self._max_items = max_items

    def is_configured(self) -> bool:
        return bool(self._feed_path)

    def notify(self, result: PipelineRunResult) -> None:
        if not self.is_configured():
            logger.debug("RssNotifier: no feed path configured, skipping")
            return

        try:
            self._feed_path.parent.mkdir(parents=True, exist_ok=True)
            root, channel = self._load_feed()
            self._prepend_item(channel, result)
            self._trim_items(channel)
            ET.ElementTree(root).write(
                self._feed_path,
                encoding="utf-8",
                xml_declaration=True,
            )
            logger.info(f"RssNotifier: wrote notification feed to {self._feed_path}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"RssNotifier: unexpected error - {exc}")

    def _load_feed(self) -> tuple[ET.Element, ET.Element]:
        if self._feed_path.exists():
            root = ET.parse(self._feed_path).getroot()
            channel = root.find("channel")
            if channel is not None:
                return root, channel

        root = ET.Element("rss", version="2.0")
        channel = ET.SubElement(root, "channel")
        ET.SubElement(channel, "title").text = f"{self._title_prefix} Pipeline Notifications"
        ET.SubElement(channel, "link").text = self._feed_link
        ET.SubElement(channel, "description").text = "Pipeline run notifications from pollingAPI."
        return root, channel

    def _prepend_item(self, channel: ET.Element, result: PipelineRunResult) -> None:
        for item in list(channel.findall("item")):
            guid = item.findtext("guid")
            if guid == result.run_id:
                channel.remove(item)

        status = "SUCCESS" if result.success else "FAILURE"
        if result.success and (
            result.zero_poll_workers or result.validation_status in {"warn", "fail"}
        ):
            status = "WARNING"

        item = ET.Element("item")
        ET.SubElement(item, "title").text = f"[{self._title_prefix}] Pipeline {status}"
        ET.SubElement(item, "link").text = self._feed_link
        ET.SubElement(item, "guid", isPermaLink="false").text = result.run_id
        finished_at = result.finished_at
        if finished_at.tzinfo is None:
            finished_at = finished_at.replace(tzinfo=UTC)
        ET.SubElement(item, "pubDate").text = format_datetime(finished_at)
        ET.SubElement(item, "description").text = _format_message(result, self._title_prefix)
        channel.insert(_first_item_index(channel), item)

    def _trim_items(self, channel: ET.Element) -> None:
        items = channel.findall("item")
        for item in items[self._max_items :]:
            channel.remove(item)


def _first_item_index(channel: ET.Element) -> int:
    for index, child in enumerate(list(channel)):
        if child.tag == "item":
            return index
    return len(channel)
