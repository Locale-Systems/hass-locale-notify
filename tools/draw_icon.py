"""Draw the brand icon: a person with a notification-bell badge.

Regenerate with: <venv>/bin/python tools/draw_icon.py custom_components/locale_notify/brand
(needs Pillow, which the test harness installs).
"""
import sys
from PIL import Image, ImageDraw


def draw(size: int) -> Image.Image:
    s = 4 * size  # supersample, then downscale for smooth edges
    u = s / 256
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1):
        return [x0 * u, y0 * u, x1 * u, y1 * u]

    blue, dark = (30, 136, 229, 255), (55, 71, 79, 255)
    # Person: head and shoulders
    d.ellipse(box(60, 24, 148, 112), fill=blue)
    d.pieslice(box(20, 124, 188, 292), 180, 360, fill=blue)
    d.rectangle(box(20, 206, 188, 240), fill=blue)
    # Bell badge, with a ring so it reads on light and dark backgrounds
    d.ellipse(box(132, 120, 252, 240), fill=(255, 255, 255, 255))
    d.ellipse(box(140, 128, 244, 232), fill=(255, 202, 40, 255), outline=dark, width=round(6 * u))
    d.pieslice(box(164, 148, 220, 212), 180, 360, fill=dark)
    d.rectangle(box(164, 180, 220, 198), fill=dark)
    d.rounded_rectangle(box(156, 194, 228, 204), radius=4 * u, fill=dark)
    d.ellipse(box(184, 204, 200, 220), fill=dark)
    d.ellipse(box(186, 140, 198, 152), fill=dark)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    out = sys.argv[1]
    draw(256).save(f"{out}/icon.png")
    draw(512).save(f"{out}/icon@2x.png")
