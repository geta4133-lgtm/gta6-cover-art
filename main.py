#!/usr/bin/env python3
"""
gta6-cover-art-01 — GTA VI themed cover-art generator.

Generates a 1080x1350 PNG (4:5 portrait) with a neon Miami sunset palette,
palm tree silhouettes, and a bold title block. Everything is drawn
procedurally with a tiny software rasterizer and written out through a
hand-rolled PNG encoder (only `zlib`/`struct`/`binascii` from stdlib are
used for compression/chunks). Fully deterministic: same input -> same bytes.

Run: python3 main.py
Out: gta6-cover-art-01.png
"""

import math
import struct
import zlib
import random

W, H = 1080, 1350

# ---------------------------------------------------------------- palette
SKY_TOP    = (14, 4, 44)      # deep indigo night
SKY_MID    = (90, 15, 105)    # purple
SKY_HOT    = (219, 62, 92)    # hot pink
SKY_LOW    = (255, 94, 58)    # orange
SUN_CORE   = (255, 214, 120)  # golden
SUN_EDGE   = (255, 128, 79)   # peach
SEA_TOP    = (38, 8, 78)
SEA_BOT    = (180, 40, 110)
GRID_A     = (255, 92, 160)   # neon pink grid lines
GRID_B     = (64, 230, 255)   # neon cyan grid lines
PALM       = (5, 2, 16)       # near-black silhouette
TITLE_INK  = (16, 6, 40)
TITLE_HOT  = (255, 96, 170)
TITLE_CYAN = (72, 224, 255)
GOLD       = (255, 196, 84)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = min(255, max(0, int(c[0])))
            self.px[i + 1] = min(255, max(0, int(c[1])))
            self.px[i + 2] = min(255, max(0, int(c[2])))

    def blend(self, x, y, c, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = int(lerp(self.px[i], c[0], a))
            self.px[i + 1] = int(lerp(self.px[i + 1], c[1], a))
            self.px[i + 2] = int(lerp(self.px[i + 2], c[2], a))

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return (self.px[i], self.px[i + 1], self.px[i + 2])


def gradient_band(cv, y0, y1, c0, c1, x0=0, x1=None):
    """Vertical gradient painted row-by-row (also supports non-full-width)."""
    if x1 is None:
        x1 = cv.w
    span = max(1, y1 - y0)
    for y in range(max(0, y0), min(cv.h, y1)):
        t = (y - y0) / span
        c = mix(c0, c1, t)
        c = (int(c[0]), int(c[1]), int(c[2]))
        row = y * cv.w
        for x in range(x0, x1):
            i = (row + x) * 3
            cv.px[i] = c[0]
            cv.px[i + 1] = c[1]
            cv.px[i + 2] = c[2]


# ---------------------------------------------------------------- geometry
def fill_rect(cv, x0, y0, x1, y1, c):
    for y in range(max(0, int(y0)), min(cv.h, int(y1) + 1)):
        for x in range(max(0, int(x0)), min(cv.w, int(x1) + 1)):
            cv.set(x, y, c)


def fill_circle(cv, cx, cy, r, c, edge=None):
    """Filled circle with optional darker edge ring (used for the sun)."""
    r2 = r * r
    for y in range(max(0, int(cy - r) - 1), min(cv.h, int(cy + r) + 2)):
        dy = y - cy
        w = math.sqrt(max(0.0, r2 - dy * dy)) if abs(dy) <= r else 0.0
        if w <= 0:
            continue
        xa, xb = int(cx - w), int(cx + w)
        for x in range(xa, xb + 1):
            dx = x - cx
            if dx * dx + dy * dy <= r2:
                if edge is not None and dx * dx + dy * dy > (r - 6) * (r - 6):
                    cv.set(x, y, edge)
                else:
                    cv.set(x, y, c)


def hline_glow(cv, x0, x1, y, c, a=1.0, thick=1, glow=2):
    for dy in range(-glow - thick // 2, thick // 2 + thick + glow):
        d = abs(dy) - thick // 2
        alpha = a * max(0.0, 1.0 - d / (glow + 1.0)) if d > 0 else a
        if alpha <= 0:
            continue
        yy = int(y + dy)
        if 0 <= yy < cv.h:
            for x in range(max(0, x0), min(cv.w, x1)):
                cv.blend(x, yy, c, alpha)


def line(cv, x0, y0, x1, y1, c):
    """Bresenham-ish DDA line."""
    steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    if steps <= 1:
        cv.set(int(x0), int(y0), c)
        return
    for i in range(steps + 1):
        t = i / steps
        cv.set(int(round(lerp(x0, x1, t))), int(round(lerp(y0, y1, t))), c)


def poly_fill(cv, pts, c):
    """Scanline polygon fill (even-odd rule)."""
    ys = [p[1] for p in pts]
    for y in range(max(0, int(min(ys))), min(cv.h, int(max(ys)) + 2)):
        xs = []
        n = len(pts)
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if (ay <= y < by) or (by <= y < ay):
                xs.append(ax + (y - ay) / (by - ay) * (bx - ax))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(xs[j])), min(cv.w, int(xs[j + 1]) + 1)):
                cv.set(x, y, c)


