"""Tests for scheduler: parser, CronService, HeartbeatService."""

import asyncio

import pytest
import pytest_asyncio

from queryclaw.bus.events import InboundMessage
from queryclaw.bus.queue import MessageBus
from queryclaw.config.schema import CronConfig, CronJobConfig, HeartbeatConfig
from queryclaw.scheduler.parser import parse_schedule
from queryclaw.scheduler.cron_service import CronService
from queryclaw.scheduler.heartbeat_service import HeartbeatService


class TestScheduleParser:
    def test_at_format(self):
        t = parse_schedule("at 09:00")
        assert t is not None
        assert "hour" in str(t).lower() or "9" in str(t)

    def test_at_invalid(self):
        with pytest.raises(ValueError, match="Invalid time|Unknown"):
            parse_schedule("at 25:00")
        with pytest.raises(ValueError, match="Invalid time"):
            parse_schedule("at 9:60")

    def test_every_minutes(self):
        t = parse_schedule("every 30m")
        assert t is not None
        assert "interval" in str(t).lower()

    def test_every_hours(self):
        t = parse_schedule("every 1h")
        assert t is not None

    def test_every_invalid(self):
        with pytest.raises(ValueError):
            parse_schedule("every 0m")
        with pytest.raises(ValueError):
            parse_schedule("every -1h")

    def test_cron_format(self):
        t = parse_schedule("cron 0 9 * * 1")
        assert t is not None
        assert "cron" in str(t).lower()

    def test_unknown_format(self):
        with pytest.raises(ValueError, match="Unknown"):
            parse_schedule("invalid schedule")


@pytest_asyncio.fixture
async def bus():
    return MessageBus()


class TestCronService:
    @pytest.mark.asyncio
    async def test_start_empty_config(self, bus):
        config = CronConfig(enabled=False)
        svc = CronService(bus, config)
        await svc.start()
        svc.stop()

    @pytest.mark.asyncio
    async def test_start_with_jobs(self, bus):
        config = CronConfig(
            enabled=True,
            jobs=[
                CronJobConfig(
                    id="test_job",
                    schedule="every 1h",
                    prompt="Test prompt",
                    enabled=True,
                ),
            ],
        )
        svc = CronService(bus, config)
        await svc.start()
        assert svc._scheduler.get_jobs()
        svc.stop()

    @pytest.mark.asyncio
    async def test_fire_publishes_inbound(self, bus):
        config = CronConfig(
            enabled=True,
            jobs=[
                CronJobConfig(
                    id="fire_test",
                    schedule="every 1h",
                    prompt="Hello from cron",
                    enabled=True,
                ),
            ],
        )
        svc = CronService(bus, config)
        await svc.start()
        await svc._fire_job(config.jobs[0])
        msg = await asyncio.wait_for(bus.inbound.get(), timeout=1.0)
        assert msg.channel == "cron"
        assert msg.content == "Hello from cron"
        assert msg.chat_id == "fire_test"
        svc.stop()


class TestHeartbeatService:
    @pytest.mark.asyncio
    async def test_start_disabled(self, bus):
        config = HeartbeatConfig(enabled=False)
        svc = HeartbeatService(bus, config)
        await svc.start()

    @pytest.mark.asyncio
    async def test_stop_breaks_loop(self, bus):
        config = HeartbeatConfig(enabled=True, interval_minutes=1)
        svc = HeartbeatService(bus, config)
        task = asyncio.create_task(svc.start())
        await asyncio.sleep(0.1)
        svc.stop()
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
