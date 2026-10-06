import unittest

from pydantic import ValidationError

from schemas.catalog import Fitting3DCoordinateUpdateSchema


class Fitting3DMountingCoordinateSchemaTests(unittest.TestCase):
    def test_unconfigured_mounting_frame_is_backward_compatible(self):
        payload = Fitting3DCoordinateUpdateSchema(origin_x=0, origin_y=0, origin_z=0)
        self.assertFalse(payload.mounting_coordinate_system_configured)
        self.assertIsNone(payload.mounting_point_x)

    def test_configured_mounting_frame_requires_complete_point(self):
        with self.assertRaises(ValidationError):
            Fitting3DCoordinateUpdateSchema(
                origin_x=0, origin_y=0, origin_z=0,
                mounting_coordinate_system_configured=True,
                mounting_point_x=1,
            )

    def test_configured_mounting_frame_accepts_complete_point(self):
        payload = Fitting3DCoordinateUpdateSchema(
            origin_x=0, origin_y=0, origin_z=0,
            mounting_coordinate_system_configured=True,
            mounting_point_x=1, mounting_point_y=2, mounting_point_z=3,
        )
        self.assertEqual((payload.mounting_point_x, payload.mounting_point_y, payload.mounting_point_z), (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
