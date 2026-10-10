"""Render the JishAtlas SVG symbol as a multi-size Windows executable icon.

The editable vector source is ``jishatlas-icon.svg``. The matching geometry
below is rendered at high resolution for Windows' ICO resource, which cannot
embed SVG directly. Run this before PyInstaller whenever the SVG changes.
Requires Pillow (included in the development dependency group).
"""

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parent
SIZES = [16, 24, 32, 48, 64, 128, 256]
MASTER_SIZE = 256
SCALE = 4

BACKGROUND = "#17313D"
INDEX = "#F2EFE4"
MARK = "#72B7A4"


def _cubic(p0, p1, p2, p3, steps=32):
    """Flatten a cubic Bezier segment for Pillow's polygon renderer."""
    points = []
    for index in range(1, steps + 1):
        t = index / steps
        one_minus_t = 1 - t
        x = (
            one_minus_t**3 * p0[0]
            + 3 * one_minus_t**2 * t * p1[0]
            + 3 * one_minus_t * t**2 * p2[0]
            + t**3 * p3[0]
        )
        y = (
            one_minus_t**3 * p0[1]
            + 3 * one_minus_t**2 * t * p1[1]
            + 3 * one_minus_t * t**2 * p2[1]
            + t**3 * p3[1]
        )
        # Keep points in the SVG's 256-unit coordinate space; render_icon
        # applies the supersampling scale once when it builds the polygon.
        points.append((x, y))
    return points


def render_icon(size):
    """Render the same square mark as jishatlas-icon.svg at ``size`` pixels."""
    scale = size * SCALE / MASTER_SIZE
    canvas_size = size * SCALE
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def box(x0, y0, x1, y1):
        return tuple(round(value * scale) for value in (x0, y0, x1, y1))

    draw.rounded_rectangle(box(0, 0, 256, 256), radius=round(44 * scale), fill=BACKGROUND)
    for top in (91, 122, 153):
        draw.rounded_rectangle(box(43, top, 67, top + 12), radius=round(3 * scale), fill=INDEX)

    # Matches the custom J path in jishatlas-icon.svg, including both curves.
    outline = [(82, 61), (187, 61), (187, 162)]
    outline += _cubic((187, 162), (187, 204), (161, 228), (119, 228))
    outline += [(78, 228), (78, 192), (118, 192)]
    outline += _cubic((118, 192), (142, 192), (152, 182), (152, 160))
    outline += [(152, 97), (82, 97)]
    draw.polygon([(round(x * scale), round(y * scale)) for x, y in outline], fill=MARK)

    return image.resize((size, size), Image.Resampling.LANCZOS)


def main():
    master = render_icon(MASTER_SIZE)
    master.save(ASSETS / "icon.ico", format="ICO", sizes=[(size, size) for size in SIZES])
    print(f"Updated {ASSETS / 'icon.ico'} from jishatlas-icon.svg geometry ({SIZES})")


if __name__ == "__main__":
    main()
