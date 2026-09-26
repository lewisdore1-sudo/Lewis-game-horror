"""Procedural asset generation — every texture and sound in the game is made
here from maths, so the project ships with no third-party art or audio.

Runs once on first launch (a few seconds) and caches into assets/generated/.
Delete that folder to regenerate. Only needs numpy + Pillow.
"""
from __future__ import annotations

import math
import os
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ASSET_VERSION = "6"
TEX = 512


# ==========================================================================
# Noise helpers (FFT-filtered noise is periodic, so every texture tiles)
# ==========================================================================
def fbm(n: int, beta: float, rng: np.random.Generator, aniso: tuple[float, float] = (1.0, 1.0)) -> np.ndarray:
    """Seamless 1/f^beta noise, normalised to 0..1."""
    white = rng.standard_normal((n, n))
    f = np.fft.fft2(white)
    fy = np.fft.fftfreq(n)[:, None] * aniso[1]
    fx = np.fft.fftfreq(n)[None, :] * aniso[0]
    r = np.sqrt(fx ** 2 + fy ** 2)
    r[0, 0] = 1.0
    f *= 1.0 / (r ** beta)
    f[0, 0] = 0
    out = np.real(np.fft.ifft2(f))
    out -= out.min()
    out /= out.max() + 1e-9
    return out


def _rgb(h: np.ndarray, lo, hi) -> np.ndarray:
    lo, hi = np.array(lo, float), np.array(hi, float)
    return lo + (hi - lo) * h[..., None]


def _save_rgb(arr: np.ndarray, path: str):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").save(path)


def _save_rgba(arr: np.ndarray, path: str):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA").save(path)


