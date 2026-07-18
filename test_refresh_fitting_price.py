from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.fitting import FittingModel
from database import repositories as repositories_package
from database.repositories import inventory_repository
from scripts import refresh_fitting_price


class RefreshFittingPriceTests(unittest.TestCase):
    def test_dry_run_preserves_row(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "refresh.db"
            session_factory = self._create_temp_session(database_path)
            self._seed_fitting(
                session_factory,
                article="07733",
                source_url="https://kronas.com.ua/test-product",
                price=0.85,
                stock="Під замовлення",
                currency="UAH",
                source_payload_json=json.dumps({"parsed_item": {"characteristics": {"H": "0"}}}, ensure_ascii=False),
                source="kronas",
            )

            with (
                patch.object(refresh_fitting_price, "DEFAULT_DB_PATH", str(database_path)),
                patch.object(inventory_repository, "SessionLocal", session_factory),
                patch.object(
                    refresh_fitting_price,
                    "parse_fitting_source_metadata",
                    self._fake_parser(
                        success=True,
                        source_site="kronas",
                        final_url="https://kronas.com.ua/test-product",
                        price=1.15,
                        availability="В наявності",
                        currency="UAH",
                    ),
                ),
                redirect_stdout(StringIO()) as stdout,
            ):
                exit_code = refresh_fitting_price.main(["--article", "07733"])

            self.assertEqual(exit_code, 0)
            output = stdout.getvalue()
            self.assertIn("WOULD UPDATE", output)
            self.assertIn("SUMMARY:", output)

            with session_factory() as session:
                row = session.get(FittingModel, 1)
                self.assertIsNotNone(row)
                assert row is not None
                self.assertEqual(row.price, 0.85)
                self.assertEqual(row.stock, "Під замовлення")
                self.assertEqual(row.currency, "UAH")
                self.assertIsNone(row.parsed_at)
                self.assertIsNone(row.price_updated_at)
                self.assertEqual(
                    row.source_payload_json,
                    json.dumps({"parsed_item": {"characteristics": {"H": "0"}}}, ensure_ascii=False),
                )

    def test_apply_updates_only_dynamic_fields(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "refresh.db"
            session_factory = self._create_temp_session(database_path)
            source_payload_json = json.dumps(
                {
                    "source_site": "viyar",
                    "parsed_item": {"characteristics": {"Матеріал": "сталь"}},
                },
                ensure_ascii=False,
            )
            self._seed_fitting(
                session_factory,
                article="118442",
                source_url="https://viyar.ua/test-product",
                price=29.97,
                stock="В наявності",
                currency="UAH",
                source_payload_json=source_payload_json,
                source="viyar",
            )

            with (
                patch.object(refresh_fitting_price, "DEFAULT_DB_PATH", str(database_path)),
                patch.object(inventory_repository, "SessionLocal", session_factory),
                patch.object(
                    refresh_fitting_price,
                    "parse_fitting_source_metadata",
                    self._fake_parser(
                        success=True,
                        source_site="viyar",
                        final_url="https://viyar.ua/test-product",
                        price=31.25,
                        availability="Немає в наявності",
                        currency="UAH",
                    ),
                ),
                redirect_stdout(StringIO()) as stdout,
            ):
                exit_code = refresh_fitting_price.main(["--article", "118442", "--apply"])

            self.assertEqual(exit_code, 0)
            output = stdout.getvalue()
            self.assertIn("UPDATED", output)
            self.assertIn("SUMMARY:", output)

            with session_factory() as session:
                row = session.get(FittingModel, 1)
                self.assertIsNotNone(row)
                assert row is not None
                self.assertEqual(row.price, 31.25)
                self.assertEqual(row.stock, "Немає в наявності")
                self.assertEqual(row.currency, "UAH")
                self.assertIsNotNone(row.parsed_at)
                self.assertIsNotNone(row.price_updated_at)
                self.assertEqual(row.name, "GIFF hinge")
                self.assertEqual(row.description, "Static description")
                self.assertEqual(row.brand, "GIFF")
                self.assertEqual(row.source, "viyar")
                self.assertEqual(row.source_url, "https://viyar.ua/test-product")
                self.assertEqual(row.source_payload_json, source_payload_json)

    def test_mt_source_is_skipped_without_parser_call(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "refresh.db"
            session_factory = self._create_temp_session(database_path)
            self._seed_fitting(
                session_factory,
                article="90001",
                source_url="https://mt.ua/product/90001",
                price=100.0,
                stock="В наявності",
                currency="UAH",
                source_payload_json="{}",
                source="mt",
            )

            parser_mock = self._fake_parser(
                success=True,
                source_site="mt",
                final_url="https://mt.ua/product/90001",
                price=120.0,
                availability="В наявності",
                currency="UAH",
            )

            with (
                patch.object(refresh_fitting_price, "DEFAULT_DB_PATH", str(database_path)),
                patch.object(inventory_repository, "SessionLocal", session_factory),
                patch.object(refresh_fitting_price, "parse_fitting_source_metadata", parser_mock),
                redirect_stdout(StringIO()) as stdout,
            ):
                exit_code = refresh_fitting_price.main(["--article", "90001"])

            self.assertEqual(exit_code, 0)
            self.assertEqual(parser_mock.call_count, 0)
            self.assertIn("SKIPPED", stdout.getvalue())

            with session_factory() as session:
                row = session.get(FittingModel, 1)
                self.assertIsNotNone(row)
                assert row is not None
                self.assertEqual(row.price, 100.0)
                self.assertEqual(row.stock, "В наявності")
                self.assertEqual(row.currency, "UAH")

    def test_parser_failure_does_not_clear_existing_values(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "refresh.db"
            session_factory = self._create_temp_session(database_path)
            self._seed_fitting(
                session_factory,
                article="07733",
                source_url="https://kronas.com.ua/test-product",
                price=0.85,
                stock="Під замовлення",
                currency="UAH",
                source_payload_json='{"source_site":"kronas"}',
                source="kronas",
            )

            with (
                patch.object(refresh_fitting_price, "DEFAULT_DB_PATH", str(database_path)),
                patch.object(inventory_repository, "SessionLocal", session_factory),
                patch.object(
                    refresh_fitting_price,
                    "parse_fitting_source_metadata",
                    self._fake_parser(
                        success=False,
                        source_site="kronas",
                        error="timeout",
                    ),
                ),
                redirect_stdout(StringIO()) as stdout,
            ):
                exit_code = refresh_fitting_price.main(["--article", "07733", "--apply"])

            self.assertEqual(exit_code, 1)
            self.assertIn("FAILED", stdout.getvalue())

            with session_factory() as session:
                row = session.get(FittingModel, 1)
                self.assertIsNotNone(row)
                assert row is not None
                self.assertEqual(row.price, 0.85)
                self.assertEqual(row.stock, "Під замовлення")
                self.assertEqual(row.currency, "UAH")
                self.assertIsNone(row.parsed_at)
                self.assertIsNone(row.price_updated_at)
                self.assertEqual(row.source_payload_json, '{"source_site":"kronas"}')

    def test_batch_lock_blocks_second_acquire(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "refresh.db"
            database_path.write_text("", encoding="utf-8")
            with refresh_fitting_price._batch_process_lock(
                database_path,
                mode="DRY-RUN",
                batch_kind="limit",
            ):
                with self.assertRaises(SystemExit) as exc_info:
                    with refresh_fitting_price._batch_process_lock(
                        database_path,
                        mode="DRY-RUN",
                        batch_kind="limit",
                    ):
                        pass
            self.assertEqual(exc_info.exception.code, 3)

    @staticmethod
    def _create_temp_session(database_path: Path):
        engine = create_engine(f"sqlite:///{database_path.as_posix()}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine, tables=[FittingModel.__table__])
        return sessionmaker(bind=engine, autocommit=False, autoflush=False)

    @staticmethod
    def _seed_fitting(
        session_factory,
        *,
        article: str,
        source_url: str,
        price: float,
        stock: str,
        currency: str,
        source_payload_json: str,
        source: str,
    ) -> None:
        with session_factory() as session:
            session.add(
                FittingModel(
                    city="Київ",
                    code="07733",
                    article=article,
                    name="GIFF hinge",
                    description="Static description",
                    price=price,
                    stock=stock,
                    fitting_type="hinges",
                    fitting_group="fittings",
                    image_url="https://example.com/image.jpg",
                    source_url=source_url,
                    source=source,
                    brand="GIFF",
                    unit="шт",
                    currency=currency,
                    parsed_at=None,
                    price_updated_at=None,
                    source_payload_json=source_payload_json,
                    owner_user_id=None,
                    is_system=True,
                    is_active=True,
                    sort_order=0,
                )
            )
            session.commit()

    @staticmethod
    def _fake_parser(**payload):
        parser_mock = AsyncMock(return_value=payload)
        return parser_mock


if __name__ == "__main__":
    unittest.main()
