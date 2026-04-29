"""CLI entry points for zweitstimme."""

from pathlib import Path

import typer
from sqlalchemy import text
from sqlalchemy.orm import Session

from pollingapi.cleaner import run_cleaning_pipeline
from pollingapi.core import PROJECT_ROOT, settings
from pollingapi.database import SessionLocal, init_db, seed_all_from_json
from pollingapi.logging_config import get_logger, setup_logging
from pollingapi.notifications import PipelineRunResult, create_notification_manager
from pollingapi.scraper.context import RunContext
from pollingapi.scraper.runner import ScraperRunner
from pollingapi.services import ExportService, S3Service

# Initialize logging with default settings
setup_logging()

app = typer.Typer(
    help="Zweitstimme CLI - German Election Polling Data Management",
    no_args_is_help=True,
)
logger = get_logger(__name__)


def get_db() -> Session:
    """Get database session."""
    return SessionLocal()


@app.command(name="db:ping")
def db_ping():
    """Verify database connectivity."""
    db = get_db()
    try:
        db.execute(text("SELECT 1"))
        logger.debug("Database ping successful")
        typer.echo("✓ Database connection: OK")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        typer.echo(f"✗ Database connection failed: {e}", err=True)
        raise typer.Exit(1) from e


@app.command(name="db:init")
def db_init(
    force: bool = typer.Option(False, "--force", "-f", help="Drop and recreate all tables"),
):
    """Initialize database tables."""
    if force:
        typer.echo("Force mode: dropping all tables...")
    init_db(drop_all=force)
    typer.echo("✓ Database initialized successfully")


@app.command(name="db:seed")
def db_seed():
    """Seed reference tables from JSON files."""
    db = get_db()

    logger.info("Seeding database from JSON files")

    results = seed_all_from_json(db)

    typer.echo("✓ Seeded reference tables from JSON files:")
    for table, count in results.items():
        typer.echo(f"  • {table}: {count} records")
        logger.info(f"Seeded {count} records into {table}")


@app.command(name="db:tables")
def db_tables():
    """List database tables with row counts."""
    from pollingapi.models import (
        Election,
        Institute,
        Method,
        Party,
        PipelineRun,
        Poll,
        PollResult,
        Provider,
        RawPoll,
        Tasker,
    )

    db = get_db()
    tables = [
        ("polls_raw", RawPoll),
        ("polls", Poll),
        ("poll_results", PollResult),
        ("institutes", Institute),
        ("parties", Party),
        ("providers", Provider),
        ("elections", Election),
        ("methods", Method),
        ("taskers", Tasker),
        ("pipeline_runs", PipelineRun),
    ]

    typer.echo("Table row counts:")
    typer.echo("-" * 40)
    for name, model in tables:
        count = db.query(model).count()
        typer.echo(f"  {name}: {count}")


@app.command(name="export:all")
def db_export():
    """Export data to JSON, CSV, and Parquet files."""
    db = get_db()
    export_service = ExportService(db)
    counts = export_service.export_all()
    typer.echo(f"✓ Exported to {settings.export_dir}:")
    typer.echo(f"  polls: {counts['polls']}")
    typer.echo(f"  poll_results: {counts['results']}")
    typer.echo(f"  observations: {counts['observations']}")
    typer.echo(f"  raw_polls: {counts['raw']}")


@app.command(name="db:reset")
def db_reset(
    confirm: bool = typer.Option(False, "--confirm", help="Confirm destructive operation"),
):
    """Reset database (drop all tables and recreate)."""
    if not confirm:
        typer.echo("⚠️  This will delete all data! Use --confirm to proceed.", err=True)
        raise typer.Exit(1)

    typer.echo("Resetting database...")
    init_db(drop_all=True)
    typer.echo("✓ Database reset successfully")


