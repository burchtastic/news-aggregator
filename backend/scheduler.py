"""APScheduler setup for periodic fetch and nightly email digest."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _fetch_job():
    from .fetcher import run_fetch_all
    try:
        result = run_fetch_all()
        logger.info("Scheduled fetch complete: %s", result)
    except Exception as exc:
        logger.error("Scheduled fetch failed: %s", exc)


def _email_job():
    from .email_digest import send_digest
    try:
        send_digest()
    except Exception as exc:
        logger.error("Scheduled email failed: %s", exc)


def start_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone="America/New_York")

    # Fetch articles every hour
    _scheduler.add_job(
        _fetch_job,
        trigger="interval",
        hours=1,
        id="hourly_fetch",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Send email digest at 6:00 PM Eastern every day
    _scheduler.add_job(
        _email_job,
        trigger=CronTrigger(hour=18, minute=0, timezone="America/New_York"),
        id="daily_digest",
        replace_existing=True,
        misfire_grace_time=600,
    )

    _scheduler.start()
    logger.info("Scheduler started (fetch=hourly, digest=18:00 ET)")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
