"""Cron service — runs scheduled jobs and injects prompts into the message bus."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from queryclaw.bus.events import InboundMessage
from queryclaw.config.schema import CronConfig, CronJobConfig
from queryclaw.scheduler.parser import parse_schedule

if TYPE_CHECKING:
    from queryclaw.bus.queue import MessageBus

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except ImportError as e:
    raise ImportError(
        "apscheduler is required for cron. Install with: pip install queryclaw[scheduler]"
    ) from e


class CronService:
    """Runs cron jobs and publishes prompts to the message bus for the agent to process."""

    def __init__(self, bus: MessageBus, config: CronConfig) -> None:
        self._bus = bus
        self._config = config
        self._scheduler = AsyncIOScheduler()
        self._running = False
        self._job_locks: dict[str, asyncio.Lock] = {}

    async def _fire_job(self, job: CronJobConfig) -> None:
        """Called when a cron job fires. Publishes InboundMessage to bus."""
        lock = self._job_locks.get(job.id)
        if lock is None:
            lock = asyncio.Lock()
            self._job_locks[job.id] = lock

        async with lock:
            try:
                logger.info("Cron job fired: {} ({})", job.id, job.schedule)
                msg = InboundMessage(
                    channel="cron",
                    sender_id="cron",
                    chat_id=job.id,
                    content=job.prompt,
                    session_key_override=f"cron:{job.id}",
                    metadata={"job_id": job.id, "schedule": job.schedule},
                )
                await self._bus.publish_inbound(msg)
            except Exception as e:
                logger.exception("Cron job {} failed: {}", job.id, e)

    async def start(self) -> None:
        """Start the cron scheduler and register all enabled jobs."""
        if not self._config.enabled or not self._config.jobs:
            return

        self._running = True
        for job in self._config.jobs:
            if not job.enabled or not job.id or not job.schedule or not job.prompt:
                continue
            try:
                trigger = parse_schedule(job.schedule)
                self._scheduler.add_job(
                    self._fire_job,
                    trigger,
                    args=[job],
                    id=job.id,
                    replace_existing=True,
                )
                logger.info("Cron job registered: {} ({})", job.id, job.schedule)
            except ValueError as e:
                logger.warning("Invalid cron job {}: {}", job.id, e)

        if self._scheduler.get_jobs():
            self._scheduler.start()
            logger.info("Cron service started with {} jobs", len(self._scheduler.get_jobs()))

    def stop(self) -> None:
        """Stop the cron scheduler."""
        self._running = False
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Cron service stopped")
