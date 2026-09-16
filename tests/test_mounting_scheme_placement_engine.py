import unittest

from services.mounting_scheme_placement_engine import (
    calculate_mounting_scheme_placement,
)


class MountingSchemePlacementEngineTests(unittest.TestCase):
    def test_equal_distributes_groups_between_offsets(self):
        result = calculate_mounting_scheme_placement(
            1000,
            {
                "distribution_mode": "equal",
                "min_group_count": 4,
                "fixed_group_count": 4,
                "start_offset_mm": 50,
                "end_offset_mm": 50,
            },
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["positions"], [50.0, 350.0, 650.0, 950.0])
        self.assertEqual(result["actual_spacing_mm"], 300.0)

    def test_equal_increases_count_to_respect_max_spacing(self):
        result = calculate_mounting_scheme_placement(
            1000,
            {
                "distribution_mode": "equal",
                "min_group_count": 2,
                "start_offset_mm": 50,
                "end_offset_mm": 50,
                "max_spacing_mm": 300,
            },
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["group_count"], 4)
        self.assertEqual(result["positions"], [50.0, 350.0, 650.0, 950.0])

    def test_equal_rejects_max_count_that_breaks_spacing_limit(self):
        result = calculate_mounting_scheme_placement(
            1000,
            {
                "distribution_mode": "equal",
                "min_group_count": 2,
                "max_group_count": 3,
                "start_offset_mm": 50,
                "end_offset_mm": 50,
                "max_spacing_mm": 300,
            },
        )

        self.assertFalse(result["valid"])
        self.assertEqual(result["positions"], [])

    def test_fixed_spacing_places_from_start_offset(self):
        result = calculate_mounting_scheme_placement(
            1000,
            {
                "distribution_mode": "fixed_spacing",
                "min_group_count": 1,
                "start_offset_mm": 50,
                "end_offset_mm": 50,
                "fixed_spacing_mm": 300,
            },
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["positions"], [50.0, 350.0, 650.0, 950.0])
        self.assertEqual(result["actual_spacing_mm"], 300.0)

    def test_fixed_spacing_rejects_fixed_count_that_does_not_fit(self):
        result = calculate_mounting_scheme_placement(
            500,
            {
                "distribution_mode": "fixed_spacing",
                "min_group_count": 3,
                "fixed_group_count": 3,
                "start_offset_mm": 50,
                "end_offset_mm": 50,
                "fixed_spacing_mm": 250,
            },
        )

        self.assertFalse(result["valid"])

    def test_centered_single_group_is_exactly_centered(self):
        result = calculate_mounting_scheme_placement(
            1000,
            {
                "distribution_mode": "centered",
                "min_group_count": 1,
                "fixed_group_count": 1,
                "start_offset_mm": 50,
                "end_offset_mm": 50,
            },
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["positions"], [500.0])

    def test_centered_three_groups_are_symmetric(self):
        result = calculate_mounting_scheme_placement(
            1000,
            {
                "distribution_mode": "centered",
                "min_group_count": 3,
                "fixed_group_count": 3,
                "start_offset_mm": 50,
                "end_offset_mm": 50,
                "fixed_spacing_mm": 200,
            },
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["positions"], [300.0, 500.0, 700.0])

    def test_centered_two_groups_are_symmetric(self):
        result = calculate_mounting_scheme_placement(
            1000,
            {
                "distribution_mode": "centered",
                "min_group_count": 2,
                "fixed_group_count": 2,
                "start_offset_mm": 100,
                "end_offset_mm": 100,
                "fixed_spacing_mm": 300,
            },
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["positions"], [350.0, 650.0])

    def test_offsets_cannot_exceed_joint_length(self):
        result = calculate_mounting_scheme_placement(
            100,
            {
                "distribution_mode": "equal",
                "min_group_count": 2,
                "start_offset_mm": 60,
                "end_offset_mm": 60,
            },
        )

        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