@app.command(name="scraper:run")
def scraper_run(
    worker: str = typer.Argument(
        ...,
        help="Worker name (e.g., 'forsa', 'bayern', 'all', 'current')",
    ),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Dry run (don't insert to DB)"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force run (ignore initial run markers)"
    ),
):
    """Run a specific scraper worker or all workers."""
    # Reconfigure logging for debug mode if needed
    if debug:
        setup_logging(log_level="DEBUG")

    db = get_db()
    context = RunContext.for_project(debug=debug)

    logger.info(f"Starting scraper run: worker={worker}, dry_run={dry_run}, debug={debug}")

    runner = ScraperRunner(db, context=context, dry_run=dry_run or debug)

    if worker.lower() in {"all", "current"}:
        current_only = worker.lower() == "current"
        logger.info("Running current scrapers" if current_only else "Running all scrapers")
        results = runner.run_all(include_dawum=not current_only, current_only=current_only)

        # Log results
        total_success = sum(1 for v in results.values() if isinstance(v, int))
        total_polls = sum(v for v in results.values() if isinstance(v, int))
        logger.info(f"Scraper run completed: {total_success} successful, {total_polls} total polls")

        typer.echo("\nResults:")
        typer.echo("-" * 50)
        for name, count in results.items():
            if isinstance(count, int):
                typer.echo(f"  ✓ {name}: {count} polls")
                logger.info(f"Scraper {name}: {count} polls inserted")
            else:
                typer.echo(f"  ✗ {name}: {count}")
                logger.error(f"Scraper {name} failed: {count}")
    else:
        logger.info(f"Running scraper: {worker}")
        try:
            count = runner.run_worker(worker)
            message = (
                f"would insert {count} polls" if dry_run or debug else f"inserted {count} polls"
            )
            typer.echo(f"✓ {worker}: {message}")
            logger.info(f"Scraper {worker} completed: {message}")
        except ValueError as e:
            logger.error(f"Scraper {worker} failed: {e}")
            typer.echo(f"✗ Error: {e}", err=True)
            typer.echo("\nAvailable workers:")
            for name in runner.list_workers():
                typer.echo(f"  - {name}")
            raise typer.Exit(1) from e


@app.command(name="scraper:list")
def scraper_list():
    """List all available scraper workers."""
    db = get_db()
    runner = ScraperRunner(db)

    typer.echo("Available scraper workers:")
    typer.echo("-" * 50)
    for name in sorted(runner.list_workers()):
        typer.echo(f"  • {name}")


@app.command(name="scraper:status")
def scraper_status():
    """Show scraper run status and data freshness."""

    typer.echo("Scraper status:")
    typer.echo("-" * 50)

    data_dir = settings.data_dir
    if not data_dir.exists():
        typer.echo("  No data directory found")
        return

    workers = [d.name for d in data_dir.iterdir() if d.is_dir()]
    for worker in sorted(workers):
        marker_file = data_dir / worker / ".historic_urls_processed"
        if marker_file.exists():
            typer.echo(f"  ✓ {worker}: Historic data processed")
        else:
            typer.echo(f"  ○ {worker}: Awaiting initial run")


@app.command(name="pipeline:clean")
def pipeline_clean(
    limit: int | None = typer.Option(None, "--limit", "-l", help="Limit number of rows to process"),
    reprocess: bool = typer.Option(False, "--reprocess", help="Reprocess already-cleaned rows"),
    rebuild: bool = typer.Option(
        False,
        "--rebuild",
        help="Delete cleaned poll/reference rows and rebuild from immutable raw rows",
    ),
):
    """Run data cleaning pipeline on raw polls."""
    db = get_db()
    stats = run_cleaning_pipeline(db, limit=limit, reprocess=reprocess, rebuild=rebuild)

    typer.echo("✓ Cleaning complete:")
    typer.echo(f"  Processed: {stats['processed']}")
    typer.echo(f"  Created: {stats['created']}")
    typer.echo(f"  Updated: {stats['updated']}")
    typer.echo(f"  Skipped: {stats['skipped']}")
    typer.echo(f"  Errors: {stats['errors']}")


