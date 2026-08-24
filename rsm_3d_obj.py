from __future__ import annotations

import numpy as np

from rsm_core import FitResult, predict_grid


VIRIDIS_RGB = [
    (68, 1, 84),
    (72, 40, 120),
    (62, 73, 137),
    (49, 104, 142),
    (38, 130, 142),
    (31, 158, 137),
    (53, 183, 121),
    (110, 206, 88),
    (181, 222, 43),
    (253, 231, 37),
]


def _append_obj_box(
    lines: list[str],
    vertex_index: int,
    bounds: tuple[float, float, float, float, float, float],
    material: str,
) -> int:
    x0, x1, y0, y1, z0, z1 = bounds
    vertices = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    for x_value, y_value, z_value in vertices:
        lines.append(f"v {x_value:.8f} {y_value:.8f} {z_value:.8f}")

    a, b, c, d, e, f, g, h = range(vertex_index, vertex_index + 8)
    lines.append(f"usemtl {material}")
    lines.extend(
        [
            f"f {a} {d} {c} {b}",
            f"f {e} {f} {g} {h}",
            f"f {a} {b} {f} {e}",
            f"f {b} {c} {g} {f}",
            f"f {c} {d} {h} {g}",
            f"f {d} {a} {e} {h}",
        ]
    )
    return vertex_index + 8


def _append_obj_legend_text(
    lines: list[str],
    text: str,
    x_left: float,
    y_center: float,
    height: float,
    z_center: float,
    vertex_index: int,
) -> int:
    segment_map = {
        "0": "abcdef",
        "1": "bc",
        "2": "abdeg",
        "3": "abcdg",
        "4": "bcfg",
        "5": "acdfg",
        "6": "acdefg",
        "7": "abc",
        "8": "abcdefg",
        "9": "abcdfg",
        "e": "adefg",
        "E": "adefg",
        "-": "g",
    }
    segment_boxes = {
        "a": (0.14, 0.86, 1.84, 2.00),
        "b": (0.84, 1.00, 1.02, 1.90),
        "c": (0.84, 1.00, 0.10, 0.98),
        "d": (0.14, 0.86, 0.00, 0.16),
        "e": (0.00, 0.16, 0.10, 0.98),
        "f": (0.00, 0.16, 1.02, 1.90),
        "g": (0.14, 0.86, 0.92, 1.08),
    }
    pixel_glyphs = {
        "X": ("10001", "01010", "00100", "00100", "01010", "10001", "10001"),
        "Y": ("10001", "01010", "00100", "00100", "00100", "00100", "00100"),
    }
    char_height = height
    char_width = height * 0.5
    spacing = height * 0.12
    cursor = x_left
    y_bottom = y_center - height / 2.0
    depth = max(height * 0.035, 0.0015)

    for char in text:
        if char in pixel_glyphs:
            cell_width = char_width / 5.0
            cell_height = char_height / 7.0
            inset = min(cell_width, cell_height) * 0.12
            for row_index, row_pattern in enumerate(pixel_glyphs[char]):
                for col_index, is_filled in enumerate(row_pattern):
                    if is_filled != "1":
                        continue
                    x0 = cursor + col_index * cell_width + inset
                    x1 = cursor + (col_index + 1) * cell_width - inset
                    y0 = y_bottom + (6 - row_index) * cell_height + inset
                    y1 = y_bottom + (7 - row_index) * cell_height - inset
                    vertex_index = _append_obj_box(
                        lines,
                        vertex_index,
                        (x0, x1, y0, y1, z_center - depth, z_center + depth),
                        "Legend_Text",
                    )
            cursor += char_width + spacing
            continue
        if char == ".":
            dot_size = height * 0.10
            vertex_index = _append_obj_box(
                lines,
                vertex_index,
                (cursor, cursor + dot_size, y_bottom, y_bottom + dot_size, z_center - depth, z_center + depth),
                "Legend_Text",
            )
            cursor += dot_size + spacing
            continue
        if char == "+":
            center_x = cursor + char_width / 2.0
            center_y = y_bottom + char_height / 2.0
            thickness = height * 0.06
            vertex_index = _append_obj_box(
                lines,
                vertex_index,
                (
                    cursor + char_width * 0.15,
                    cursor + char_width * 0.85,
                    center_y - thickness,
                    center_y + thickness,
                    z_center - depth,
                    z_center + depth,
                ),
                "Legend_Text",
            )
            vertex_index = _append_obj_box(
                lines,
                vertex_index,
                (
                    center_x - thickness,
                    center_x + thickness,
                    y_bottom + char_height * 0.32,
                    y_bottom + char_height * 0.68,
                    z_center - depth,
                    z_center + depth,
                ),
                "Legend_Text",
            )
            cursor += char_width + spacing
            continue

        for segment in segment_map.get(char, ""):
            sx0, sx1, sy0, sy1 = segment_boxes[segment]
            vertex_index = _append_obj_box(
                lines,
                vertex_index,
                (
                    cursor + sx0 * char_width,
                    cursor + sx1 * char_width,
                    y_bottom + sy0 * char_height / 2.0,
                    y_bottom + sy1 * char_height / 2.0,
                    z_center - depth,
                    z_center + depth,
                ),
                "Legend_Text",
            )
        cursor += char_width + spacing
    return vertex_index


