from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from database.deletion_protection import canonical_edge_identity_key, is_auto_recreate_suppressed
from database.edge_lifecycle_schema import ensure_edge_lifecycle_schema
from database.models.canonical_edge import CanonicalEdgeModel
from database.models.hole_library import HoleLibraryTypeModel  # noqa: F401 - register mapper
from database.repositories.edge_foundation_repository import EdgeFoundationRepository
from database.repositories.inventory_repository import delete_material
from scripts import upgrade_edge_foundation_schema as migration
from services.edge_foundation_persistence_service import EdgeFoundationPersistenceService


def _foreign_keys_on(dbapi_connection, _connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=OFF")


class MaterialEdgeLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database_path = Path(self.tmpdir.name) / "lifecycle.db"
        with sqlite3.connect(self.database_path) as connection:
            connection.executescript(
                """
                CREATE TABLE materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, article TEXT NOT NULL UNIQUE, name TEXT,
                    description TEXT, color TEXT, dimensions TEXT, thickness TEXT, manufacturer_id INTEGER,
                    image TEXT, source_url TEXT, source TEXT, product_type TEXT, owner_user_id TEXT,
                    category TEXT, tg_file_id TEXT, is_default BOOLEAN NOT NULL DEFAULT 0,
                    image_cached_bytes BLOB, image_cached_content_type TEXT, image_source_url TEXT,
                    image_cached_hash TEXT, imported_at DATETIME, static_updated_at DATETIME
                );
                CREATE TABLE material_images (id INTEGER PRIMARY KEY AUTOINCREMENT, material_id INTEGER, source_url TEXT, image_cached_bytes BLOB, image_cached_content_type TEXT);
                CREATE TABLE material_prices (id INTEGER PRIMARY KEY AUTOINCREMENT, article TEXT, city TEXT, price REAL, currency TEXT, unit TEXT, availability TEXT);
                CREATE TABLE material_user_links (id INTEGER PRIMARY KEY AUTOINCREMENT, material_article TEXT, user_id TEXT);
                CREATE TABLE material_manufacturers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, normalized_name TEXT NOT NULL UNIQUE, code TEXT, website_url TEXT, logo_url TEXT, owner_user_id TEXT, is_active BOOLEAN NOT NULL DEFAULT 1, is_system BOOLEAN NOT NULL DEFAULT 1, created_at DATETIME, updated_at DATETIME);
                CREATE TABLE suppliers (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL);
                CREATE TABLE audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, actor_user_id TEXT, actor_email TEXT, action TEXT, entity_type TEXT, entity_id TEXT, details TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
                INSERT INTO material_manufacturers (name, normalized_name) VALUES ('Rehau', 'rehau');
                INSERT INTO suppliers (code, name) VALUES ('viyar', 'VIYAR');
                """
            )
            migration.ensure_edge_foundation_schema(connection)
            ensure_edge_lifecycle_schema(connection)

        self.engine = create_engine(f"sqlite:///{self.database_path.as_posix()}")
        event.listen(self.engine, "connect", _foreign_keys_on)
        self.session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _add_material(self, article: str) -> int:
        row = self.session.execute(
            text("INSERT INTO materials (article, name) VALUES (:article, :name) RETURNING id"),
            {"article": article, "name": article},
        ).one()
        self.session.flush()
        return int(row[0])

    def _add_edge(self, policy: str = "delete_when_orphan") -> tuple[int, int, int]:
        manufacturer_id = self.session.execute(text("SELECT id FROM material_manufacturers")).scalar_one()
        supplier_id = self.session.execute(text("SELECT id FROM suppliers")).scalar_one()
        edge = EdgeFoundationRepository(self.session).create_edge(
            manufacturer_id=manufacturer_id,
            manufacturer_article="E-1",
            name="Edge E-1",
            material_type="ABS",
            width_mm=22.0,
            thickness_mm=0.8,
            is_active=True,
            cleanup_policy=policy,
        )
        offer = EdgeFoundationRepository(self.session).create_offer(
            edge_id=edge.id,
            supplier_id=supplier_id,
            article="SUP-1",
            source_url="https://viyar.ua/edge",
            unit="м.п.",
            stock="in stock",
            is_active=True,
        )
        price = EdgeFoundationRepository(self.session).upsert_offer_price(
            offer_id=offer.id,
            city="Kyiv",
            price=10.0,
            currency="UAH",
        )
        self.session.commit()
        return int(edge.id), int(offer.id), int(price.id)

    def _add_relation(self, material_id: int, edge_id: int) -> None:
        self.session.execute(
            text("INSERT INTO material_edge_relations (material_id, edge_id, relation_type) VALUES (:m, :e, 'recommended')"),
            {"m": material_id, "e": edge_id},
        )
        self.session.commit()

    def _delete(self, article: str):
        with patch("database.repositories.inventory_repository.SessionLocal", return_value=self.session):
            return delete_material(article)

    def _counts(self) -> dict[str, int]:
        return {
            table: int(self.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
            for table in ("materials", "material_edge_relations", "canonical_edges", "edge_supplier_offers", "edge_supplier_offer_prices")
        }

    def test_shared_auto_edge_is_preserved(self) -> None:
        material_a = self._add_material("A")
        material_b = self._add_material("B")
        edge_id, _, _ = self._add_edge()
        self._add_relation(material_a, edge_id)
        self._add_relation(material_b, edge_id)

        self._delete("A")

        self.assertEqual(self._counts(), {"materials": 1, "material_edge_relations": 1, "canonical_edges": 1, "edge_supplier_offers": 1, "edge_supplier_offer_prices": 1})

    def test_single_use_auto_edge_and_dependents_are_deleted(self) -> None:
        material_id = self._add_material("A")
        edge_id, _, _ = self._add_edge()
        self._add_relation(material_id, edge_id)

        self._delete("A")

        self.assertEqual(self._counts(), {"materials": 0, "material_edge_relations": 0, "canonical_edges": 0, "edge_supplier_offers": 0, "edge_supplier_offer_prices": 0})
        self.assertEqual(self.session.execute(text("SELECT COUNT(*) FROM audit_logs WHERE action='catalog.edge_deleted'")).scalar_one(), 0)

    def test_protected_edge_is_preserved_after_last_relation_is_removed(self) -> None:
        material_id = self._add_material("A")
        edge_id, _, _ = self._add_edge(policy="protected")
        self._add_relation(material_id, edge_id)

        self._delete("A")

        self.assertEqual(self._counts(), {"materials": 0, "material_edge_relations": 0, "canonical_edges": 1, "edge_supplier_offers": 1, "edge_supplier_offer_prices": 1})

    def test_manager_owned_material_cannot_delete_protected_edge(self) -> None:
        material_id = self._add_material("A")
        self.session.execute(
            text("UPDATE materials SET owner_user_id = 'manager-1' WHERE id = :id"),
            {"id": material_id},
        )
        edge_id, _, _ = self._add_edge(policy="protected")
        self._add_relation(material_id, edge_id)

        self._delete("A")

        self.assertEqual(self._counts()["canonical_edges"], 1)

    def test_manual_edge_suppression_blocks_recreation(self) -> None:
        material_id = self._add_material("A")
        edge_id, _, _ = self._add_edge(policy="protected")
        edge = self.session.get(CanonicalEdgeModel, edge_id)
        identity_key = canonical_edge_identity_key(edge)
        self.session.execute(
            text("INSERT INTO audit_logs (action, entity_type, entity_id) VALUES ('catalog.edge_deleted', 'canonical_edge', :key)"),
            {"key": identity_key},
        )
        self.session.commit()

        self.assertTrue(is_auto_recreate_suppressed(self.session, "canonical_edge", identity_key))
        service = EdgeFoundationPersistenceService(session=self.session)
        result = service.persist_preview_item(
            material_id=material_id,
            preview_item={
                "status": "parsed",
                "canonical_candidate": {"manufacturer": "Rehau", "manufacturer_article": "E-1", "name": "Edge E-1", "material_type": "ABS", "width_mm": 22.0, "thickness_mm": 0.8},
                "supplier_offer_candidate": {"supplier": "viyar", "article": "SUP-1", "source_url": "https://viyar.ua/edge", "unit": "м.п."},
            },
        )
        self.assertEqual(result["reason"], "canonical_edge_deletion_suppressed")

    def test_material_delete_rolls_back_on_commit_failure(self) -> None:
        material_id = self._add_material("A")
        edge_id, _, _ = self._add_edge()
        self._add_relation(material_id, edge_id)
        with patch.object(self.session, "commit", side_effect=RuntimeError("forced_delete_failure")):
            with self.assertRaisesRegex(RuntimeError, "forced_delete_failure"):
                self._delete("A")

        self.session.rollback()
        self.assertEqual(self._counts(), {"materials": 1, "material_edge_relations": 1, "canonical_edges": 1, "edge_supplier_offers": 1, "edge_supplier_offer_prices": 1})


if __name__ == "__main__":
    unittest.main()
