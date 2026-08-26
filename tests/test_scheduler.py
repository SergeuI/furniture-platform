from __future__ import annotations

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import main
import main_api
from services import scheduler


class FakeCronTrigger:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeScheduler:
    instances: list["FakeScheduler"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.timezone = kwargs.get("timezone")
        self.add_job_calls: list[dict] = []
        self.start_calls = 0
        self.running = False
        FakeScheduler.instances.append(self)

    def add_job(self, func, **kwargs):
        self.add_job_calls.append(
            {
                "func": func,
                "kwargs": kwargs,
            }
        )

    def start(self):
        self.start_calls += 1
        self.running = True


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        FakeScheduler.instances.clear()
        scheduler._scheduler = None

    def tearDown(self) -> None:
        scheduler._scheduler = None

    def test_start_scheduler_registers_default_cron_jobs(self) -> None:
        with (
            patch.object(scheduler, "AsyncIOScheduler", FakeScheduler),
            patch.object(scheduler, "CronTrigger", FakeCronTrigger),
            patch.dict(
                os.environ,
                {
                    "PARSER_TIMEZONE": "Europe/Kyiv",
                    "VIYAR_PARSER_ENABLED": "1",
                    "VIYAR_PARSER_DAYS": "tue,fri",
                    "VIYAR_PARSER_HOUR": "3",
                    "VIYAR_PARSER_MINUTE": "10",
                    "MT_PARSER_ENABLED": "1",
                    "MT_PARSER_DAYS": "wed",
                    "MT_PARSER_HOUR": "3",
                    "MT_PARSER_MINUTE": "40",
                    "VIYAR_SERVICE_SYNC_ENABLED": "1",
                    "VIYAR_SERVICE_SYNC_DAYS": "mon-sun",
                    "VIYAR_SERVICE_SYNC_HOUR": "4",
                    "VIYAR_SERVICE_SYNC_MINUTE": "10",
                },
                clear=False,
            ),
        ):
            started = scheduler.start_scheduler()

        self.assertIs(started, FakeScheduler.instances[0])
        self.assertEqual(started.start_calls, 1)
        self.assertEqual(started.timezone.key, "Europe/Kyiv")
        self.assertEqual(len(started.add_job_calls), 3)

        jobs = {call["kwargs"]["id"]: call for call in started.add_job_calls}
        self.assertSetEqual(
            set(jobs),
            {"viyar-parser", "mt-parser", "viyar-service-sync"},
        )

        self.assertIs(jobs["viyar-parser"]["func"], scheduler.run_viyar_parser_job)
        self.assertIs(jobs["mt-parser"]["func"], scheduler.run_mt_parser_job)
        self.assertIs(jobs["viyar-service-sync"]["func"], scheduler.run_viyar_service_sync_job)

        for job in jobs.values():
            self.assertTrue(job["kwargs"]["replace_existing"])
            self.assertEqual(job["kwargs"]["max_instances"], 1)
            self.assertTrue(job["kwargs"]["coalesce"])
            self.assertEqual(job["kwargs"]["misfire_grace_time"], scheduler.DEFAULT_MISFIRE_GRACE_SECONDS)

        self.assertEqual(jobs["viyar-parser"]["kwargs"]["trigger"].kwargs["day_of_week"], "tue,fri")
        self.assertEqual(jobs["viyar-parser"]["kwargs"]["trigger"].kwargs["hour"], 3)
        self.assertEqual(jobs["viyar-parser"]["kwargs"]["trigger"].kwargs["minute"], 10)

        self.assertEqual(jobs["mt-parser"]["kwargs"]["trigger"].kwargs["day_of_week"], "wed")
        self.assertEqual(jobs["mt-parser"]["kwargs"]["trigger"].kwargs["hour"], 3)
        self.assertEqual(jobs["mt-parser"]["kwargs"]["trigger"].kwargs["minute"], 40)

        self.assertEqual(jobs["viyar-service-sync"]["kwargs"]["trigger"].kwargs["day_of_week"], "mon-sun")
        self.assertEqual(jobs["viyar-service-sync"]["kwargs"]["trigger"].kwargs["hour"], 4)
        self.assertEqual(jobs["viyar-service-sync"]["kwargs"]["trigger"].kwargs["minute"], 10)

    def test_start_scheduler_is_idempotent(self) -> None:
        with (
            patch.object(scheduler, "AsyncIOScheduler", FakeScheduler),
            patch.object(scheduler, "CronTrigger", FakeCronTrigger),
            patch.dict(
                os.environ,
                {
                    "PARSER_TIMEZONE": "Europe/Kyiv",
                    "VIYAR_PARSER_ENABLED": "1",
                    "VIYAR_PARSER_DAYS": "tue,fri",
                    "VIYAR_PARSER_HOUR": "3",
                    "VIYAR_PARSER_MINUTE": "10",
                    "MT_PARSER_ENABLED": "1",
                    "MT_PARSER_DAYS": "wed",
                    "MT_PARSER_HOUR": "3",
                    "MT_PARSER_MINUTE": "40",
                    "VIYAR_SERVICE_SYNC_ENABLED": "1",
                    "VIYAR_SERVICE_SYNC_DAYS": "mon-sun",
                    "VIYAR_SERVICE_SYNC_HOUR": "4",
                    "VIYAR_SERVICE_SYNC_MINUTE": "10",
                },
                clear=False,
            ),
        ):
            first = scheduler.start_scheduler()
            second = scheduler.start_scheduler()

        self.assertIs(first, second)
        self.assertEqual(len(FakeScheduler.instances), 1)
        self.assertEqual(first.start_calls, 1)
        self.assertEqual(len(first.add_job_calls), 3)

    def test_env_overrides_disable_jobs_and_change_timezone(self) -> None:
        with (
            patch.object(scheduler, "AsyncIOScheduler", FakeScheduler),
            patch.object(scheduler, "CronTrigger", FakeCronTrigger),
            patch.dict(
                os.environ,
                {
                    "PARSER_TIMEZONE": "UTC",
                    "VIYAR_PARSER_ENABLED": "0",
                    "MT_PARSER_ENABLED": "1",
                    "MT_PARSER_DAYS": "thu",
                    "MT_PARSER_HOUR": "5",
                    "MT_PARSER_MINUTE": "17",
                    "VIYAR_SERVICE_SYNC_ENABLED": "0",
                },
                clear=False,
            ),
        ):
            started = scheduler.start_scheduler()

        self.assertEqual(started.timezone.key, "UTC")
        self.assertEqual(len(started.add_job_calls), 1)

        job = started.add_job_calls[0]
        self.assertIs(job["func"], scheduler.run_mt_parser_job)
        self.assertEqual(job["kwargs"]["id"], "mt-parser")
        self.assertEqual(job["kwargs"]["trigger"].kwargs["day_of_week"], "thu")
        self.assertEqual(job["kwargs"]["trigger"].kwargs["hour"], 5)
        self.assertEqual(job["kwargs"]["trigger"].kwargs["minute"], 17)

    def test_normal_startup_does_not_export_demo_material_seed(self) -> None:
        self.assertFalse(hasattr(main, "seed_materials"))

    async def test_real_scheduler_populates_next_run_time(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "PARSER_TIMEZONE": "Europe/Kyiv",
                    "VIYAR_PARSER_ENABLED": "1",
                    "VIYAR_PARSER_DAYS": "tue,fri",
                    "VIYAR_PARSER_HOUR": "3",
                    "VIYAR_PARSER_MINUTE": "10",
                    "MT_PARSER_ENABLED": "1",
                    "MT_PARSER_DAYS": "wed",
                    "MT_PARSER_HOUR": "3",
                    "MT_PARSER_MINUTE": "40",
                    "VIYAR_SERVICE_SYNC_ENABLED": "1",
                    "VIYAR_SERVICE_SYNC_DAYS": "mon-sun",
                    "VIYAR_SERVICE_SYNC_HOUR": "4",
                    "VIYAR_SERVICE_SYNC_MINUTE": "10",
                },
                clear=False,
            ),
            patch.object(scheduler, "run_viyar_parser_job", new=AsyncMock(return_value=None)),
            patch.object(scheduler, "run_mt_parser_job", new=AsyncMock(return_value=None)),
            patch.object(scheduler, "run_viyar_service_sync_job", new=AsyncMock(return_value=None)),
        ):
            started = scheduler.start_scheduler()

            try:
                self.assertTrue(started.running)
                jobs = started.get_jobs()
                self.assertEqual(len(jobs), 3)
                for job in jobs:
                    self.assertIsNotNone(job.next_run_time)
                    self.assertFalse(job.next_run_time is None)
                    self.assertEqual(job.trigger.timezone.key, "Europe/Kyiv")
                    self.assertIn(job.id, {"viyar-parser", "mt-parser", "viyar-service-sync"})
            finally:
                started.shutdown(wait=False)
                scheduler._scheduler = None

    async def test_mt_parser_job_serializes_bootstrap_and_scheduled_runs(self) -> None:
        started = []
        release = asyncio.Event()
        first_entered = asyncio.Event()

        async def fake_mt_parser():
            started.append(asyncio.current_task().get_name())
            first_entered.set()
            await release.wait()
            return (2, 1)

        with patch.object(scheduler, "run_mt_parser", side_effect=fake_mt_parser):
            task_one = asyncio.create_task(
                scheduler.run_mt_parser_job(source="startup"),
                name="mt-bootstrap",
            )
            await first_entered.wait()

            task_two = asyncio.create_task(
                scheduler.run_mt_parser_job(source="scheduler"),
                name="mt-scheduled",
            )

            await asyncio.sleep(0.05)
            self.assertEqual(len(started), 1)

            release.set()
            result_one, result_two = await asyncio.gather(task_one, task_two)

        self.assertEqual(result_one, (2, 1))
        self.assertEqual(result_two, (2, 1))
        self.assertEqual(len(started), 2)

    async def test_bootstrap_skip_when_disabled(self) -> None:
        with patch.object(main, "run_mt_parser_job", new=AsyncMock()) as mock_job:
            await main.maybe_run_mt_parser_on_start(False)

        mock_job.assert_not_awaited()

    async def test_main_api_startup_only_controls_material_queue_loop(self) -> None:
        startup_mock = MagicMock(return_value="started")
        shutdown_mock = MagicMock(return_value="stopped")
        with (
            patch.object(main_api, "start_material_import_queue_loop", new=startup_mock),
            patch.object(main_api, "stop_material_import_queue_loop", new=shutdown_mock),
        ):
            await main_api.startup_background_services()
            await main_api.shutdown_background_services()

        startup_mock.assert_called_once_with()
        shutdown_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