def normal_from_height(h: np.ndarray, strength: float) -> np.ndarray:
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    n = np.stack([-dx, dy, np.ones_like(h)], axis=-1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return (n * 0.5 + 0.5) * 255


def _grid(n=TEX):
    y, x = np.mgrid[0:n, 0:n].astype(float) / n
    return x, y


# ==========================================================================
# Surfaces — each returns (rgb 0..255, height 0..1)
# ==========================================================================
def tex_damask(rng):
    x, y = _grid()
    # A symmetric medallion motif, repeated 2x2 per tile, offset every other row
    def motif(u, v):
        cu, cv = (u % 0.5) - 0.25, (v % 0.5) - 0.25
        r = np.sqrt(cu ** 2 + (cv * 0.75) ** 2)
        a = np.arctan2(cv, np.abs(cu))
        petals = np.cos(a * 6) * 0.035 + 0.13
        m = (np.abs(r - petals) < 0.012) | (r < 0.03)
        vine = np.abs(np.sin((cv + np.abs(cu) * 1.4) * math.tau * 4)) < 0.08
        return m | (vine & (r < 0.22) & (r > 0.15))
    pat = motif(x, y) | motif(x + 0.25, y + 0.25)
    pat = np.array(Image.fromarray((pat * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 255.0
    age = fbm(TEX, 1.6, rng)
    stripes = 0.5 + 0.5 * np.cos(x * math.tau * 16)
    base = _rgb(age * 0.35 + stripes * 0.05, (14, 30, 31), (40, 62, 60))
    gold = np.array([112, 98, 62], float)
    rgb = base * (1 - pat[..., None] * 0.75) + gold * pat[..., None] * 0.75
    stain = np.clip((fbm(TEX, 2.2, rng) - 0.62) * 3, 0, 1)
    rgb *= (1 - stain[..., None] * 0.35)
    return rgb, pat * 0.7 + age * 0.3


def tex_wallpaper(rng, base_lo, base_hi, accent, stripe_n=10, floral=False):
    x, y = _grid()
    age = fbm(TEX, 1.7, rng)
    stripe = (np.abs(np.sin(x * math.pi * stripe_n)) > 0.93).astype(float)
    rgb = _rgb(age * 0.5, base_lo, base_hi)
    pat = stripe
    if floral:
        u, v = (x * 4) % 1 - 0.5, (y * 4 + np.floor(x * 4) * 0.5) % 1 - 0.5
        r = np.sqrt(u ** 2 + v ** 2)
        a = np.arctan2(v, u)
        flower = (r < 0.12 + 0.05 * np.cos(a * 5)) & (r > 0.04)
        pat = np.maximum(pat, flower.astype(float))
    pat = np.array(Image.fromarray((pat * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))) / 255.0
    rgb = rgb * (1 - pat[..., None] * 0.5) + np.array(accent, float) * pat[..., None] * 0.5
    return rgb, pat * 0.6 + age * 0.4


def tex_stone(rng, mossy=True):
    x, y = _grid()
    rows = 8
    row = np.floor(y * rows)
    offs = (row % 2) * 0.5 / 4
    col = np.floor((x + offs) * 4)
    fx = ((x + offs) * 4) % 1
    fy = (y * rows) % 1
    mortar = np.minimum(np.minimum(fx, 1 - fx) * 4 * 0.5, np.minimum(fy, 1 - fy) * 4)
    mortar = np.clip(mortar * 6, 0, 1)
    rnd = np.random.default_rng(int(rng.integers(1e9)))
    tint = rnd.uniform(0.75, 1.1, (rows, 4))[row.astype(int) % rows, col.astype(int) % 4]
    n = fbm(TEX, 1.4, rng)
    h = mortar * (0.6 + 0.4 * n)
    rgb = _rgb(n * 0.6 + 0.2, (48, 50, 48), (118, 118, 110)) * tint[..., None]
    rgb *= (0.45 + 0.55 * mortar[..., None])
    if mossy:
        moss = np.clip((fbm(TEX, 2.0, rng) - 0.55) * 3, 0, 1) * (1 - mortar * 0.5)
        rgb = rgb * (1 - moss[..., None] * 0.6) + np.array([40, 58, 30]) * moss[..., None] * 0.6
    return rgb, h


def tex_marble(rng):
    x, y = _grid()
    check = ((np.floor(x * 2) + np.floor(y * 2)) % 2).astype(float)
    n = fbm(TEX, 1.8, rng)
    vein = np.abs(np.sin((x * 3 + y * 2 + n * 3.0) * math.pi * 2))
    vein = np.clip(1 - vein * 8, 0, 1) * 0.6
    light = _rgb(n * 0.15, (178, 174, 164), (206, 203, 194))
    dark = _rgb(n * 0.15, (18, 20, 21), (36, 38, 40))
    rgb = light * check[..., None] + dark * (1 - check[..., None])
    rgb = rgb * (1 - vein[..., None]) + np.where(check[..., None] > 0.5, 110, 80) * vein[..., None]
    grout = np.minimum(np.abs((x * 2) % 1 - 0.5), np.abs((y * 2) % 1 - 0.5))
    gmask = np.clip((0.497 - grout) * 400, 0, 1)
    edge = 1 - np.clip((0.5 - grout) * 250, 0, 1)
    rgb *= (1 - edge[..., None] * 0.5)
    return rgb, gmask * 0.9 + n * 0.1


def tex_wood_floor(rng):
    x, y = _grid()
    planks = 6
    col = np.floor(x * planks)
    fx = (x * planks) % 1
    rnd = np.random.default_rng(int(rng.integers(1e9)))
    shift = rnd.uniform(0, 1, planks)[col.astype(int) % planks]
    seg = np.floor((y + shift) * 2)
    fy = ((y + shift) * 2) % 1
    grain_n = fbm(TEX, 1.2, rng, aniso=(1.0, 0.08))
    rings = np.sin((grain_n * 18 + fx * 2) * math.pi) * 0.5 + 0.5
    tone = rnd.uniform(0.7, 1.15, (planks, 4))[col.astype(int) % planks, seg.astype(int) % 4]
    rgb = _rgb(rings * 0.5 + grain_n * 0.5, (46, 26, 14), (104, 64, 36)) * tone[..., None]
    gap = np.clip(np.minimum(fx, 1 - fx) * 60, 0, 1) * np.clip(np.minimum(fy, 1 - fy) * 120, 0, 1)
    rgb *= (0.35 + 0.65 * gap[..., None])
    wear = fbm(TEX, 2.0, rng)
    rgb *= (0.85 + 0.25 * wear[..., None])
    return rgb, gap * 0.7 + rings * 0.3


def tex_wood_dark(rng):
    x, y = _grid()
    g = fbm(TEX, 1.2, rng, aniso=(1.0, 0.06))
    rings = np.sin(g * 40) * 0.5 + 0.5
    rgb = _rgb(rings * 0.6 + g * 0.4, (22, 12, 7), (70, 40, 22))
    return rgb, rings


def tex_carpet(rng):
    x, y = _grid()
    n = fbm(TEX, 0.9, rng)
    fib = fbm(TEX, 0.3, rng)
    u = np.abs(x - 0.5)
    border = (u > 0.36) & (u < 0.42)
    diamond = (np.abs((x * 4) % 1 - 0.5) + np.abs((y * 4) % 1 - 0.5)) < 0.18
    base = _rgb(n * 0.4 + fib * 0.3, (58, 10, 14), (110, 24, 26))
    gold = np.array([128, 96, 44], float)
    m = (border | (diamond & (u < 0.34))).astype(float)
    m = np.array(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))) / 255
    rgb = base * (1 - m[..., None] * 0.7) + gold * m[..., None] * 0.7
    return rgb, fib * 0.6 + m * 0.4


def tex_plaster(rng):
    n = fbm(TEX, 1.9, rng)
    fine = fbm(TEX, 0.8, rng)
    rgb = _rgb(n * 0.3 + fine * 0.2, (150, 144, 128), (196, 190, 172))
    water = np.clip((fbm(TEX, 2.3, rng) - 0.6) * 4, 0, 1)
    rgb = rgb * (1 - water[..., None] * 0.35) + np.array([120, 96, 60]) * water[..., None] * 0.2
    return rgb, fine * 0.5 + n * 0.5


def tex_panel(rng):
    """Corridor wood panelling: vertical boards with raised panels."""
    x, y = _grid()
    fx, fy = (x * 2) % 1, (y * 2) % 1
    inset = (np.minimum(fx, 1 - fx) > 0.1) & (np.minimum(fy, 1 - fy) > 0.1)
    bevel = np.clip(np.minimum(np.minimum(fx, 1 - fx), np.minimum(fy, 1 - fy)) * 12, 0, 1)
    g = fbm(TEX, 1.2, rng, aniso=(0.08, 1.0))
    rgb = _rgb(g, (38, 22, 13), (78, 46, 26)) * (0.8 + 0.2 * inset[..., None])
    return rgb, bevel * 0.7 + g * 0.3


def tex_grass(rng):
    n = fbm(TEX, 1.3, rng)
    blades = fbm(TEX, 0.4, rng)
    rgb = _rgb(n * 0.5 + blades * 0.5, (14, 26, 12), (52, 74, 34))
    dirt = np.clip((fbm(TEX, 2.0, rng) - 0.65) * 3, 0, 1)
    rgb = rgb * (1 - dirt[..., None] * 0.5) + np.array([50, 40, 28]) * dirt[..., None] * 0.5
    return rgb, blades


def tex_hedge(rng):
    n = fbm(TEX, 1.0, rng)
    leaves = fbm(TEX, 0.55, rng)
    h = np.clip(leaves * 1.4 - 0.2, 0, 1)
    rgb = _rgb(h * 0.7 + n * 0.3, (6, 16, 6), (48, 76, 34))
    rgb *= (0.5 + 0.6 * h[..., None])
    return rgb, h


def tex_gravel(rng):
    x, y = _grid()
    cells = 40
    rnd = np.random.default_rng(int(rng.integers(1e9)))
    pts = rnd.uniform(0, 1, (cells * 6, 2))
    img = Image.new("L", (TEX, TEX), 0)
    d = ImageDraw.Draw(img)
    for px, py in pts:
        r = rnd.uniform(5, 13)
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                cx, cy = (px + ox) * TEX, (py + oy) * TEX
                d.ellipse([cx - r, cy - r * 0.8, cx + r, cy + r * 0.8], fill=int(rnd.uniform(120, 255)))
    h = np.array(img.filter(ImageFilter.GaussianBlur(1.6))) / 255.0
    n = fbm(TEX, 1.5, rng)
    rgb = _rgb(h * 0.7 + n * 0.3, (44, 42, 36), (138, 130, 116))
    return rgb, h


def tex_tile(rng):
    x, y = _grid()
    fx, fy = (x * 4) % 1, (y * 4) % 1
    grout = np.clip(np.minimum(np.minimum(fx, 1 - fx), np.minimum(fy, 1 - fy)) * 40, 0, 1)
    n = fbm(TEX, 1.6, rng)
    rnd = np.random.default_rng(int(rng.integers(1e9)))
    tone = rnd.uniform(0.8, 1.1, (4, 4))[(np.floor(y * 4) % 4).astype(int), (np.floor(x * 4) % 4).astype(int)]
    rgb = _rgb(n, (86, 42, 26), (140, 74, 46)) * tone[..., None]
    rgb *= (0.4 + 0.6 * grout[..., None])
    return rgb, grout


def tex_fabric(rng, lo, hi):
    x, y = _grid()
    weave = (np.sin(x * math.tau * 128) * np.sin(y * math.tau * 128)) * 0.5 + 0.5
    n = fbm(TEX, 1.4, rng)
    rgb = _rgb(n * 0.6 + weave * 0.25, lo, hi)
    return rgb, weave


def tex_bark(rng):
    n = fbm(TEX, 1.1, rng, aniso=(1.0, 0.1))
    ridges = np.abs(np.sin(n * 25))
    rgb = _rgb(ridges * 0.6 + n * 0.4, (18, 14, 10), (70, 58, 46))
    return rgb, ridges


SURFACES = {
    "damask": (lambda r: tex_damask(r), 3.0),
    "wall_study": (lambda r: tex_wallpaper(r, (14, 32, 22), (36, 58, 40), (90, 110, 70), 12), 2.5),
    "wall_rose": (lambda r: tex_wallpaper(r, (86, 50, 54), (138, 92, 92), (170, 140, 120), 8, True), 2.5),
    "wall_gallery": (lambda r: tex_wallpaper(r, (40, 8, 10), (78, 20, 22), (110, 70, 40), 6), 2.5),
    "wall_parlour": (lambda r: tex_wallpaper(r, (64, 54, 22), (104, 90, 40), (60, 40, 20), 14), 2.5),
    "stone": (lambda r: tex_stone(r), 4.0),
    "marble": (lambda r: tex_marble(r), 5.0),
    "wood": (lambda r: tex_wood_floor(r), 4.0),
    "wood_dark": (lambda r: tex_wood_dark(r), 2.0),
    "carpet": (lambda r: tex_carpet(r), 1.5),
    "plaster": (lambda r: tex_plaster(r), 2.5),
    "panel": (lambda r: tex_panel(r), 3.0),
    "grass": (lambda r: tex_grass(r), 3.0),
    "hedge": (lambda r: tex_hedge(r), 6.0),
    "gravel": (lambda r: tex_gravel(r), 5.0),
    "tile": (lambda r: tex_tile(r), 4.0),
    "fabric_red": (lambda r: tex_fabric(r, (44, 6, 10), (98, 20, 24)), 1.5),
    "fabric_linen": (lambda r: tex_fabric(r, (150, 144, 130), (212, 206, 192)), 1.5),
    "fabric_green": (lambda r: tex_fabric(r, (16, 36, 28), (44, 76, 58)), 1.5),
    "bark": (lambda r: tex_bark(r), 4.0),
}


# ==========================================================================
# Paintings, decals, sky, overlays
# ==========================================================================
def painting(idx: int, rng) -> np.ndarray:
    """Dark oil-painting style canvases. The figures never have faces."""
    w, h = 256, 320
    y, x = np.mgrid[0:h, 0:w].astype(float)
    n = np.array(Image.fromarray((fbm(TEX, 1.5, rng)[:h, :w] * 255).astype(np.uint8))) / 255.0
    palettes = [((20, 16, 12), (84, 62, 40)), ((10, 14, 18), (52, 66, 72)), ((24, 10, 10), (90, 40, 34)),
                ((14, 14, 10), (70, 70, 50))]
    lo, hi = palettes[idx % 4]
    bg = _rgb(np.clip(n * 0.7 + (1 - y / h) * 0.3, 0, 1), lo, hi)
    img = Image.fromarray(bg.astype(np.uint8))
    d = ImageDraw.Draw(img)
    kind = idx % 8
    skin = (150, 132, 112)
    if kind in (0, 3, 6):          # faceless portrait
        d.ellipse([w * 0.18, h * 0.62, w * 0.82, h * 1.25], fill=(18, 16, 16))       # shoulders
        d.rectangle([w * 0.42, h * 0.48, w * 0.58, h * 0.66], fill=tuple(int(c * 0.8) for c in skin))
        d.ellipse([w * 0.3, h * 0.18, w * 0.7, h * 0.58], fill=skin)                 # blank face
        d.chord([w * 0.27, h * 0.12, w * 0.73, h * 0.46], 180, 360, fill=(26, 20, 16))  # hair
        if kind == 6:
            d.rectangle([w * 0.3, h * 0.32, w * 0.7, h * 0.38], fill=(20, 12, 12))    # blindfold
    elif kind in (1, 4):           # the mansion at night
        d.ellipse([w * 0.66, h * 0.1, w * 0.84, h * 0.24], fill=(190, 190, 170))
        d.rectangle([w * 0.15, h * 0.45, w * 0.85, h * 0.85], fill=(16, 18, 18))
        d.polygon([(w * 0.1, h * 0.46), (w * 0.5, h * 0.28), (w * 0.9, h * 0.46)], fill=(10, 12, 12))
        for i in range(5):
            c = (150, 120, 60) if i in (1, 4) else (20, 22, 24)
            d.rectangle([w * (0.2 + i * 0.13), h * 0.55, w * (0.27 + i * 0.13), h * 0.64], fill=c)
        d.rectangle([w * 0.47, h * 0.7, w * 0.53, h * 0.85], fill=(6, 6, 6))
        d.rectangle([w * 0.495, h * 0.74, w * 0.51, h * 0.84], fill=(4, 4, 4))           # a figure in the door
    elif kind in (2, 5):           # a door, ajar
        d.rectangle([w * 0.3, h * 0.15, w * 0.7, h * 0.92], fill=(40, 28, 18))
        d.polygon([(w * 0.3, h * 0.15), (w * 0.44, h * 0.2), (w * 0.44, h * 0.88), (w * 0.3, h * 0.92)], fill=(0, 0, 0))
    else:                          # the garden, a lone figure far away
        d.rectangle([0, h * 0.6, w, h], fill=(18, 26, 16))
        for i in range(6):
            cx = w * (0.1 + i * 0.16)
            d.ellipse([cx - 22, h * 0.36, cx + 22, h * 0.64], fill=(12, 20, 12))
        d.rectangle([w * 0.49, h * 0.55, w * 0.51, h * 0.66], fill=(2, 2, 2))
        d.ellipse([w * 0.485, h * 0.52, w * 0.515, h * 0.565], fill=(2, 2, 2))
    img = img.filter(ImageFilter.GaussianBlur(1.1))
    arr = np.array(img).astype(float)
    crack = fbm(TEX, 0.7, rng)[:h, :w]
    arr *= (0.8 + 0.25 * crack[..., None])
    varnish = np.array([1.08, 1.0, 0.78])        # yellowed varnish
    return arr * varnish


def decal_stain(rng) -> np.ndarray:
    n = fbm(256, 1.8, rng)
    y, x = np.mgrid[0:256, 0:256].astype(float) / 256 - 0.5
    r = np.sqrt(x ** 2 + y ** 2)
    a = np.clip((0.42 - r) * 4 + (n - 0.5) * 1.8, 0, 1)
    a = np.clip(a * 1.6, 0, 1) * 0.85
    rgb = _rgb(n, (28, 4, 4), (70, 12, 10))
    return np.dstack([rgb, a * 255])


def _font(size: int):
    for name in ("seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def decal_writing(text: str, rng) -> np.ndarray:
    w, h = 1024, 256
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    font = _font(84)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    scale = min(1.0, (w - 60) / max(tw, 1))
    if scale < 1.0:
        font = _font(int(84 * scale))
        bbox = d.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((w - tw) / 2 - bbox[0], (h - th) / 2 - bbox[1]), text, fill=255, font=font)
    a = np.array(img).astype(float) / 255
    # wobble each column so it looks hand-smeared
    wob = (np.sin(np.arange(w) / 37.0) * 4 + np.sin(np.arange(w) / 11.0) * 2).astype(int)
    a = np.stack([np.roll(a[:, i], wob[i]) for i in range(w)], axis=1)
    drips = np.zeros_like(a)
    rnd = np.random.default_rng(int(rng.integers(1e9)))
    for cx in rnd.choice(np.where(a.max(0) > 0.5)[0], size=18, replace=False):
        top = int(np.argmax(a[:, cx] > 0.5))
        L = int(rnd.uniform(15, 70))
        drips[top: min(h, top + L), max(0, cx - 1): cx + 2] = np.linspace(0.9, 0, min(h, top + L) - top)[:, None]
    a = np.clip(np.maximum(a, drips), 0, 1)
    a = np.array(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.3))).astype(float)
    n = fbm(256, 1.3, rng)
    tone = np.array(Image.fromarray((n * 255).astype(np.uint8)).resize((w, h))).astype(float) / 255
    rgb = _rgb(tone, (40, 4, 4), (96, 14, 12))
    return np.dstack([rgb, a * 0.92])