@app.command(name="pipeline:run")
def pipeline_run(
    include_dawum: bool = typer.Option(True, "--dawum/--no-dawum", help="Include DAWUM API"),
):
    """Run full pipeline (scraper + cleaner + export + archive)."""
    import shutil
    from datetime import datetime

    from pollingapi.models import PipelineRun

    db = get_db()
    s3_service = S3Service()

    # ------------------------------------------------------------------ setup
    run_result = PipelineRunResult()
    run_result.started_at = datetime.now()
    notifier = create_notification_manager()

    try:
        # -------------------------------------------------------------- scraper
        typer.echo("=== Running Scraper ===")
        typer.echo("")
        context = RunContext.for_project(run_id=run_result.run_id)
        runner = ScraperRunner(db, context=context)
        scraper_results = runner.run_all(include_dawum=include_dawum)

        for name, value in scraper_results.items():
            run_result.scrapers_run += 1
            if isinstance(value, int):
                run_result.scrapers_succeeded += 1
                run_result.total_scraped_polls += value
            else:
                run_result.scrapers_failed += 1
                run_result.scraper_errors[name] = str(value)

        typer.echo(f"✓ Total scraped: {run_result.total_scraped_polls} polls")
        typer.echo(
            f"  Workers: {run_result.scrapers_succeeded} OK / {run_result.scrapers_failed} failed"
        )
        if run_result.scraper_errors:
            for name, err in run_result.scraper_errors.items():
                typer.echo(f"  ✗ {name}: {err}")
        typer.echo("")

        # -------------------------------------------------------------- cleaner
        typer.echo("=== Running Cleaner ===")
        typer.echo("")
        etl_stats = run_cleaning_pipeline(db)
        run_result.etl_processed = etl_stats["processed"]
        run_result.etl_created = etl_stats["created"]
        run_result.etl_updated = etl_stats["updated"]
        run_result.etl_skipped = etl_stats["skipped"]
        run_result.etl_errors = etl_stats["errors"]

        typer.echo(f"✓ Processed : {run_result.etl_processed}")
        typer.echo(f"✓ Created   : {run_result.etl_created}")
        typer.echo(f"✓ Updated   : {run_result.etl_updated}")
        typer.echo(f"✓ Skipped   : {run_result.etl_skipped}")
        typer.echo(f"✓ Errors    : {run_result.etl_errors}")
        typer.echo("")

        # -------------------------------------------------------------- export
        typer.echo("=== Running Export ===")
        typer.echo("")
        export_service = ExportService(db)
        export_counts = export_service.export_all()
        run_result.export_polls = export_counts["polls"]
        run_result.export_poll_results = export_counts["results"]
        run_result.export_raw_polls = export_counts["raw"]

        typer.echo(
            f"✓ Exported {run_result.export_polls} polls,"
            f" {run_result.export_poll_results} poll results,"
            f" and {run_result.export_raw_polls} raw polls"
        )
        typer.echo("")

        # -------------------------------------------------------------- archive
        if s3_service.is_configured():
            typer.echo("=== Creating Archive ===")
            typer.echo("")

            data_dir = settings.data_dir
            json_dir = PROJECT_ROOT / "json"
            archive_name = f"pollingapi-archive-{datetime.now().strftime('%Y-%m-%d-%H-%M')}.zip"
            archive_path = settings.data_dir.parent / archive_name

            import shutil as sh
            import tempfile

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                sh.copytree(data_dir, tmp_path / "data")
                sh.copytree(json_dir, tmp_path / "json")

                shutil.make_archive(
                    base_name=str(archive_path.with_suffix("")),
                    format="zip",
                    root_dir=str(tmp_path),
                )

            archive_size = archive_path.stat().st_size
            archive_size_mb = archive_size / 1024 / 1024
            typer.echo(f"✓ Created archive: {archive_name} ({archive_size_mb:.1f} MB)")

            typer.echo(f"Uploading to S3 bucket: {s3_service.bucket_name}...")

            key = f"archives/{archive_name}"
            if s3_service.upload_archive(archive_path, key):
                typer.echo(f"✓ Uploaded to s3://{s3_service.bucket_name}/{key}")

                archives = s3_service.list_archives()
                s3_service.upload_index(archives)
                typer.echo("✓ Updated archive index")

                archive_path.unlink()
                typer.echo(f"✓ Removed local archive: {archive_name}")

                run_result.archive_created = True
                run_result.archive_size_mb = archive_size_mb
            else:
                typer.echo("✗ Failed to upload to S3", err=True)

            typer.echo("")
            typer.echo("=== Archive Complete ===")
        else:
            typer.echo("=== Skipping Archive (S3 not configured) ===")
            typer.echo("")

        run_result.success = True

    except Exception as exc:
        run_result.success = False
        run_result.error = str(exc)
        logger.error(f"Pipeline run failed: {exc}", exc_info=True)
        typer.echo(f"\n✗ Pipeline failed: {exc}", err=True)

    finally:
        run_result.finished_at = datetime.now()

        # ---------------------------------------------------------- persist run record
        try:
            pipeline_run_record = PipelineRun(
                run_id=run_result.run_id,
                started_at=run_result.started_at,
                finished_at=run_result.finished_at,
                duration_seconds=run_result.duration_seconds,
                success=run_result.success,
                error=run_result.error,
                scrapers_run=run_result.scrapers_run,
                scrapers_succeeded=run_result.scrapers_succeeded,
                scrapers_failed=run_result.scrapers_failed,
                total_scraped_polls=run_result.total_scraped_polls,
                etl_processed=run_result.etl_processed,
                etl_created=run_result.etl_created,
                etl_updated=run_result.etl_updated,
                etl_skipped=run_result.etl_skipped,
                etl_errors=run_result.etl_errors,
                export_polls=run_result.export_polls,
                export_poll_results=run_result.export_poll_results,
                export_raw_polls=run_result.export_raw_polls,
                archive_created=run_result.archive_created,
                archive_size_mb=run_result.archive_size_mb,
            )
            db.add(pipeline_run_record)
            db.commit()
            logger.info(f"Pipeline run record saved: run_id={run_result.run_id}")
        except Exception as db_exc:
            logger.warning(f"Failed to persist pipeline run record: {db_exc}")

        # ---------------------------------------------------------- notify
        notifier.notify(run_result)

        # ---------------------------------------------------------- summary
        status_icon = "✓" if run_result.success else "✗"
        typer.echo(f"=== Pipeline {'Complete' if run_result.success else 'FAILED'} ===")
        typer.echo("")
        typer.echo(f"  {status_icon} Run ID  : {run_result.run_id}")
        typer.echo(f"    Duration: {run_result.duration_human}")
        typer.echo(f"    Scraped : {run_result.total_scraped_polls} new polls")
        typer.echo(
            f"    Created : {run_result.etl_created} | Updated: {run_result.etl_updated}"
            f" | Errors: {run_result.etl_errors}"
        )
        if notifier.notifier_count > 0:
            typer.echo(f"    Notified: {notifier.notifier_count} backend(s)")
        typer.echo("")

        if not run_result.success:
            raise typer.Exit(1)


