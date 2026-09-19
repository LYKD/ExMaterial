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


class VersionTests(unittest.TestCase):
    def test_public_release_version(self) -> None:
        self.assertEqual(__version__, "1.0.0")


if __name__ == "__main__":
    unittest.main()
