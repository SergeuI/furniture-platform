from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts import upgrade_edge_foundation_schema as migration


class UpgradeEdgeFoundationSchemaTests(unittest.TestCase):
    def test_ensure_edge_foundation_schema_creates_tables_and_leaves_legacy_edge_tables_intact(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "edges.db"
            with sqlite3.connect(database_path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE materials (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        article TEXT NOT NULL UNIQUE
                    );
                    CREATE TABLE material_manufacturers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        normalized_name TEXT NOT NULL
                    );
                    CREATE TABLE suppliers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        code TEXT NOT NULL UNIQUE,
                        name TEXT NOT NULL
                    );
                    CREATE TABLE material_edge_options (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        material_article TEXT,
                        edge_key TEXT
                    );
                    CREATE TABLE material_edge_prices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        edge_option_id INTEGER,
                        city TEXT,
                        price REAL
                    );
                    INSERT INTO materials (article) VALUES ('M-1');
                    INSERT INTO material_manufacturers (name, normalized_name) VALUES ('Kronospan', 'kronospan');
                    INSERT INTO suppliers (code, name) VALUES ('viyar', 'VIYAR');
                    INSERT INTO material_edge_options (material_article, edge_key) VALUES ('M-1', 'edge_04');
                    INSERT INTO material_edge_prices (edge_option_id, city, price) VALUES (1, 'Kyiv', 12.5);
                    """
                )
                legacy_option_count = connection.execute(
                    "SELECT COUNT(*) FROM material_edge_options"
                ).fetchone()[0]
                legacy_price_count = connection.execute(
                    "SELECT COUNT(*) FROM material_edge_prices"
                ).fetchone()[0]

                migration.ensure_edge_foundation_schema(connection)

                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM material_edge_options"
                    ).fetchone()[0],
                    legacy_option_count,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM material_edge_prices"
                    ).fetchone()[0],
                    legacy_price_count,
                )

                for table_name in (
                    "canonical_edges",
                    "material_edge_relations",
                    "edge_supplier_offers",
                    "edge_supplier_offer_prices",
                ):
                    row = connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table_name,),
                    ).fetchone()
                    self.assertIsNotNone(row, table_name)

                index_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'index' ORDER BY name"
                    ).fetchall()
                }
                self.assertIn("uq_material_edge_relations_identity_null_supplier", index_names)
                self.assertIn("uq_material_edge_relations_identity_supplier", index_names)
                self.assertNotIn("uq_material_edge_relations_identity", index_names)

                null_supplier_index_sql = connection.execute(
                    """
                    SELECT sql
                    FROM sqlite_master
                    WHERE type = 'index' AND name = 'uq_material_edge_relations_identity_null_supplier'
                    """
                ).fetchone()[0]
                supplier_index_sql = connection.execute(
                    """
                    SELECT sql
                    FROM sqlite_master
                    WHERE type = 'index' AND name = 'uq_material_edge_relations_identity_supplier'
                    """
                ).fetchone()[0]
                self.assertIn("WHERE source_supplier_id IS NULL", null_supplier_index_sql)
                self.assertIn("WHERE source_supplier_id IS NOT NULL", supplier_index_sql)

    def test_edge_foundation_relation_identity_is_partial_unique_and_city_prices_are_per_offer(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            database_path = Path(tmpdir) / "edges.db"
            with sqlite3.connect(database_path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE materials (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        article TEXT NOT NULL UNIQUE
                    );
                    CREATE TABLE material_manufacturers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        normalized_name TEXT NOT NULL
                    );
                CREATE TABLE suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL
                );
                """
                )
                migration.ensure_edge_foundation_schema(connection)
                connection.execute("INSERT INTO materials (article) VALUES ('M-1')")
                connection.execute(
                    "INSERT INTO material_manufacturers (name, normalized_name) VALUES ('Kronospan', 'kronospan')"
                )
                connection.execute("INSERT INTO suppliers (code, name) VALUES ('viyar', 'VIYAR')")
                connection.execute("INSERT INTO suppliers (code, name) VALUES ('kronas', 'KRONAS')")
                connection.execute(
                    """
                    INSERT INTO canonical_edges (
                        manufacturer_article,
                        name,
                        decor_code,
                        color,
                        material_type,
                        width_mm,
                        thickness_mm,
                        finish,
                        image_url,
                        is_active
                    ) VALUES ('E-001', 'Edge A', 'DC-1', 'Oak', 'ABS', 22.0, 1.0, 'matte', 'https://example.com/edge.png', 1)
                    """
                )
                connection.execute(
                    """
                    INSERT INTO material_edge_relations (
                        material_id,
                        edge_id,
                        relation_type,
                        source_supplier_id,
                        source_url
                    ) VALUES (1, 1, 'manual', NULL, 'https://viyar.ua/product-a')
                    """
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO material_edge_relations (
                            material_id,
                            edge_id,
                            relation_type,
                            source_supplier_id,
                            source_url
                        ) VALUES (1, 1, 'manual', NULL, 'https://viyar.ua/product-b')
                        """
                    )
                connection.execute(
                    """
                    INSERT INTO material_edge_relations (
                        material_id,
                        edge_id,
                        relation_type,
                        source_supplier_id,
                        source_url
                    ) VALUES (1, 1, 'recommended', 1, 'https://viyar.ua/product-a')
                    """
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO material_edge_relations (
                            material_id,
                            edge_id,
                            relation_type,
                            source_supplier_id,
                            source_url
                        ) VALUES (1, 1, 'recommended', 1, 'https://viyar.ua/product-b')
                        """
                    )

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO material_edge_relations (
                            material_id,
                            edge_id,
                            relation_type,
                            source_supplier_id,
                            source_url
                        ) VALUES (1, 1, 'manual', NULL, 'https://viyar.ua/product-c')
                        """
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO material_edge_relations (
                            material_id,
                            edge_id,
                            relation_type,
                            source_supplier_id,
                            source_url
                        ) VALUES (1, 1, 'recommended', 1, 'https://viyar.ua/product-c')
                        """
                    )

                connection.execute(
                    """
                    INSERT INTO material_edge_relations (
                        material_id,
                        edge_id,
                        relation_type,
                        source_supplier_id,
                        source_url
                    ) VALUES (1, 1, 'recommended', 2, 'https://kronas.ua/product-a')
                    """
                )
                connection.execute(
                    """
                    INSERT INTO material_edge_relations (
                        material_id,
                        edge_id,
                        relation_type,
                        source_supplier_id,
                        source_url
                    ) VALUES (1, 1, 'compatible', 1, 'https://viyar.ua/product-compatible')
                    """
                )
                connection.execute(
                    """
                    INSERT INTO edge_supplier_offers (
                        edge_id,
                        supplier_id,
                        article,
                        source_url,
                        unit,
                        stock,
                        is_active,
                        priority
                    ) VALUES (1, 1, 'E-001-V', 'https://viyar.ua/offer', 'м', 'in stock', 1, 10)
                    """
                )

                relation_rows = connection.execute(
                    """
                    SELECT material_id, edge_id, relation_type, source_supplier_id, source_url
                    FROM material_edge_relations
                    ORDER BY id
                    """
                ).fetchall()
                self.assertEqual(
                    relation_rows,
                    [
                        (1, 1, 'manual', None, 'https://viyar.ua/product-a'),
                        (1, 1, 'recommended', 1, 'https://viyar.ua/product-a'),
                        (1, 1, 'recommended', 2, 'https://kronas.ua/product-a'),
                        (1, 1, 'compatible', 1, 'https://viyar.ua/product-compatible'),
                    ],
                )

                offer_prices_table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'edge_supplier_offer_prices'"
                ).fetchone()
                self.assertIsNotNone(offer_prices_table)

                connection.execute(
                    """
                    INSERT INTO edge_supplier_offer_prices (
                        offer_id,
                        city,
                        price,
                        currency,
                        availability
                    ) VALUES (1, 'Kyiv', 12.5, 'UAH', 'in stock')
                    """
                )
                connection.execute(
                    """
                    INSERT INTO edge_supplier_offer_prices (
                        offer_id,
                        city,
                        price,
                        currency,
                        availability
                    ) VALUES (1, 'Lviv', 13.0, 'UAH', 'in stock')
                    """
                )

                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO edge_supplier_offer_prices (
                            offer_id,
                            city,
                            price,
                            currency,
                            availability
                        ) VALUES (1, 'Kyiv', 14.0, 'UAH', 'in stock')
                        """
                    )


if __name__ == "__main__":
    unittest.main()