def sky(rng) -> np.ndarray:
    w, h = 1024, 512
    y = np.linspace(0, 1, h)[:, None] * np.ones((1, w))
    n = np.array(Image.fromarray((fbm(TEX, 1.6, rng) * 255).astype(np.uint8)).resize((w, h))) / 255.0
    # v=0 (image top) is the zenith, the horizon sits at the middle row
    horizon = np.exp(-np.abs(y - 0.5) * 7.0)
    grad = _rgb(horizon, (2, 4, 6), (26, 34, 38))
    clouds = np.clip((n - 0.45) * 2.2, 0, 1) * np.clip(1 - np.abs(y - 0.3) * 3, 0, 1)
    rgb = grad * (1 - clouds[..., None] * 0.6) + np.array([30, 36, 38]) * clouds[..., None] * 0.6
    rnd = np.random.default_rng(int(rng.integers(1e9)))
    for _ in range(900):
        sx, sy = rnd.integers(0, w), rnd.integers(0, int(h * 0.47))
        b = rnd.uniform(60, 220) * (1 - clouds[sy, sx])
        rgb[sy, sx] = np.maximum(rgb[sy, sx], b)
    return rgb


def moon_tex(rng) -> np.ndarray:
    s = 256
    y, x = np.mgrid[0:s, 0:s].astype(float) / s - 0.5
    r = np.sqrt(x ** 2 + y ** 2)
    n = fbm(s, 1.7, rng)
    disc = np.clip((0.48 - r) * 80, 0, 1)
    glow = np.clip(1 - r * 2, 0, 1) ** 3 * 0.35
    rgb = _rgb(n, (150, 154, 146), (228, 230, 220))
    a = np.maximum(disc, glow)
    return np.dstack([rgb * np.maximum(disc, 0.8)[..., None], a * 255])


