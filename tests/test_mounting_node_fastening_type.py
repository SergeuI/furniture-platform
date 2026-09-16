import sqlite3
import unittest
from database.mounting_node_fastening_type_schema import apply_schema

from pydantic import ValidationError
from schemas.mounting_nodes import MountingNodeCreateSchema, MountingNodeUpdateSchema, MountingNodeDetailSchema


class FasteningTypeTests(unittest.TestCase):
    def test_schema_upgrade_preserves_rows_and_is_idempotent(self):
        with sqlite3.connect(":memory:") as connection:
            connection.execute("CREATE TABLE mounting_nodes (id INTEGER PRIMARY KEY, name TEXT)")
            connection.execute("INSERT INTO mounting_nodes VALUES (1, 'Confirmat old')")
            connection.commit()
            self.assertTrue(apply_schema(connection))
            self.assertFalse(apply_schema(connection))
            self.assertEqual(connection.execute("SELECT * FROM mounting_nodes").fetchall(), [(1, "Confirmat old", None)])
            self.assertEqual(connection.execute("PRAGMA table_info(mounting_nodes)").fetchall()[-1][3], 0)

    def test_schema_vocabulary_and_null(self):
        for value in (None, "confirmat", "minifix", "rafix", "screw", "dowel", "other"):
            self.assertEqual(MountingNodeCreateSchema(name="Test", fastening_type=value).fastening_type, value)
            self.assertEqual(MountingNodeUpdateSchema(fastening_type=value).fastening_type, value)
        for schema in (MountingNodeCreateSchema, MountingNodeUpdateSchema):
            for value in ("invalid", "", "hinge", 1):
                with self.assertRaises(ValidationError):
                    schema(name="Test", fastening_type=value)
        self.assertIsNone(MountingNodeDetailSchema(id=1, code="old", name="Old").fastening_type)
