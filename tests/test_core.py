from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

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

    def test_shape_preserving_interpolation_does_not_invent_peak_heights(self) -> None:
        source = [(0.0, 98.0), (1.0, 100.0), (2.0, 99.0), (3.0, 20.0)]
        curve = xrd_tools.cubic_spline_interpolate(source, 200)

        self.assertEqual(max(intensity for _x, intensity in curve), 100.0)
        for x_value, intensity in source:
            self.assertIn((x_value, intensity), curve)

    def test_processed_d_curve_breaks_at_missing_acquisition_interval(self) -> None:
        rows = [
            (10.00, 10.0, 8.0),
            (10.02, 20.0, 7.9),
            (10.04, 98.00848, 7.8),
            (10.40, 100.0, 7.0),
            (10.42, 15.0, 6.9),
        ]
        curve = xrd_tools.processed_curve_points(rows, "d", 600)
        breaks = [
            index
            for index, (x_value, y_value) in enumerate(curve)
            if not math.isfinite(x_value) or not math.isfinite(y_value)
        ]

        self.assertEqual(len(breaks), 1)
        finite_curve = [(x_value, y_value) for x_value, y_value in curve if math.isfinite(x_value)]
        self.assertEqual(max(y_value for _x_value, y_value in finite_curve), 100.0)
        self.assertEqual(sum(y_value == 100.0 for _x_value, y_value in finite_curve), 1)
        self.assertFalse(any(7.0 < x_value < 7.8 for x_value, y_value in curve if math.isfinite(x_value)))

        class RecordingCanvas:
            def __init__(self) -> None:
                self.blue_lines = 0

            def delete(self, *_args) -> None:
                pass

            def winfo_width(self) -> int:
                return 700

            def winfo_height(self) -> int:
                return 400

            def create_text(self, *_args, **_kwargs) -> None:
                pass

            def create_line(self, *_args, **kwargs) -> None:
                if kwargs.get("fill") == "#1f77b4":
                    self.blue_lines += 1

            def create_oval(self, *_args, **_kwargs) -> None:
                pass

        canvas = RecordingCanvas()
        config = xrd_tools.processed_plot_config(curve, "d", 600, (9.0, 1.0))
        from exmaterial.plot_viewer import IMAGE_MARGIN, draw_scatter_plot, save_scatter_jpg

        draw_scatter_plot(canvas, **config)
        self.assertEqual(canvas.blue_lines, 2)

        with tempfile.TemporaryDirectory() as temp_dir:
            jpg_path = Path(temp_dir) / "processed_xrd_d.jpg"
            save_scatter_jpg(
                jpg_path,
                curve,
                "XRD 处理后: d",
                "d (Å)",
                "强度",
                (9.0, 1.0),
                1,
                y_limits=(0, 100),
                connect_points=True,
                point_radius=0,
            )
            from PIL import Image

            with Image.open(jpg_path) as image:
                image = image.convert("RGB")
                gap_midpoint = (7.0 + 7.8) / 2
                x_min, x_max = 9.0, 1.0
                margin_left, margin_right, margin_top, margin_bottom = IMAGE_MARGIN
                pixel_x = round(
                    margin_left
                    + (gap_midpoint - x_min) / (x_max - x_min) * (image.width - margin_left - margin_right)
                )
                gap_column = [image.getpixel((pixel_x, y)) for y in range(margin_top, image.height - margin_bottom)]
                self.assertFalse(any(blue > red * 1.25 and red < 180 for red, _green, blue in gap_column))


class VersionTests(unittest.TestCase):
    def test_public_release_version(self) -> None:
        self.assertEqual(__version__, "1.0.2")


if __name__ == "__main__":
    unittest.main()