def vignette() -> np.ndarray:
    s = 512
    y, x = np.mgrid[0:s, 0:s].astype(float) / s - 0.5
    r = np.sqrt((x * 1.1) ** 2 + y ** 2)
    a = np.clip((r - 0.28) * 2.6, 0, 1) ** 1.6
    return np.dstack([np.zeros((s, s, 3)), a * 235])


def grain(rng) -> np.ndarray:
    s = 256
    v = rng.normal(128, 60, (s, s))
    return np.dstack([v, v, v, np.full((s, s), 20.0)])


def scanlines() -> np.ndarray:
    s = 256
    rows = (np.arange(s) % 4 < 1).astype(float)[:, None] * np.ones((1, s))
    return np.dstack([np.zeros((s, s, 3)), rows * 26])


def radial_glow() -> np.ndarray:
    s = 128
    y, x = np.mgrid[0:s, 0:s].astype(float) / s - 0.5
    a = np.clip(1 - np.sqrt(x ** 2 + y ** 2) * 2, 0, 1) ** 2.2
    return np.dstack([np.full((s, s, 3), 255.0), a * 255])


# ==========================================================================
# Audio — 16-bit mono WAV
# ==========================================================================
SR = 44100


def _write_wav(path: str, samples: np.ndarray, sr: int = SR):
    s = np.clip(samples, -1, 1)
    data = (s * 32000).astype("<i2").tobytes()
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data)