@app.command(name="pipeline:inspect")
def pipeline_inspect(
    raw_id: int = typer.Argument(..., help="Raw poll ID to inspect"),
):
    """Inspect how a single raw row would be cleaned."""
    db = get_db()
    from pollingapi.models import RawPoll

    raw_poll = db.query(RawPoll).filter(RawPoll.id == raw_id).first()
    if not raw_poll:
        typer.echo(f"✗ Raw poll {raw_id} not found", err=True)
        raise typer.Exit(1)

    typer.echo(f"Inspecting raw poll {raw_id}:")
    typer.echo(f"  publish_date: {raw_poll.publish_date}")
    typer.echo(f"  institute_id: {raw_poll.institute_id}")
    typer.echo(f"  provider: {raw_poll.provider}")
    typer.echo(f"  scope: {raw_poll.scope}")
    typer.echo(f"  parties: {raw_poll.parties}")


# ============================================================================
# Server Commands (server:*)
# ============================================================================


@app.command(name="server:start")
def server_start(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
):
    """Start the API server (development mode)."""
    import uvicorn

    logger.info(f"Starting API server on {host}:{port}")
    typer.echo(f"Starting server on {host}:{port}...")
    uvicorn.run(
        "pollingapi.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command(name="server:prod")
def server_prod(
    host: str = typer.Option(
        "127.0.0.1", "--host", "-h", help="Host to bind to (use 127.0.0.1 for nginx reverse proxy)"
    ),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    workers: int | None = typer.Option(
        None, "--workers", "-w", help="Number of Gunicorn workers (default: 2 * CPU cores + 1)"
    ),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Worker timeout in seconds"),
    keepalive: int = typer.Option(5, "--keepalive", help="Keep-alive timeout in seconds"),
    max_requests: int = typer.Option(
        10000,
        "--max-requests",
        help="Max requests per worker before restart (prevents memory leaks)",
    ),
    access_log: str | None = typer.Option(
        None, "--access-log", help="Access log file path (default: stdout)"
    ),
    error_log: str | None = typer.Option(
        None, "--error-log", help="Error log file path (default: stderr)"
    ),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run as daemon (background process)"),
    pid_file: str | None = typer.Option(None, "--pid", help="PID file path for daemon mode"),
):
    """Start the production API server with Gunicorn.

    This is the recommended way to run in production with nginx as reverse proxy.
    Bind to 127.0.0.1 and let nginx handle external traffic.

    Examples:
        # Basic production server (binds to localhost:8000, 5 workers)
        pollingapi server:prod

        # Custom workers and port
        pollingapi server:prod -h 127.0.0.1 -p 8080 -w 4

        # With log files
        pollingapi server:prod --access-log /var/log/pollingapi/access.log \\
                              --error-log /var/log/pollingapi/error.log

        # As daemon with PID file
        pollingapi server:prod --daemon --pid /var/run/pollingapi.pid
    """
    import multiprocessing
    import subprocess
    import sys

    # Calculate default workers if not specified
    if workers is None:
        workers = (multiprocessing.cpu_count() * 2) + 1

    # Ensure logs directory exists if log files specified
    for log_path in [access_log, error_log]:
        if log_path:
            log_dir = Path(log_path).parent
            log_dir.mkdir(parents=True, exist_ok=True)

    # Build Gunicorn command
    cmd = [
        sys.executable,
        "-m",
        "gunicorn",
        "-k",
        "uvicorn.workers.UvicornWorker",
        "pollingapi.main:app",
        "--bind",
        f"{host}:{port}",
        "--workers",
        str(workers),
        "--timeout",
        str(timeout),
        "--keep-alive",
        str(keepalive),
        "--max-requests",
        str(max_requests),
        "--max-requests-jitter",
        str(max_requests // 20),  # 5% jitter
        "--worker-class",
        "uvicorn.workers.UvicornWorker",
        "--worker-tmp-dir",
        "/dev/shm",  # Use RAM for temp files (faster)
        "--preload",  # Preload app for memory efficiency
    ]

    # Add logging options
    if access_log:
        cmd.extend(["--access-logfile", access_log])
    else:
        cmd.append("--access-logfile")  # Send to stdout
        cmd.append("-")

    if error_log:
        cmd.extend(["--error-logfile", error_log])
    else:
        cmd.append("--error-logfile")  # Send to stderr
        cmd.append("-")

    # Add daemon options
    if daemon:
        cmd.append("--daemon")
        if pid_file:
            cmd.extend(["--pid", pid_file])

    # Log configuration
    logger.info(
        f"Starting production server: host={host}, port={port}, workers={workers}, "
        f"timeout={timeout}s, max_requests={max_requests}"
    )

    typer.echo("Starting production server with Gunicorn...")
    typer.echo(f"  Bind: {host}:{port}")
    typer.echo(f"  Workers: {workers}")
    typer.echo(f"  Timeout: {timeout}s")
    typer.echo(f"  Max requests/worker: {max_requests}")

    if host == "0.0.0.0":
        typer.echo("")
        typer.echo("⚠️  Warning: Binding to 0.0.0.0 exposes the server directly to the internet.")
        typer.echo("   Consider using 127.0.0.1 with nginx as reverse proxy for production.")
    elif host == "127.0.0.1":
        typer.echo("")
        typer.echo("✓ Binding to localhost (127.0.0.1)")
        typer.echo("  Ensure nginx is configured as reverse proxy:")
        typer.echo("")
        typer.echo(r"  location / {")
        typer.echo(r"      proxy_pass http://127.0.0.1:8000;")
        typer.echo(r"      proxy_set_header Host $host;")
        typer.echo(r"      proxy_set_header X-Real-IP $remote_addr;")
        typer.echo(r"  }")

    if daemon:
        typer.echo("")
        typer.echo("Running as daemon")
        if pid_file:
            typer.echo(f"PID file: {pid_file}")

    typer.echo("")

    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            logger.error(f"Gunicorn exited with code {result.returncode}")
            raise typer.Exit(result.returncode)
    except KeyboardInterrupt:
        typer.echo("\nShutting down server...")
        logger.info("Server shutdown requested via keyboard interrupt")
        raise typer.Exit(0) from None
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        typer.echo(f"✗ Error starting server: {e}", err=True)
        raise typer.Exit(1) from e


# ============================================================================
# Log Commands (logs:*)
# ============================================================================


@app.command(name="logs:view")
def logs_view(
    log_file: str = typer.Option(
        "zweitstimme", "--file", "-f", help="Log file to view (zweitstimme, scraper, errors)"
    ),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-F", help="Follow log output (like tail -f)"),
):
    """View log files."""
    log_dir = settings.data_dir / "logs"

    if log_file == "zweitstimme":
        log_path = log_dir / "zweitstimme.log"
    elif log_file == "scraper":
        log_path = log_dir / "scraper.log"
    elif log_file == "errors":
        log_path = log_dir / "errors.log"
    else:
        log_path = log_dir / log_file

    if not log_path.exists():
        typer.echo(f"✗ Log file not found: {log_path}", err=True)
        raise typer.Exit(1)

    if follow:
        typer.echo(f"Following {log_path} (Ctrl+C to exit)...")
        import time

        with open(log_path) as f:
            # Go to end of file
            f.seek(0, 2)
            try:
                while True:
                    line = f.readline()
                    if line:
                        typer.echo(line.rstrip())
                    else:
                        time.sleep(0.1)
            except KeyboardInterrupt:
                typer.echo("\nStopped following logs.")
    else:
        # Read last N lines
        with open(log_path) as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            typer.echo(f"Last {len(last_lines)} lines from {log_path}:")
            typer.echo("-" * 60)
            for line in last_lines:
                typer.echo(line.rstrip())


@app.command(name="logs:list")
def logs_list():
    """List available log files."""
    log_dir = settings.data_dir / "logs"

    if not log_dir.exists():
        typer.echo("No logs directory found.")
        return

    typer.echo("Available log files:")
    typer.echo("-" * 50)

    log_files = ["zweitstimme.log", "scraper.log", "errors.log"]
    for log_file in log_files:
        log_path = log_dir / log_file
        if log_path.exists():
            size = log_path.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size > 1024 else f"{size} B"
            typer.echo(f"  ✓ {log_file}: {size_str}")
        else:
            typer.echo(f"  ○ {log_file}: not created yet")


# ============================================================================
# Data Archive Commands (data:*)
# ============================================================================


@app.command(name="data:archive")
def data_archive(
    keep: bool = typer.Option(False, "--keep", help="Keep local archive after upload"),
):
    """Create and upload data archive to S3."""
    import shutil
    from datetime import datetime

    s3_service = S3Service()

    if not s3_service.is_configured():
        typer.echo("✗ S3 not configured. Check AWS environment variables.", err=True)
        typer.echo("\nRequired environment variables:")
        typer.echo("  AWS_ACCESS_KEY_ID")
        typer.echo("  AWS_SECRET_ACCESS_KEY")
        typer.echo("  AWS_S3_BUCKET_NAME")
        typer.echo("  AWS_S3_REGION")
        typer.echo("  AWS_S3_ENDPOINT_URL (for S3-compatible services)")
        raise typer.Exit(1)

    typer.echo("Running data export...")

    db = get_db()
    export_service = ExportService(db)
    export_counts = export_service.export_all()
    typer.echo(
        f"✓ Exported {export_counts['polls']} polls, {export_counts['results']} poll results, "
        f"and {export_counts['raw']} raw polls"
    )

    typer.echo("\nCreating data archive...")

    data_dir = settings.data_dir
    json_dir = PROJECT_ROOT / "json"

    if not data_dir.exists():
        typer.echo(f"✗ Data directory not found: {data_dir}", err=True)
        raise typer.Exit(1)

    if not json_dir.exists():
        typer.echo(f"✗ JSON directory not found: {json_dir}", err=True)
        raise typer.Exit(1)

    archive_name = f"pollingapi-archive-{datetime.now().strftime('%Y-%m-%d-%H-%M')}.zip"
    archive_path = settings.data_dir.parent / archive_name

    try:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            import shutil as sh

            sh.copytree(data_dir, tmp_path / "data")
            sh.copytree(json_dir, tmp_path / "json")

            shutil.make_archive(
                base_name=str(archive_path.with_suffix("")),
                format="zip",
                root_dir=str(tmp_path),
            )

        archive_size = archive_path.stat().st_size
        typer.echo(f"✓ Created archive: {archive_name} ({archive_size / 1024 / 1024:.1f} MB)")

        typer.echo(f"Uploading to S3 bucket: {s3_service.bucket_name}...")

        key = f"archives/{archive_name}"
        if s3_service.upload_archive(archive_path, key):
            typer.echo(f"✓ Uploaded to s3://{s3_service.bucket_name}/{key}")

            archives = s3_service.list_archives()
            s3_service.upload_index(archives)
            typer.echo("✓ Updated archive index")

            if not keep:
                archive_path.unlink()
                typer.echo(f"✓ Removed local archive: {archive_name}")
            else:
                typer.echo(f"✓ Kept local archive: {archive_path}")

            typer.echo("\nArchive available at:")
            typer.echo("  /v1/archive")
            typer.echo("  /v1/archive.json")
        else:
            typer.echo("✗ Failed to upload to S3", err=True)
            raise typer.Exit(1)

    except Exception as e:
        logger.error(f"Failed to create archive: {e}")
        typer.echo(f"✗ Error: {e}", err=True)
        if archive_path.exists():
            archive_path.unlink()
        raise typer.Exit(1) from e


@app.command(name="data:list")
def data_list():
    """List available data archives in S3."""
    s3_service = S3Service()

    if not s3_service.is_configured():
        typer.echo("✗ S3 not configured.", err=True)
        raise typer.Exit(1)

    archives = s3_service.list_archives()

    if not archives:
        typer.echo("No archives found in S3 bucket.")
        return

    typer.echo(f"Available archives in {s3_service.bucket_name}:")
    typer.echo("-" * 60)
    for archive in archives:
        size_mb = archive.size / 1024 / 1024
        date_str = archive.created_at.strftime("%Y-%m-%d %H:%M")
        typer.echo(f"  {archive.filename}")
        typer.echo(f"    Size: {size_mb:.1f} MB | Date: {date_str}")
        typer.echo(f"    URL: {archive.public_url}")


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
