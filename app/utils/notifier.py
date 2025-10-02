import asyncio

import httpx

NTFY_TOPIC = "zweitstimme_org"  # change this to your ntfy topic


async def send_notification(title: str, message: str):
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    headers = {"Title": title, "Priority": "high"}
    async with httpx.AsyncClient() as client:
        await client.post(url, data=message.encode("utf-8"), headers=headers)


def notify_background(title: str, message: str):
    """Fire-and-forget notification (non-blocking)."""
    asyncio.create_task(send_notification(title, message))