# ---------------------------------------------------------------- scene
def draw_sky(cv):
    horizon = int(H * 0.62)
    band = [
        (0,    int(H * 0.22), SKY_TOP, SKY_TOP),
        (int(H * 0.22), int(H * 0.40), SKY_TOP, SKY_MID),
        (int(H * 0.40), int(H * 0.52), SKY_MID, SKY_HOT),
        (int(H * 0.52), horizon, SKY_HOT, SKY_LOW),
    ]
    for y0, y1, a, b in band:
        gradient_band(cv, y0, y1, a, b)

    # soft stars in the upper third (fixed seed -> deterministic)
    rnd = random.Random(1987)
    for _ in range(140):
        x = rnd.randrange(0, W)
        y = rnd.randrange(0, int(H * 0.34))
        b = rnd.uniform(0.25, 0.85)
        cv.blend(x, y, (255, 236, 210), b)


def draw_sun(cv):
    cx, cy, r = W // 2, int(H * 0.545), 150
    # glow halo
    for y in range(cy - 2 * r, cy + 2 * r):
        for x in range(cx - 2 * r, cx + 2 * r):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 < (2 * r) ** 2 and d2 > r * r:
                t = 1.0 - (math.sqrt(d2) - r) / r
                cv.blend(x, y, SUN_EDGE, 0.28 * t * t)
    fill_circle(cv, cx, cy, r, SUN_CORE, edge=SUN_EDGE)
    # retro sun slats (horizontal cut lines)
    slat_h, gap = 6, 9
    y = cy + int(r * 0.18)
    while y < cy + r:
        fill_rect(cv, cx - r - 2, y, cx + r + 2, y + slat_h - 1, mix(SKY_LOW, SUN_EDGE, 0.25))
        y += slat_h + gap