def _t(seconds):
    return np.arange(int(SR * seconds)) / SR


def _lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    f = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    f *= 1 / (1 + (freqs / cutoff) ** 4)
    return np.fft.irfft(f, len(x))


def _bandpass(x, lo, hi):
    f = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    f *= np.exp(-((np.log(np.maximum(freqs, 1)) - np.log((lo * hi) ** 0.5)) ** 2) / (2 * (np.log(hi / lo) / 2) ** 2))
    return np.fft.irfft(f, len(x))


def _norm(x, peak=0.9):
    return x / (np.max(np.abs(x)) + 1e-9) * peak


def _loopable(x: np.ndarray, fade: float = 0.5) -> np.ndarray:
    n = int(SR * fade)
    head, body = x[:n], x[n:]
    ramp = np.linspace(0, 1, n)
    body[-n:] = body[-n:] * (1 - ramp) + head * ramp
    return body


def _env(n, attack, release):
    e = np.ones(n)
    a, r = int(SR * attack), int(SR * release)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r) ** 2
    return e


def make_sounds(rng, out: str):
    # Fluorescent hum — UK mains 50 Hz, integer cycles so it loops cleanly
    t = _t(4.0)
    hum = sum(np.sin(math.tau * 50 * k * t) / k ** 1.3 for k in range(1, 9))
    hum += 0.08 * _bandpass(rng.standard_normal(len(t)), 2000, 6000) * (0.6 + 0.4 * np.sin(math.tau * 100 * t))
    _write_wav(os.path.join(out, "hum_loop.wav"), _norm(hum, 0.5))

    # Garden wind — shaped noise with slow gusts
    t = _t(12.5)
    noise = _lowpass(rng.standard_normal(len(t)), 700)
    gust = 0.55 + 0.45 * np.sin(math.tau * t / 6.0) * np.sin(math.tau * t / 2.3 + 1)
    whistle = 0.05 * np.sin(math.tau * (620 + 40 * np.sin(math.tau * t / 3)) * t) * np.clip(gust - 0.6, 0, 1)
    _write_wav(os.path.join(out, "wind_loop.wav"), _norm(_loopable(noise * gust + whistle), 0.6))

    # Low dread drone — detuned sines + filtered rumble
    t = _t(12.5)
    drone = (np.sin(math.tau * 43.65 * t) + 0.7 * np.sin(math.tau * 44.1 * t) +
             0.35 * np.sin(math.tau * 65.4 * t + np.sin(math.tau * 0.15 * t) * 2) +
             0.2 * np.sin(math.tau * 92.5 * t))
    drone += 0.6 * _lowpass(rng.standard_normal(len(t)), 90)
    _write_wav(os.path.join(out, "drone_loop.wav"), _norm(_loopable(drone), 0.55))

    # Heartbeat loop (~70 bpm lub-dub)
    t = _t(0.86)
    hb = np.zeros_like(t)
    for start, amp in ((0.0, 1.0), (0.2, 0.7)):
        tt = t - start
        m = tt >= 0
        hb[m] += amp * np.sin(math.tau * 48 * tt[m]) * np.exp(-tt[m] * 18)
    _write_wav(os.path.join(out, "heartbeat_loop.wav"), _norm(hb, 0.9))

    # Walker presence — slow, wet breathing
    t = _t(4.0)
    br = _bandpass(rng.standard_normal(len(t)), 250, 1400)
    breath_env = np.clip(np.sin(math.tau * t / 4.0), 0, 1) ** 1.5 + 0.6 * np.clip(-np.sin(math.tau * t / 4.0), 0, 1) ** 2
    _write_wav(os.path.join(out, "breath_loop.wav"), _norm(br * breath_env, 0.7))

    # Clock tick loop (1 s)
    t = _t(1.0)
    tick = np.zeros_like(t)
    for s0, f in ((0.0, 2400), (0.5, 1900)):
        tt = t - s0
        m = (tt >= 0) & (tt < 0.05)
        tick[m] += np.sin(math.tau * f * tt[m]) * np.exp(-tt[m] * 160)
    _write_wav(os.path.join(out, "tick_loop.wav"), _norm(tick, 0.5))

    # Stinger — dissonant cluster that swells and cuts
    t = _t(2.6)
    freqs = [220, 233.1, 246.9, 311.1, 329.6, 440 * 1.06]
    st = sum(np.sin(math.tau * f * t + rng.uniform(0, 6)) for f in freqs)
    st += 0.8 * _bandpass(rng.standard_normal(len(t)), 800, 5000)
    st *= _env(len(t), 0.02, 1.8) * (1 + 0.5 * np.sin(math.tau * 7 * t))
    low = np.sin(math.tau * 36 * t) * np.exp(-t * 1.2) * 1.4
    _write_wav(os.path.join(out, "sting.wav"), _norm(st + low, 0.95))

    # Caught — a rising scream of noise into silence
    t = _t(1.8)
    sweep = np.sin(math.tau * (120 + 900 * t ** 2) * t)
    ca = sweep * 0.7 + _bandpass(rng.standard_normal(len(t)), 400, 6000) * (t / 1.8)
    ca *= _env(len(t), 0.01, 0.05)
    _write_wav(os.path.join(out, "caught.wav"), _norm(ca, 0.95))

    # Key pickup — detuned music-box
    t = _t(2.2)
    kk = np.zeros_like(t)
    for i, f in enumerate((1318.5, 987.8, 1174.7, 880.0 * 0.985)):
        tt = t - i * 0.16
        m = tt >= 0
        kk[m] += np.sin(math.tau * f * tt[m]) * np.exp(-tt[m] * 3.5) + 0.3 * np.sin(math.tau * f * 2.01 * tt[m]) * np.exp(-tt[m] * 6)
    _write_wav(os.path.join(out, "key.wav"), _norm(kk, 0.7))

    # Shift — reversed swell (the house moving)
    t = _t(2.0)
    sw = _lowpass(rng.standard_normal(len(t)), 400) * (t / 2.0) ** 3
    sw += 0.5 * np.sin(math.tau * 55 * t) * (t / 2.0) ** 2
    sw *= _env(len(t), 0.0, 0.08)
    _write_wav(os.path.join(out, "shift.wav"), _norm(sw, 0.8))

    # Floorboard creak
    t = _t(0.9)
    f0 = 180 + 90 * np.sin(math.tau * 1.3 * t)
    phase = np.cumsum(math.tau * f0 / SR)
    cr = np.sign(np.sin(phase)) * 0.4 + np.sin(phase * 2.01) * 0.3
    cr = _bandpass(cr, 250, 2500) * _env(len(t), 0.08, 0.3)
    _write_wav(os.path.join(out, "creak.wav"), _norm(cr, 0.6))

    # Footsteps: wood, marble, grass
    for name, (lo, hi, dec, n_var) in {"step_wood": (80, 900, 38, 3), "step_stone": (300, 4000, 55, 3),
                                        "step_grass": (600, 6000, 25, 3)}.items():
        for v in range(n_var):
            t = _t(0.3)
            s = _bandpass(rng.standard_normal(len(t)), lo, hi) * np.exp(-t * dec)
            if name != "step_grass":
                s += 0.8 * np.sin(math.tau * (70 + v * 8) * t) * np.exp(-t * 45)
            _write_wav(os.path.join(out, f"{name}_{v}.wav"), _norm(s, 0.55))

    # Locked door rattle
    t = _t(0.7)
    rat = np.zeros_like(t)
    for s0 in (0.0, 0.12, 0.21, 0.38):
        tt = t - s0
        m = tt >= 0
        rat[m] += _bandpass(rng.standard_normal(m.sum()), 500, 3000) * np.exp(-tt[m] * 30)
        rat[m] += 0.5 * np.sin(math.tau * 140 * tt[m]) * np.exp(-tt[m] * 40)
    _write_wav(os.path.join(out, "locked.wav"), _norm(rat, 0.7))

    # Water pouring
    t = _t(2.4)
    w = _bandpass(rng.standard_normal(len(t)), 700, 5000) * (0.7 + 0.3 * np.sin(math.tau * 9 * t))
    w *= _env(len(t), 0.2, 0.6)
    _write_wav(os.path.join(out, "water.wav"), _norm(w, 0.5))

    # Paper
    t = _t(0.5)
    p = _bandpass(rng.standard_normal(len(t)), 2000, 9000) * np.abs(np.sin(math.tau * 6 * t)) * _env(len(t), 0.02, 0.2)
    _write_wav(os.path.join(out, "paper.wav"), _norm(p, 0.45))

    # Front door opening — deep groan
    t = _t(3.0)
    f0 = 70 + 30 * t
    phase = np.cumsum(math.tau * f0 / SR)
    dg = _bandpass(np.sign(np.sin(phase)) * 0.5 + rng.standard_normal(len(t)) * 0.1, 80, 1200)
    dg *= _env(len(t), 0.3, 1.0)
    _write_wav(os.path.join(out, "door_open.wav"), _norm(dg, 0.8))

    # Flashlight click
    t = _t(0.08)
    c = rng.standard_normal(len(t)) * np.exp(-t * 180)
    _write_wav(os.path.join(out, "click.wav"), _norm(c, 0.5))


