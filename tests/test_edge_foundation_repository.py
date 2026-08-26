from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import Boolean, Column, Integer, String, Table, create_engine, text
from sqlalchemy.orm import sessionmaker

from database.base import Base
from database.models.canonical_edge import (  # noqa: F401
    CanonicalEdgeModel,
    EdgeSupplierOfferModel,
    EdgeSupplierOfferPriceModel,
    MaterialEdgeRelationModel,
)
from database.repositories.edge_foundation_repository import EdgeFoundationRepository
from scripts import upgrade_edge_foundation_schema as migration


class EdgeFoundationRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database_path = Path(self._tmpdir.name) / "edges.db"
        self._created_stub_tables = []
        self._ensure_stub_table(
            "materials",
            Column("id", Integer, primary_key=True),
        )
        self._ensure_stub_table(
            "material_manufacturers",
            Column("id", Integer, primary_key=True),
        )
        self._ensure_stub_table(
            "suppliers",
            Column("id", Integer, primary_key=True),
            Column("code", String),
            Column("name", String),
            Column("is_system", Boolean),
            Column("is_active", Boolean),
        )
        self.engine = create_engine(
            f"sqlite:///{self.database_path}",
            connect_args={"check_same_thread": False},
        )
        self.session_maker = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def tearDown(self) -> None:
        for table in self._created_stub_tables:
            Base.metadata.remove(table)
        self.engine.dispose()
        self._tmpdir.cleanup()

    def _ensure_stub_table(self, table_name: str, *columns: Column) -> None:
        if table_name in Base.metadata.tables:
            return
        table = Table(table_name, Base.metadata, *columns)
        self._created_stub_tables.append(table)

    def test_repository_supports_canonical_edges_relations_offers_and_city_prices(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.executescript(
                """
                CREATE TABLE materials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article TEXT NOT NULL UNIQUE,
                    name TEXT
                );
                CREATE TABLE material_manufacturers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL
                );
                CREATE TABLE suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    is_system BOOLEAN NOT NULL DEFAULT 1,
                    is_active BOOLEAN NOT NULL DEFAULT 1
                );
                INSERT INTO material_manufacturers (name, normalized_name) VALUES ('Kronospan', 'kronospan');
                INSERT INTO materials (article, name) VALUES ('M-1', 'Material 1');
                INSERT INTO materials (article, name) VALUES ('M-2', 'Material 2');
                INSERT INTO suppliers (code, name, is_system, is_active) VALUES ('viyar', 'VIYAR', 1, 1);
                INSERT INTO suppliers (code, name, is_system, is_active) VALUES ('kronas', 'KRONAS', 1, 1);
                """
            )
            migration.ensure_edge_foundation_schema(connection)

        db = self.session_maker()
        try:
            manufacturer_id = db.execute(
                text("SELECT id FROM material_manufacturers WHERE normalized_name = 'kronospan'")
            ).fetchone()[0]
            material_one_id = db.execute(
                text("SELECT id FROM materials WHERE article = 'M-1'")
            ).fetchone()[0]
            material_two_id = db.execute(
                text("SELECT id FROM materials WHERE article = 'M-2'")
            ).fetchone()[0]
            supplier_viyar_id = db.execute(
                text("SELECT id FROM suppliers WHERE code = 'viyar'")
            ).fetchone()[0]
            supplier_kronas_id = db.execute(
                text("SELECT id FROM suppliers WHERE code = 'kronas'")
            ).fetchone()[0]

            repository = EdgeFoundationRepository(session=db)

            edge = repository.create_edge(
                manufacturer_id=manufacturer_id,
                manufacturer_article="E-001",
                name="Edge A",
                decor_code="DC-1",
                color="Oak",
                material_type="ABS",
                width_mm=22.0,
                thickness_mm=1.0,
                finish="matte",
                image_url="https://example.com/edge.png",
                is_active=True,
            )
            self.assertIsNotNone(edge)
            self.assertIsNone(edge.supplier_offers[0] if edge.supplier_offers else None)

            relation_one = repository.create_relation(
                material_id=material_one_id,
                edge_id=edge.id,
                relation_type="recommended",
                source_supplier_id=supplier_viyar_id,
                source_url="https://viyar.ua/product",
            )
            relation_two = repository.create_relation(
                material_id=material_two_id,
                edge_id=edge.id,
                relation_type="compatible",
                source_supplier_id=supplier_kronas_id,
                source_url="https://kronas.ua/product",
            )
            self.assertIsNotNone(relation_one)
            self.assertIsNotNone(relation_two)
            null_supplier_relation = repository.create_relation(
                material_id=material_one_id,
                edge_id=edge.id,
                relation_type="manual",
                source_supplier_id=None,
                source_url="https://viyar.ua/manual-a",
            )
            self.assertIsNotNone(null_supplier_relation)
            self.assertEqual(
                db.execute(text("SELECT COUNT(*) FROM material_edge_relations")).fetchone()[0],
                3,
            )

            duplicate_relation = repository.create_relation(
                material_id=material_one_id,
                edge_id=edge.id,
                relation_type="recommended",
                source_supplier_id=supplier_viyar_id,
                source_url="https://viyar.ua/product-b",
            )
            self.assertIsNone(duplicate_relation)

            duplicate_null_supplier = repository.create_relation(
                material_id=material_one_id,
                edge_id=edge.id,
                relation_type="manual",
                source_supplier_id=None,
                source_url="https://viyar.ua/manual-b",
            )
            self.assertIsNone(duplicate_null_supplier)

            relation_rows = db.execute(
                text(
                    """
                    SELECT relation_type, source_supplier_id, source_url
                    FROM material_edge_relations
                    ORDER BY id
                    """
                )
            ).fetchall()
            self.assertEqual(
                [tuple(row) for row in relation_rows],
                [
                    ("recommended", supplier_viyar_id, "https://viyar.ua/product"),
                    ("compatible", supplier_kronas_id, "https://kronas.ua/product"),
                    ("manual", None, "https://viyar.ua/manual-a"),
                ],
            )

            offer_viyar = repository.upsert_offer(
                edge_id=edge.id,
                supplier_id=supplier_viyar_id,
                article="E-001-V",
                source_url="https://viyar.ua/offer",
                external_product_id=None,
                unit="м",
                stock="in stock",
                is_active=True,
                priority=10,
            )
            offer_kronas = repository.upsert_offer(
                edge_id=edge.id,
                supplier_id=supplier_kronas_id,
                article="E-001-K",
                source_url="https://kronas.ua/offer",
                external_product_id=None,
                unit="м",
                stock="in stock",
                is_active=True,
                priority=20,
            )
            self.assertIsNotNone(offer_viyar)
            self.assertIsNotNone(offer_kronas)

            duplicate_offer = repository.create_offer(
                edge_id=edge.id,
                supplier_id=supplier_viyar_id,
                article="E-001-V-2",
                source_url="https://viyar.ua/offer-2",
                external_product_id=None,
                unit="м",
                stock="in stock",
                is_active=True,
                priority=15,
            )
            self.assertIsNone(duplicate_offer)

            price_kyiv = repository.upsert_offer_price(
                offer_id=offer_viyar.id,
                city="Kyiv",
                price=12.5,
                currency="UAH",
                availability="in stock",
            )
            price_lviv = repository.upsert_offer_price(
                offer_id=offer_viyar.id,
                city="Lviv",
                price=13.0,
                currency="UAH",
                availability="in stock",
            )
            self.assertEqual(price_kyiv.city, "Kyiv")
            self.assertEqual(price_lviv.city, "Lviv")

            updated_kyiv = repository.upsert_offer_price(
                offer_id=offer_viyar.id,
                city="Kyiv",
                price=12.75,
                currency="UAH",
                availability="limited",
            )
            self.assertEqual(updated_kyiv.price, 12.75)
            self.assertEqual(updated_kyiv.availability, "limited")

            prices = repository.list_offer_prices(offer_viyar.id)
            self.assertEqual([row.city for row in prices], ["Kyiv", "Lviv"])
            self.assertEqual([row.price for row in prices], [12.75, 13.0])

            edge_relations = repository.list_relations_by_material(material_one_id)
            self.assertEqual(len(edge_relations), 2)
            self.assertEqual({row.relation_type for row in edge_relations}, {"recommended", "manual"})

            materials_for_edge = repository.list_materials_by_edge(edge.id)
            self.assertEqual({row.material_id for row in materials_for_edge}, {material_one_id, material_two_id})

            offers_for_edge = repository.list_offers_by_edge(edge.id)
            self.assertEqual({row.supplier_id for row in offers_for_edge}, {supplier_viyar_id, supplier_kronas_id})
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