def draw_ocean(cv):
    horizon = int(H * 0.62)
    bottom = int(H * 0.80)
    gradient_band(cv, horizon, bottom, SEA_TOP, SEA_BOT, x1=W)

    # perspective neon grid on the water
    rows = 14
    for i in range(rows):
        t = i / rows
        y = horizon + int((bottom - horizon) * (t * t))
        c = mix(GRID_A, GRID_B, t)
        hline_glow(cv, 0, W, y, c, a=0.55, thick=1, glow=1)

    # vertical grid lines converging to a vanishing point
    vpx, vpy = W // 2, horizon
    for i in range(-8, 9):
        xb = W // 2 + i * 130
        steps = bottom - horizon
        for s in range(steps):
            t = s / steps
            x = int(lerp(vpx, xb, t * t))
            y = horizon + s
            cv.blend(x, y, mix(GRID_A, GRID_B, t), 0.35)

    # sun reflection column
    for y in range(horizon, bottom, 2):
        t = (y - horizon) / (bottom - horizon)
        w = int(lerp(28, 110, t))
        c = mix(SUN_CORE, GRID_A, t)
        for dx in range(-w, w + 1):
            if abs(dx) % 5 < 3:
                cv.blend(W // 2 + dx, y, c, 0.20 * (1 - t) + 0.10)


def draw_palm(cv, cx, base_y, height, lean, rnd):
    """Silhouette palm: curved trunk + 8 fronds."""
    # trunk (series of short segments with curvature)
    segs = 22
    pts = []
    for i in range(segs + 1):
        t = i / segs
        x = cx + lean * (t * t) * 1.0 + math.sin(t * 3.1) * 6
        y = base_y - height * t
        pts.append((x, y))
    for i in range(segs):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        w = max(2, int(9 * (1 - i / segs) + 3))
        steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for s in range(steps + 1):
            t = s / steps
            x = lerp(x0, x1, t)
            y = lerp(y0, y1, t)
            fill_rect(cv, x - w / 2, y - 1, x + w / 2, y + 1, PALM)
    tx, ty = pts[-1]

    # fronds
    n = 9
    for k in range(n):
        ang = math.pi * (k / (n - 1))  # 0..pi fan
        L = rnd.uniform(78, 118)
        droop = rnd.uniform(0.9, 1.5)
        prev = (tx, ty)
        for s in range(1, 15):
            t = s / 14
            a = ang + t * 0.5 * droop * (1 if k % 2 == 0 else -1)
            px = tx + math.cos(ang) * L * t
            py = ty - math.sin(ang) * L * t * (1 - 0.55 * t * t)
            px += math.sin(t * 5.0 + k) * 3
            line(cv, prev[0], prev[1], px, py, PALM)
            prev = (px, py)
        # little leaf notches
        mx, my = prev
        for d in range(-3, 4):
            cv.set(int(mx + d), int(my + d * 0.6), PALM)

    # coconuts
    for d in ((-9, 6), (9, 8), (0, 12)):
        fill_circle(cv, tx + d[0], ty + d[1], 5, PALM)


def draw_ground(cv):
    """Dark promenade at the bottom where the palms stand."""
    y0 = int(H * 0.80)
    gradient_band(cv, y0, H, (10, 3, 24), (24, 6, 48))
    # boardwalk stripes
    for i in range(6):
        y = y0 + 14 + i * 22
        hline_glow(cv, 0, W, y, GRID_A, a=0.18, thick=2, glow=3)


def draw_frame(cv):
    """Neon inner frame + corner ticks."""
    m = 34
    for (x0, y0, x1, y1) in (
        (m, m, W - m, m),
        (W - m, m, W - m, H - m),
        (W - m, H - m, m, H - m),
        (m, H - m, m, m),
    ):
        line(cv, x0, y0, x1, y1, GRID_B)
        line(cv, x0 + 1, y0, x1 + 1, y1, mix(GRID_B, (0, 0, 0), 0.7))
    tl = 26
    for cx, cy, dx, dy in ((m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)):
        for i in range(tl):
            cv.set(cx + dx * i, cy, TITLE_HOT)
            cv.set(cx, cy + dy * i, TITLE_HOT)


# ---------------------------------------------------------------- glyphs
# 5x7 pixel font for the title + small text. Deterministic, original shapes.
FONT = {
    'G': ["01111", "10000", "10000", "10011", "10001", "10001", "01110"],
    'T': ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    'A': ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    '6': ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    'V': ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    'I': ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    'M': ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    'E': ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    ':': ["00000", "00100", "00100", "00000", "00100", "00100", "00000"],
    'C': ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    'O': ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    'V2': None,  # placeholder guard (unused)
    'R': ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    'D': ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    'S': ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    'N': ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    'U': ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    'W': ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    'P': ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    'L': ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    'Y': ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    'B': ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    'O2': None,
    'F': ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    'U2': None,
    'N2': None,
    '.': ["00000", "00000", "00000", "00000", "00000", "00110", "00110"],
    '-': ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ' ': ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    '2': ["01110", "10001", "00001", "00110", "01000", "10000", "11111"],
    '0': ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    '1': ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
}


def draw_text(cv, text, x, y, scale, c, shadow=None, shadow_off=None):
    """Draw text with the 5x7 font at an integer scale."""
    cx = x
    for ch in text:
        g = FONT.get(ch)
        if g is None:
            g = FONT.get(ch + '2') or FONT[' ']
        for gy in range(7):
            for gx in range(5):
                if g[gy][gx] == '1':
                    for sy in range(scale):
                        for sx in range(scale):
                            px, py = cx + gx * scale + sx, y + gy * scale + sy
                            if shadow is not None:
                                so = shadow_off or (scale, scale)
                                cv.blend(px + so[0], py + so[1], shadow, 0.85)
                            cv.set(px, py, c)
        cx += 6 * scale


def draw_title_block(cv):
    """Bold 'GTA VI' style title + subtitle, original typeface shapes."""
    tx = 92
    y = int(H * 0.845)

    # soft neon glow plate behind the title
    for dy in range(-18, 82):
        a = max(0.0, 0.30 - abs(dy - 30) / 220)
        if a > 0:
            for dx in range(-24, 640):
                cv.blend(tx + dx, y + dy, TITLE_HOT, a * 0.35)

    draw_text(cv, "GTA", tx, y, 12, TITLE_INK, shadow=TITLE_HOT, shadow_off=(7, 7))
    draw_text(cv, "VI", tx + 3 * 6 * 12 + 22, y, 12, TITLE_INK, shadow=TITLE_HOT, shadow_off=(7, 7))

    # cyan keyline under title
    hline_glow(cv, tx - 6, tx + 560, y + 7 * 12 + 16, TITLE_CYAN, a=0.9, thick=3, glow=4)
    hline_glow(cv, tx - 6, tx + 330, y + 7 * 12 + 26, TITLE_HOT, a=0.8, thick=2, glow=3)

    # subtitle
    draw_text(cv, "VICE ISLES", tx + 2, y + 7 * 12 + 40, 6, GOLD, shadow=(10, 4, 30), shadow_off=(3, 3))

    # footer credit line
    draw_text(cv, "COMING: 2026 - LEONIDA", tx + 2, H - 96, 4, (255, 220, 200),
              shadow=(30, 8, 40), shadow_off=(2, 2))
    draw_text(cv, "ORIGINAL FAN ART", tx + 2, H - 70, 4, TITLE_CYAN)


def render():
    cv = Canvas(W, H)
    draw_sky(cv)
    draw_ocean(cv)
    draw_sun(cv)
    # re-paint ocean band over sun bottom so the sun "sits" behind water slats
    draw_ground(cv)
    rnd = random.Random(6)
    draw_palm(cv, 150, int(H * 0.84), 400, 40, rnd)
    draw_palm(cv, 330, int(H * 0.815), 300, 24, rnd)
    draw_palm(cv, W - 160, int(H * 0.84), 420, -46, rnd)
    draw_palm(cv, W - 340, int(H * 0.815), 290, -26, rnd)
    draw_title_block(cv)
    draw_frame(cv)
    return cv


# ---------------------------------------------------------------- PNG out
def chunk(tag, data):
    raw = tag + data
    return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)


def write_png(path, cv):
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)  # 8-bit RGB
    stride = cv.w * 3
    scan = bytearray()
    for y in range(cv.h):
        scan.append(0)  # filter type 0 (None) — deterministic, simple
        scan += cv.px[y * stride:(y + 1) * stride]
    idat = zlib.compress(bytes(scan), 9)
    with open(path, "wb") as f:
        f.write(sig)
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", idat))
        f.write(chunk(b"IEND", b""))


def main():
    cv = render()
    write_png("gta6-cover-art-01.png", cv)
    print("wrote gta6-cover-art-01.png ({}x{})".format(cv.w, cv.h))


if __name__ == "__main__":
    main()
