"""Draws the Post Studio icon, in the palette the studio already uses.

    python scripts/make_icon.py

Writes `assets/post-studio.ico` for the Windows shortcut and prints the
`<link rel="icon">` tag for `page.html`, which is what the taskbar shows while
the app window is open: a Chrome app window takes its icon from the page's
favicon rather than from whatever launched it, so both are needed and both
should be the same mark.

WHY THIS IS CODE RATHER THAN A FILE SOMEBODY DREW. There is no image library
here and no designer, and a binary checked in with no way to regenerate it is
a thing nobody can change later. This is 200 lines of arithmetic and it can be
re-run after any change of mind about the colour.

THE MARK. Three bars, left aligned, of falling width, on the near-black tile
the app itself uses. Bars of *equal* width would read as a hamburger menu at
16 pixels, which is the size that matters most and the one people design for
last; falling widths and a brighter top bar read as written lines instead.
Nothing else survives being 16 pixels wide, which is why there is nothing else.
"""

from __future__ import annotations

import base64
import math
import pathlib
import struct
import zlib

REPO = pathlib.Path(__file__).resolve().parents[1]
TARGET = REPO / "assets" / "post-studio.ico"

#: From page.html: the app ground and the one accent colour it allows itself.
GROUND = (2, 4, 10)
CYAN_BRIGHT = (103, 232, 249)
CYAN = (34, 211, 238)

#: Every size Windows asks for, from the taskbar to the alt-tab card.
SIZES = (16, 32, 48, 64, 128, 256)

#: Drawn this many times larger and averaged down, which is the whole
#: anti-aliasing strategy. Cheap, and exact enough that a rounded corner at 16
#: pixels does not look chewed.
SUPERSAMPLE = 4

Pixel = tuple[int, int, int, int]


def _rounded_box(x: float, y: float, left: float, top: float, right: float, bottom: float, radius: float) -> float:
    """Signed distance from a rounded rectangle. Negative means inside."""
    # Distance to the nearest corner circle's centre, clamped into the box's
    # straight-edged core, which is the standard rounded-rect field.
    cx = min(max(x, left + radius), right - radius)
    cy = min(max(y, top + radius), bottom - radius)
    return math.hypot(x - cx, y - cy) - radius


def _blend(under: Pixel, over: tuple[int, int, int], alpha: float) -> Pixel:
    if alpha <= 0:
        return under
    r, g, b, a = under
    nr = round(r * (1 - alpha) + over[0] * alpha)
    ng = round(g * (1 - alpha) + over[1] * alpha)
    nb = round(b * (1 - alpha) + over[2] * alpha)
    na = round(a * (1 - alpha) + 255 * alpha)
    return (nr, ng, nb, na)


def render(size: int) -> list[list[Pixel]]:
    """One icon, at one size, already anti-aliased."""
    big = size * SUPERSAMPLE
    grid: list[list[Pixel]] = [[(0, 0, 0, 0) for _ in range(big)] for _ in range(big)]

    tile_radius = big * 0.22
    # A hair of inset so the tile's own edge is antialiased rather than being
    # cut off square by the edge of the canvas.
    inset = big * 0.02

    # Bars: left aligned, falling width, the top one brighter. The numbers are
    # fractions of the tile so every size renders the same picture.
    # Tops chosen so the space above the first bar and below the last match:
    # the block runs 0.28 to 0.725, leaving 0.28 above and 0.275 below. The
    # first draft sat visibly low, which is the sort of thing only a magnified
    # side-by-side shows and every taskbar then shows forever.
    bars = (
        (0.28, 0.60, CYAN_BRIGHT),
        (0.46, 0.43, CYAN),
        (0.64, 0.29, CYAN),
    )
    bar_height = big * 0.085
    bar_left = big * 0.20

    for py in range(big):
        y = py + 0.5
        for px in range(big):
            x = px + 0.5

            if _rounded_box(x, y, inset, inset, big - inset, big - inset, tile_radius) < 0:
                grid[py][px] = (*GROUND, 255)
            else:
                continue

            for top_fraction, width_fraction, colour in bars:
                top = big * top_fraction
                bar_width = big * width_fraction
                # Capsule ends: a rounded box whose radius is half its height.
                distance = _rounded_box(
                    x,
                    y,
                    bar_left,
                    top,
                    bar_left + bar_width,
                    top + bar_height,
                    bar_height / 2,
                )
                if distance < 0:
                    grid[py][px] = _blend(grid[py][px], colour, 1.0)

    return _downsample(grid, size)


def _downsample(grid: list[list[Pixel]], size: int) -> list[list[Pixel]]:
    """Box filter, which is all the smoothing a flat mark needs."""
    out: list[list[Pixel]] = []
    span = SUPERSAMPLE * SUPERSAMPLE
    for y in range(size):
        row: list[Pixel] = []
        for x in range(size):
            r = g = b = a = 0
            for sy in range(SUPERSAMPLE):
                for sx in range(SUPERSAMPLE):
                    pr, pg, pb, pa = grid[y * SUPERSAMPLE + sy][x * SUPERSAMPLE + sx]
                    r += pr
                    g += pg
                    b += pb
                    a += pa
            row.append((r // span, g // span, b // span, a // span))
        out.append(row)
    return out


def to_png(grid: list[list[Pixel]]) -> bytes:
    """A minimal RGBA PNG. Written here because there is no image library."""
    size = len(grid)
    raw = bytearray()
    for row in grid:
        # Filter type 0 (None) per scanline. The mark is flat colour, so the
        # smarter filters would buy almost nothing for a lot more code.
        raw.append(0)
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def to_ico(images: list[tuple[int, bytes]]) -> bytes:
    """Packs PNGs into an .ico. Windows has read PNG entries since Vista."""
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)
    # Every entry's offset depends on the size of the whole directory, so the
    # directory has to be measured before any of it can be written.
    offset = len(header) + 16 * count
    directory = b""
    body = b""
    for size, png in images:
        # 0 means 256 in the one byte the format gives each dimension.
        stored = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", stored, stored, 0, 0, 1, 32, len(png), offset)
        body += png
        offset += len(png)
    return header + directory + body


def main() -> int:
    images = [(size, to_png(render(size))) for size in SIZES]
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(to_ico(images))
    print(f"wrote {TARGET} ({TARGET.stat().st_size:,} bytes, {len(SIZES)} sizes)")

    # 32px is what a browser tab and a Chrome app window's taskbar entry use.
    favicon = dict(images)[32]
    encoded = base64.b64encode(favicon).decode("ascii")
    print("\nFor page.html, inside <head>:\n")
    print(f'<link rel="icon" type="image/png" href="data:image/png;base64,{encoded}">')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
