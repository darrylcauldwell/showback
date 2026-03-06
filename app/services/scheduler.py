import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    """Start the background scheduler for cost calculations."""
    from app.services.cost_calculator import calculate_all_costs

    scheduler.add_job(
        calculate_all_costs,
        "interval",
        minutes=settings.calculation_interval_minutes,
        id="cost_calculation",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started (interval: %d minutes)", settings.calculation_interval_minutes)

    # Run once on startup after a short delay
    asyncio.get_event_loop().call_later(5, lambda: asyncio.ensure_future(calculate_all_costs()))


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
