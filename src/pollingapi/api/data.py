"""Archive API router for data downloads."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from pollingapi.services.s3 import ArchiveMetadata, S3Service

router = APIRouter(prefix="/archive", tags=["archive"])

s3_service = S3Service()


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Data Archive - Zweitstimme Polling API</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #f5f5f5;
        }
        h1 { color: #333; margin-bottom: 10px; }
        .subtitle { color: #666; margin-bottom: 30px; }
        .archive-list { background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .archive-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px;
            border-bottom: 1px solid #eee;
        }
        .archive-item:last-child { border-bottom: none; }
        .archive-info { flex: 1; }
        .archive-name { font-weight: 600; font-size: 16px; color: #333; }
        .archive-meta { font-size: 13px; color: #888; margin-top: 4px; }
        .download-btn {
            background: #007bff;
            color: white;
            padding: 10px 20px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.2s;
        }
        .download-btn:hover { background: #0056b3; }
        .empty { text-align: center; padding: 60px 20px; color: #888; }
        .footer { margin-top: 30px; text-align: center; font-size: 13px; color: #888; }
        .footer a { color: #007bff; text-decoration: none; }
        .footer a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Data Archive</h1>
    <p class="subtitle">Download complete snapshots of the Zweitstimme polling database</p>

    ARCHIVE_LIST

    <div class="footer">
        <p>Powered by <a href="https://github.com/zweitstimme-org/pollingAPI">Zweitstimme.org polling-api</a></p>
    </div>
</body>
</html>"""

ARCHIVE_ITEM_TEMPLATE = """        <div class="archive-item">
            <div class="archive-info">
                <div class="archive-name">ARCHIVE_NAME</div>
                <div class="archive-meta">ARCHIVE_META</div>
            </div>
            <a href="ARCHIVE_URL" class="download-btn">Download</a>
        </div>"""

EMPTY_STATE = """    <div class="archive-list">
        <div class="empty">
            <p>No archives available yet.</p>
            <p>Archives are created periodically. Check back later.</p>
        </div>
    </div>"""


def format_size(size_bytes: int | float) -> str:
    """Format file size in human-readable format."""
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def render_html_archive_list(archives: list[ArchiveMetadata]) -> str:
    """Render HTML archive list."""
    if not archives:
        return HTML_TEMPLATE.replace("ARCHIVE_LIST", EMPTY_STATE)

    items = []
    for archive in archives:
        size_str = format_size(archive.size)
        date_str = archive.created_at.strftime("%B %d, %Y at %H:%M")
        meta = f"{size_str} • {date_str}"

        items.append(
            ARCHIVE_ITEM_TEMPLATE.replace("ARCHIVE_NAME", archive.filename)
            .replace("ARCHIVE_META", meta)
            .replace("ARCHIVE_URL", archive.public_url)
        )

    list_html = """    <div class="archive-list">\n""" + "\n".join(items) + """\n    </div>"""
    return HTML_TEMPLATE.replace("ARCHIVE_LIST", list_html)


@router.get("", response_class=HTMLResponse)
def list_archives_html():
    """List all available data archives as HTML."""
    archives = s3_service.list_archives()
    return render_html_archive_list(archives)


@router.get(".json")
def list_archives_json():
    """List all available data archives as JSON."""
    archives = s3_service.list_archives()

    if not s3_service.is_configured():
        return JSONResponse(
            {"error": "Archive service not configured", "archives": []},
            status_code=503,
        )

    return {
        "archives": [
            {
                "filename": a.filename,
                "size": a.size,
                "size_formatted": format_size(a.size),
                "created_at": a.created_at.isoformat(),
                "download_url": a.public_url,
            }
            for a in archives
        ],
        "count": len(archives),
    }


@router.get("latest")
def get_latest_archive():
    """Get the latest archive."""
    archives = s3_service.list_archives()

    if not s3_service.is_configured():
        return JSONResponse(
            {"error": "Archive service not configured"},
            status_code=503,
        )

    if not archives:
        raise HTTPException(status_code=404, detail="No archives available")

    latest = archives[0]
    return {
        "filename": latest.filename,
        "size": latest.size,
        "size_formatted": format_size(latest.size),
        "created_at": latest.created_at.isoformat(),
        "download_url": latest.public_url,
    }


@router.get("{filename}")
def get_archive(filename: str):
    """Get metadata for a specific archive."""
    archive = s3_service.get_archive(filename)

    if not s3_service.is_configured():
        return JSONResponse(
            {"error": "Archive service not configured"},
            status_code=503,
        )

    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found")

    return {
        "filename": archive.filename,
        "size": archive.size,
        "size_formatted": format_size(archive.size),
        "created_at": archive.created_at.isoformat(),
        "download_url": archive.public_url,
    }


@router.get("{filename}/download")
def download_archive(filename: str):
    """Redirect to download URL for a specific archive."""
    archive = s3_service.get_archive(filename)

    if not s3_service.is_configured():
        raise HTTPException(status_code=503, detail="Archive service not configured")

    if not archive:
        raise HTTPException(status_code=404, detail="Archive not found")

    return RedirectResponse(url=archive.public_url)