# ==========================================================================
def generate_all(out_dir: str, force: bool = False, progress=None) -> str:
    """Build every asset into out_dir. Returns out_dir. Skips if up to date."""
    stamp = os.path.join(out_dir, "VERSION")
    if not force and os.path.exists(stamp) and open(stamp).read().strip() == ASSET_VERSION:
        return out_dir
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(1790)
    steps = len(SURFACES) + 8
    done = 0

    def tick(msg):
        nonlocal done
        done += 1
        if progress:
            progress(done / steps, msg)

    for name, (fn, strength) in SURFACES.items():
        rgb, h = fn(rng)
        _save_rgb(rgb, os.path.join(out_dir, f"{name}.png"))
        _save_rgb(normal_from_height(h, strength), os.path.join(out_dir, f"{name}_n.png"))
        tick(name)
    for i in range(8):
        _save_rgb(painting(i, rng), os.path.join(out_dir, f"painting_{i}.png"))
    tick("paintings")
    for i in range(3):
        _save_rgba(decal_stain(rng), os.path.join(out_dir, f"stain_{i}.png"))
    from .rooms_data import NIGHT_WRITING
    for i, text in enumerate(NIGHT_WRITING):
        _save_rgba(decal_writing(text, rng), os.path.join(out_dir, f"writing_{i}.png"))
    tick("decals")
    _save_rgb(sky(rng), os.path.join(out_dir, "sky.png"))
    _save_rgba(moon_tex(rng), os.path.join(out_dir, "moon.png"))
    tick("sky")
    _save_rgba(vignette(), os.path.join(out_dir, "vignette.png"))
    for i in range(4):
        _save_rgba(grain(rng), os.path.join(out_dir, f"grain_{i}.png"))
    _save_rgba(scanlines(), os.path.join(out_dir, "scanlines.png"))
    _save_rgba(radial_glow(), os.path.join(out_dir, "glow.png"))
    tick("overlays")
    make_sounds(rng, out_dir)
    tick("audio")
    with open(stamp, "w") as f:
        f.write(ASSET_VERSION)
    return out_dir
