from __future__ import annotations

import math
import unittest

from exmaterial import __version__
from exmaterial import thermal_tools, xrd_tools


class ThermalToolsTests(unittest.TestCase):
    def test_calculates_thermal_conductivity(self) -> None:
        self.assertEqual(thermal_tools.calculate_thermal_conductivity("1.5", "0.8", "2"), "2.4")

    def test_ignores_incomplete_thermal_rows_and_sorts_points(self) -> None:
        rows = [
            {"temperature_c": "25", "density": "1", "heat_capacity": "2", "thermal_diffusivity": "3"},
            {"temperature_c": "-75", "thermal_conductivity": "4"},
            {"temperature_c": "invalid", "thermal_conductivity": "99"},
        ]
        self.assertEqual(thermal_tools.thermal_points(rows), [(-75.0, 4.0), (25.0, 6.0)])


class XrdToolsTests(unittest.TestCase):
    def test_theta_and_d_round_trip(self) -> None:
        two_theta = 26.5
        d_value = xrd_tools.theta_to_d(two_theta, 1.5406)
        self.assertAlmostEqual(xrd_tools.d_to_theta(d_value, 1.5406), two_theta, places=10)

    def test_parse_xrd_text_accepts_common_delimiters(self) -> None:
        rows, skipped = xrd_tools.parse_xrd_text("header\n10,100\n20;200\n30 300", "1.5406")
        self.assertEqual(skipped, 1)
        self.assertEqual([row[0] for row in rows], [10.0, 20.0, 30.0])
        self.assertEqual([row[1] for row in rows], [100.0, 200.0, 300.0])

    def test_processed_rows_are_normalized_and_finite(self) -> None:
        rows, _ = xrd_tools.parse_xrd_text("10 5\n20 15\n30 10\n40 20", "1.5406")
        processed = xrd_tools.process_xrd_rows(rows)
        intensities = [row[1] for row in processed]
        self.assertEqual(max(intensities), 100.0)
        self.assertGreaterEqual(min(intensities), 0.0)
        self.assertTrue(all(math.isfinite(value) for value in intensities))

    def test_processed_d_preserves_peak_intensities_from_d_input(self) -> None:
        theta_rows, _ = xrd_tools.parse_xrd_text(
            "10 100\n20 50\n30 12\n40 18\n50 8\n60 3\n70 1\n80 3\n90 1\n100 1",
            "1.5406",
        )
        d_rows, _ = xrd_tools.parse_xrd_axis_text(
            xrd_tools.rows_to_d_text(theta_rows),
            "1.5406",
            "d",
        )
        processed_theta = xrd_tools.process_xrd_rows(theta_rows, "theta")
        processed_d = xrd_tools.process_xrd_rows(d_rows, "d")
        self.assertEqual(len(processed_theta), len(processed_d))
        for theta_row, d_row in zip(sorted(processed_theta), sorted(processed_d)):
            self.assertAlmostEqual(theta_row[0], d_row[0], places=6)
            self.assertAlmostEqual(theta_row[1], d_row[1], places=6)


class VersionTests(unittest.TestCase):
    def test_public_release_version(self) -> None:
        self.assertEqual(__version__, "1.0.1")


if __name__ == "__main__":
    unittest.main()
