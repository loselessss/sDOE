from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


SIZE = 1024
SCALE = 4
CANVAS = SIZE * SCALE
ASSET_DIR = Path(__file__).resolve().parent / "assets"


def scaled_points(points: list[tuple[float, float]]) -> list[tuple[int, int]]:
    return [(round(x * SCALE), round(y * SCALE)) for x, y in points]


def surface_y(x: float, depth: float) -> float:
    normalized = (x - 520.0) / 330.0
    return 610.0 - 245.0 * (1.0 - normalized * normalized) + depth


def build_icon() -> Image.Image:
    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (48 * SCALE, 48 * SCALE, 976 * SCALE, 976 * SCALE),
        radius=190 * SCALE,
        fill=(20, 48, 53, 255),
        outline=(222, 242, 238, 100),
        width=10 * SCALE,
    )

    # Coordinate axes remain legible at taskbar-icon sizes.
    axis = (239, 247, 245, 235)
    draw.line(scaled_points([(205, 755), (205, 270)]), fill=axis, width=26 * SCALE)
    draw.line(scaled_points([(190, 755), (840, 755)]), fill=axis, width=26 * SCALE)
    draw.polygon(scaled_points([(205, 235), (174, 294), (236, 294)]), fill=axis)
    draw.polygon(scaled_points([(875, 755), (814, 724), (814, 786)]), fill=axis)

    x_values = [245 + index * 12 for index in range(52)]
    depths = [-105, -52, 0, 52, 105]
    bands = [
        (56, 200, 182, 150),
        (69, 210, 190, 175),
        (83, 220, 198, 205),
        (103, 228, 205, 225),
        (132, 234, 214, 245),
    ]

    for depth, color in zip(depths, bands, strict=True):
        points = [(x, surface_y(x, depth)) for x in x_values]
        draw.line(scaled_points(points), fill=color, width=22 * SCALE, joint="curve")

    # Cross-lines turn the stacked curves into a compact response-surface grid.
    for x in [280, 365, 450, 535, 620, 705, 790]:
        points = [(x, surface_y(x, depth)) for depth in depths]
        draw.line(
            scaled_points(points),
            fill=(186, 242, 228, 190),
            width=13 * SCALE,
        )

    peak_x = 520
    peak_y = surface_y(peak_x, -105)
    radius = 42
    draw.ellipse(
        (
            (peak_x - radius) * SCALE,
            (peak_y - radius) * SCALE,
            (peak_x + radius) * SCALE,
            (peak_y + radius) * SCALE,
        ),
        fill=(255, 105, 88, 255),
        outline=(255, 239, 233, 255),
        width=10 * SCALE,
    )

    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    icon = build_icon()
    icon.save(ASSET_DIR / "rsm_icon.png", optimize=True)
    icon.save(
        ASSET_DIR / "rsm_icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
