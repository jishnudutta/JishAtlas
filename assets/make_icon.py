"""Generate the JishAtlas application icon.

Produces:
    assets/icon.ico   - multi-resolution Windows icon (16..256 px)
    assets/icon.png   - 512 px PNG (README / branding)

Design: a rounded-square cyan-blue gradient tile with a glossy white
folder, a subtle globe ring (the "Atlas" in JishAtlas), paper lines,
and a bright AI sparkle. Everything is rendered at 4x and downscaled
with LANCZOS so edges stay sharp at every size.

Usage:  python assets/make_icon.py
Requires: pillow (dev dependency)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ASSETS = Path(__file__).resolve().parent
SIZES = [16, 24, 32, 48, 64, 128, 256]
BASE = 256
SS = 4  # supersample factor

# Palette (cyan theme used across the CLI)
BG_TOP = (0, 198, 255)          # bright cyan
BG_BOTTOM = (10, 40, 120)       # deep blue
FOLDER_TOP = (255, 255, 255)
FOLDER_BOTTOM = (198, 228, 255)
FOLDER_TAB = (176, 216, 255)
FOLDER_LINE = (128, 170, 220)
SHADOW = (5, 15, 60, 160)
GLOBE_RING = (255, 255, 255, 90)
SPARK = (255, 232, 90)
SPARK_CORE = (255, 255, 255)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _vertical_gradient(size, box, top, bottom):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    h = max(1, y1 - y0)
    for y in range(y0, y1):
        color = _lerp(top, bottom, (y - y0) / max(1, h - 1))
        draw.line([(x0, y), (x1, y)], fill=color)
    return img


def _rounded_alpha(size, box, radius):
    """Return an L-mode mask with a rounded rectangle filled 255."""
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=255)
    return mask


def _sparkle_points(cx, cy, r):
    return [
        (cx, cy - r), (cx + r * 0.25, cy - r * 0.25), (cx + r, cy),
        (cx + r * 0.25, cy + r * 0.25), (cx, cy + r),
        (cx - r * 0.25, cy + r * 0.25), (cx - r, cy),
        (cx - r * 0.25, cy - r * 0.25),
    ]


def draw_icon(size):
    """Render the icon at a given size (master drawn at 4x, downscaled)."""
    ss = size * SS
    img = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))

    def s(v):
        return int(round(v * ss / BASE))

    def p(v):
        return max(1, int(round(v * ss / BASE)))

    # --- Background tile: rounded square with vertical gradient ---
    pad = s(10)
    corner = s(56)
    tile = _vertical_gradient(
        ss,
        (pad, pad, ss - pad, ss - pad),
        BG_TOP,
        BG_BOTTOM,
    )
    tile.putalpha(_rounded_alpha(ss, (pad, pad, ss - pad - 1, ss - pad - 1), corner))
    img.alpha_composite(tile)

    # --- Globe ring behind the folder (the "Atlas" nod) ---
    globe = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    gd = ImageDraw.Draw(globe)
    gcx, gcy = s(160), s(150)
    gr = s(64)
    gd.ellipse(
        [gcx - gr, gcy - gr, gcx + gr, gcy + gr],
        outline=GLOBE_RING,
        width=p(4),
    )
    gd.ellipse(
        [gcx - gr, gcy - gr // 2, gcx + gr, gcy + gr // 2],
        outline=GLOBE_RING,
        width=p(2),
    )
    img.alpha_composite(globe)

    # --- Folder shadow ---
    shadow = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [s(44), s(118), s(212), s(194)],
        radius=s(18),
        fill=SHADOW,
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(p(7)))
    img.alpha_composite(shadow)

    # --- Folder body (back panel) ---
    body_box = (s(38), s(102), s(218), s(190))
    body = _vertical_gradient(ss, body_box, FOLDER_TOP, FOLDER_BOTTOM)
    body.putalpha(_rounded_alpha(ss, body_box, s(18)))
    img.alpha_composite(body)

    # --- Folder tab (light gradient, cohesive with the body) ---
    tab_box = (s(38), s(70), s(104), s(106))
    tab_grad = _vertical_gradient(ss, tab_box, FOLDER_TOP, FOLDER_TAB)
    tab_grad.putalpha(_rounded_alpha(ss, tab_box, s(12)))
    img.alpha_composite(tab_grad)

    # --- Front flap (lighter, overlapping the body) ---
    flap_box = (s(38), s(142), s(218), s(190))
    flap = _vertical_gradient(ss, flap_box, FOLDER_TOP, (226, 240, 255))
    flap.putalpha(_rounded_alpha(ss, flap_box, s(18)))
    img.alpha_composite(flap)

    draw = ImageDraw.Draw(img)

    # --- Paper lines inside the folder ---
    line_color = (*FOLDER_LINE, 255)
    for i, y in enumerate([s(124), s(138), s(154)]):
        x1 = s(164) if i < 2 else s(140)
        draw.line(
            [(s(56), y), (x1, y)],
            fill=line_color,
            width=p(4),
        )

    # --- AI sparkle: soft glow halo, then crisp star on top ---
    glow = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.polygon(_sparkle_points(s(178), s(88), s(36)), fill=(*SPARK, 190))
    glow = glow.filter(ImageFilter.GaussianBlur(p(6)))
    img.alpha_composite(glow)

    draw.polygon(_sparkle_points(s(178), s(88), s(32)), fill=SPARK)
    draw.polygon(_sparkle_points(s(152), s(76), s(10)), fill=SPARK_CORE)

    return img.resize((size, size), Image.LANCZOS)


def main():
    master = draw_icon(BASE)

    # Multi-resolution ICO.
    master.save(
        ASSETS / "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in SIZES],
    )

    # Large PNG for branding / README.
    draw_icon(512).save(ASSETS / "icon.png", format="PNG")

    print(f"OK {ASSETS / 'icon.ico'} (sizes {SIZES})")
    print(f"OK {ASSETS / 'icon.png'} (512px)")


if __name__ == "__main__":
    main()