def _format_legend_value(value: float) -> str:
    if not np.isfinite(value):
        return "0"
    absolute = abs(value)
    if absolute >= 100_000 or (0 < absolute < 0.001):
        return f"{value:.2e}"
    return f"{value:.4g}"


def make_surface_obj_files(
    result: FitResult,
    axis_x: str,
    axis_y: str,
    fixed_values: dict[str, float],
    grid_size: int,
) -> tuple[bytes, bytes]:
    xx, yy, zz = predict_grid(result, axis_x, axis_y, fixed_values, grid_size)
    x_center = float((np.nanmin(xx) + np.nanmax(xx)) / 2.0)
    y_center = float((np.nanmin(yy) + np.nanmax(yy)) / 2.0)
    z_center = float((np.nanmin(zz) + np.nanmax(zz)) / 2.0)
    x_scale = max(float(np.nanmax(xx) - np.nanmin(xx)), 1e-12)
    y_scale = max(float(np.nanmax(yy) - np.nanmin(yy)), 1e-12)
    z_scale = max(float(np.nanmax(zz) - np.nanmin(zz)), 1e-12)

    lines = [
        "# RSM predicted response surface",
        "# Includes a 3D color legend with min/mid/max response labels",
        f"# X axis: {axis_x}",
        f"# Y axis: {axis_y}",
        f"# Z axis: {result.y_label}",
        "mtllib rsm_surface.mtl",
    ]
    if fixed_values:
        for factor, value in fixed_values.items():
            lines.append(f"# Fixed {factor}: {value}")
    lines.append("o RSM_Surface")
    lines.append("s 1")

    rows, cols = xx.shape
    for row in range(rows):
        for col in range(cols):
            x_value = 1.4 * (float(xx[row, col]) - x_center) / x_scale
            y_value = 1.2 * (float(yy[row, col]) - y_center) / y_scale
            z_value = 0.8 * (float(zz[row, col]) - z_center) / z_scale
            lines.append(f"v {x_value:.8f} {z_value:.8f} {y_value:.8f}")

    z_min = float(np.nanmin(zz))
    z_max = float(np.nanmax(zz))
    z_span = z_max - z_min
    lines.extend(
        [
            f"# Legend min: {_format_legend_value(z_min)}",
            f"# Legend mid: {_format_legend_value((z_min + z_max) / 2.0)}",
            f"# Legend max: {_format_legend_value(z_max)}",
        ]
    )
    last_material = ""
    for row in range(rows - 1):
        for col in range(cols - 1):
            v1 = row * cols + col + 1
            v2 = v1 + 1
            v3 = (row + 1) * cols + col + 2
            v4 = (row + 1) * cols + col + 1
            face_value = float(np.mean([zz[row, col], zz[row, col + 1], zz[row + 1, col + 1], zz[row + 1, col]]))
            normalized = 0.5 if z_span <= 0 else (face_value - z_min) / z_span
            color_index = min(int(np.clip(normalized, 0.0, 1.0) * len(VIRIDIS_RGB)), len(VIRIDIS_RGB) - 1)
            material = f"Viridis_{color_index:02d}"
            if material != last_material:
                lines.append(f"usemtl {material}")
                last_material = material
            lines.append(f"f {v1} {v2} {v3} {v4}")

    normalized_x_max = 0.70
    legend_left = normalized_x_max + 0.12
    legend_right = legend_left + 0.075
    legend_bottom = -0.40
    legend_top = 0.40
    legend_depth = 0.018
    vertex_index = rows * cols + 1

    lines.append("s off")
    lines.append("o RSM_Legend_Frame")
    vertex_index = _append_obj_box(
        lines,
        vertex_index,
        (
            legend_left - 0.008,
            legend_right + 0.008,
            legend_bottom - 0.008,
            legend_top + 0.008,
            -legend_depth,
            legend_depth,
        ),
        "Legend_Frame",
    )

    lines.append("o RSM_Legend_ColorBar")
    bin_height = (legend_top - legend_bottom) / len(VIRIDIS_RGB)
    for color_index in range(len(VIRIDIS_RGB)):
        y0 = legend_bottom + color_index * bin_height
        y1 = legend_bottom + (color_index + 1) * bin_height
        vertex_index = _append_obj_box(
            lines,
            vertex_index,
            (legend_left, legend_right, y0, y1, -legend_depth * 1.35, legend_depth * 1.35),
            f"Viridis_{color_index:02d}",
        )

    tick_x0 = legend_right + 0.006
    tick_x1 = legend_right + 0.030
    label_x = legend_right + 0.040
    text_height = 0.055
    lines.append("o RSM_Legend_Ticks_And_Labels")
    legend_values = [z_min, (z_min + z_max) / 2.0, z_max]
    legend_positions = [legend_bottom, (legend_bottom + legend_top) / 2.0, legend_top]
    for value, position in zip(legend_values, legend_positions):
        vertex_index = _append_obj_box(
            lines,
            vertex_index,
            (
                tick_x0,
                tick_x1,
                position - 0.004,
                position + 0.004,
                -legend_depth * 1.5,
                legend_depth * 1.5,
            ),
            "Legend_Text",
        )
        vertex_index = _append_obj_legend_text(
            lines,
            _format_legend_value(value),
            label_x,
            position,
            text_height,
            0.0,
            vertex_index,
        )

    axis_x_code = f"X{result.factors.index(axis_x) + 1}"
    axis_y_code = f"X{result.factors.index(axis_y) + 1}"
    response_code = result.y_name.upper() if result.y_name.upper().startswith("Y") else "Y1"
    lines.append("o RSM_Axis_Labels")
    vertex_index = _append_obj_legend_text(
        lines, axis_x_code, -0.07, -0.50, 0.10, 0.0, vertex_index
    )
    vertex_index = _append_obj_legend_text(
        lines, axis_y_code, -0.86, 0.00, 0.10, 0.0, vertex_index
    )
    vertex_index = _append_obj_legend_text(
        lines, response_code, legend_left - 0.005, 0.49, 0.10, 0.0, vertex_index
    )

    material_lines = ["# RSM Viridis materials"]
    for index, (red, green, blue) in enumerate(VIRIDIS_RGB):
        material_lines.extend(
            [
                f"newmtl Viridis_{index:02d}",
                f"Ka {red / 255.0:.6f} {green / 255.0:.6f} {blue / 255.0:.6f}",
                f"Kd {red / 255.0:.6f} {green / 255.0:.6f} {blue / 255.0:.6f}",
                "Ks 0.120000 0.120000 0.120000",
                "Ns 24.000000",
                "illum 2",
                "",
            ]
        )
    material_lines.extend(
        [
            "newmtl Legend_Frame",
            "Ka 0.050000 0.050000 0.050000",
            "Kd 0.120000 0.120000 0.120000",
            "Ks 0.100000 0.100000 0.100000",
            "Ns 12.000000",
            "illum 2",
            "",
            "newmtl Legend_Text",
            "Ka 0.020000 0.020000 0.020000",
            "Kd 0.030000 0.030000 0.030000",
            "Ks 0.000000 0.000000 0.000000",
            "Ns 1.000000",
            "illum 1",
            "",
        ]
    )

    obj_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    mtl_bytes = ("\n".join(material_lines) + "\n").encode("utf-8")
    return obj_bytes, mtl_bytes



