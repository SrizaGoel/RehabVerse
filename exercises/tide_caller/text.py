"""Custom TTF text rendering for Tide Caller, composited onto cv2 (BGR,
numpy) frames via PIL. Mirrors Black Hole Surgeon's font system: Orbitron
for all UI text, NotoSans variants available for non-Latin scripts if the
multilingual system is ever turned on.

Everything funnels through draw_text() - a drop-in for cv2.putText that
looks up (x, y) as the text's top-left baseline-ish anchor the same way
cv2.putText does, but renders with real anti-aliasing, stroke/outline
support, and correct glyph shapes instead of cv2's blocky Hershey font.

Design goal (same as audio.py / session_log.py): a missing or unreadable
font file must never crash the game. If a TTF can't be loaded, draw_text
falls back to cv2.putText so the game stays fully playable.
"""

from __future__ import annotations

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

# Single UI font family (Goldman - chunky, geometric, badge-like) with one
# static file per weight. Goldman only ships Regular + Bold, so Medium falls
# back to Regular and Black falls back to Bold (the heaviest available).
# Static files are more reliable than variable-font axis selection (no risk
# of a named instance not matching), so this is the primary font path;
# NotoSans variable fonts remain available below for non-Latin scripts if
# the multilingual system is ever turned on.
UI_FONT_FILES = {
    "Regular": "Goldman-Regular.ttf",
    "Medium": "Goldman-Regular.ttf",
    "Bold": "Goldman-Bold.ttf",
    "Black": "Goldman-Bold.ttf",
}
DEFAULT_FONT = "ui_font"

NOTO_DEVANAGARI = "NotoSansDevanagariVariableFont_wdth,wght.ttf"
NOTO_GURMUKHI = "NotoSansGurmukhiVariableFont_wdth,wght.ttf"
NOTO_BENGALI = "NotoSansBengaliVariableFont_wdth,wght.ttf"
NOTO_TELUGU = "NotoSansTeluguVariableFont_wdth,wght.ttf"

_font_cache: dict[tuple, ImageFont.FreeTypeFont] = {}


def _load_font(font_file: str, size: int, weight: str = "Regular"):
    """Load (and cache) a TTF at a given pixel size + weight. font_file may
    be a literal filename (any font) or the special value 'quicksand', which
    resolves to the correct static weight file automatically. Returns None
    if the file can't be found/read - callers fall back to cv2.putText."""
    resolved_file = UI_FONT_FILES.get(weight, UI_FONT_FILES["Regular"]) \
        if font_file == DEFAULT_FONT else font_file
    key = (resolved_file, size)
    if key in _font_cache:
        return _font_cache[key]

    path = os.path.join(_FONTS_DIR, resolved_file)
    try:
        font = ImageFont.truetype(path, size)
    except Exception:
        _font_cache[key] = None
        return None

    _font_cache[key] = font
    return font


def measure_text(text: str, font_file: str = DEFAULT_FONT, size: int = 24,
                  weight: str = "Regular") -> tuple:
    """(width, height) of text at this font/size, for layout/centering.
    Falls back to cv2's Hershey metrics if the TTF isn't available, so
    callers can always trust the returned size for positioning."""
    font = _load_font(font_file, size, weight)
    if font is None:
        (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, size / 32, 1)
        return w, h
    tmp = Image.new("L", (1, 1))
    bbox = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_text(frame, text: str, pos: tuple, size: int = 24,
              color_bgr: tuple = (255, 255, 255), *, font_file: str = DEFAULT_FONT,
              weight: str = "Regular", align: str = "left",
              stroke_width: int = 0, stroke_color_bgr: tuple = (0, 0, 0),
              glow: bool = False, glow_color_bgr: tuple = None,
              glow_strength: float = 0.8) -> None:
    """Draw anti-aliased TTF text onto a cv2 BGR frame in place.

    pos is (x, y) - x follows `align`; y is the text's top edge (unlike
    cv2.putText's baseline-based y, which made precise vertical stacking
    fiddly). Falls back to cv2.putText automatically if the font can't be
    loaded, so a missing/renamed font file never breaks a screen.

    glow=True adds a soft blurred colored halo behind the text (a real
    neon-style glow, not just a flat fill) - defaults to glowing the same
    color as the text itself.
    """
    font = _load_font(font_file, size, weight)
    if font is None:
        _fallback_puttext(frame, text, pos, size, color_bgr, align)
        return

    tmp = Image.new("L", (1, 1))
    bbox = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=font,
                                         stroke_width=stroke_width)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    glow_radius = max(4, size // 6) if glow else 0
    pad = stroke_width + 2 + int(glow_radius * 2.4)
    patch_w, patch_h = tw + pad * 2, th + pad * 2

    x, y = pos
    if align == "center":
        x -= tw // 2
    elif align == "right":
        x -= tw

    patch = Image.new("RGBA", (patch_w, patch_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(patch)
    rgb_color = (color_bgr[2], color_bgr[1], color_bgr[0])
    rgb_stroke = (stroke_color_bgr[2], stroke_color_bgr[1], stroke_color_bgr[0])
    draw.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=(*rgb_color, 255),
              stroke_width=stroke_width, stroke_fill=(*rgb_stroke, 255))

    if glow:
        _add_glow(frame, patch, x - pad, y - pad, glow_color_bgr or color_bgr,
                  blur_radius=glow_radius, intensity=glow_strength)

    _composite(frame, patch, x - pad, y - pad)


def draw_gradient_text(frame, text: str, pos: tuple, size: int = 32,
                        top_color_bgr: tuple = (255, 250, 235),
                        bottom_color_bgr: tuple = (40, 140, 220), *,
                        font_file: str = DEFAULT_FONT, weight: str = "Black",
                        align: str = "center", stroke_width: int = 2,
                        stroke_color_bgr: tuple = (20, 20, 20),
                        glow: bool = True, glow_color_bgr: tuple = None,
                        glow_strength: float = 0.9) -> None:
    """Hero/title text with a vertical color gradient inside the glyph
    shapes (icy highlight -> deep color), mirroring Black Hole Surgeon's
    metallic title effect. glow=True (default for titles) adds a soft
    blurred halo so the title reads as genuinely glowing, not flat-filled.
    Falls back to flat draw_text if the font or a gradient composite isn't
    available."""
    font = _load_font(font_file, size, weight)
    if font is None:
        _fallback_puttext(frame, text, pos, size, top_color_bgr, align)
        return

    tmp = Image.new("L", (1, 1))
    bbox = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=font,
                                         stroke_width=stroke_width)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    glow_radius = max(6, size // 4) if glow else 0
    pad = stroke_width + 2 + int(glow_radius * 2.4)
    patch_w, patch_h = tw + pad * 2, th + pad * 2

    x, y = pos
    if align == "center":
        x -= tw // 2
    elif align == "right":
        x -= tw

    # 1. glyph mask (alpha only, white fill) so we know exactly which
    #    pixels belong to the text.
    mask = Image.new("L", (patch_w, patch_h), 0)
    ImageDraw.Draw(mask).text((pad - bbox[0], pad - bbox[1]), text, font=font,
                               fill=255)

    # 2. vertical gradient the same size as the patch - a non-linear curve
    #    concentrates the bright highlight near the top third (a "shine
    #    band") instead of a flat linear fade, reading as polished metal
    #    rather than a plain top-to-bottom blend.
    top = np.array([top_color_bgr[2], top_color_bgr[1], top_color_bgr[0]], dtype=float)
    bottom = np.array([bottom_color_bgr[2], bottom_color_bgr[1], bottom_color_bgr[0]], dtype=float)
    t = np.linspace(0, 1, patch_h)
    shine_curve = t ** 1.6  # slower rise near the top = wider bright band
    grad = shine_curve.reshape(-1, 1, 1)
    grad_rgb = (top * (1 - grad) + bottom * grad).astype(np.uint8)
    grad_rgb = np.repeat(grad_rgb, patch_w, axis=1)
    gradient_img = Image.fromarray(grad_rgb, mode="RGB").convert("RGBA")
    gradient_img.putalpha(mask)

    # 3. stroke, drawn separately underneath so the gradient fill sits on top.
    if stroke_width > 0:
        stroke_layer = Image.new("RGBA", (patch_w, patch_h), (0, 0, 0, 0))
        rgb_stroke = (stroke_color_bgr[2], stroke_color_bgr[1], stroke_color_bgr[0])
        ImageDraw.Draw(stroke_layer).text(
            (pad - bbox[0], pad - bbox[1]), text, font=font,
            fill=(0, 0, 0, 0), stroke_width=stroke_width,
            stroke_fill=(*rgb_stroke, 255))
        stroke_layer.alpha_composite(gradient_img)
        final_patch = stroke_layer
    else:
        final_patch = gradient_img

    if glow:
        halo_color = glow_color_bgr or bottom_color_bgr
        _add_glow(frame, final_patch, x - pad, y - pad, halo_color,
                  blur_radius=glow_radius, intensity=glow_strength)

    _composite(frame, final_patch, x - pad, y - pad)


# ------------------------------------------------------------------
# INTERNAL HELPERS
# ------------------------------------------------------------------
def _add_glow(frame, patch_rgba: Image.Image, x: int, y: int, color_bgr: tuple,
              blur_radius: int, intensity: float = 0.8) -> None:
    """Composite a soft blurred colored glow of patch_rgba's shape onto
    frame at (x,y), meant to be called BEFORE the sharp patch itself is
    composited on top. Layers multiple blur passes at different radii
    (wide+faint -> narrow+bright) for a true radiant falloff instead of a
    single flat blur - the same technique used for panel border glow."""
    alpha = patch_rgba.split()[-1]
    rgb = (color_bgr[2], color_bgr[1], color_bgr[0])
    glow_rgb_img = Image.new("RGB", patch_rgba.size, rgb)

    layers = [
        (blur_radius * 2.2, intensity * 0.35),
        (blur_radius * 1.3, intensity * 0.55),
        (blur_radius * 0.7, intensity * 0.85),
    ]
    for radius, layer_intensity in layers:
        blurred = alpha.filter(ImageFilter.GaussianBlur(radius))
        blurred = blurred.point(lambda p, li=layer_intensity: int(min(255, p * li)))
        glow_rgba = Image.merge("RGBA", (*glow_rgb_img.split(), blurred))
        _composite(frame, glow_rgba, x, y)


def _composite(frame, patch_rgba: Image.Image, x: int, y: int) -> None:
    """Alpha-composite a PIL RGBA patch onto a cv2 BGR numpy frame at (x,y),
    clipping to the frame bounds so partially off-screen text never errors."""
    h, w = frame.shape[:2]
    pw, ph = patch_rgba.size

    src_x0, src_y0 = 0, 0
    dst_x0, dst_y0 = x, y
    if dst_x0 < 0:
        src_x0 = -dst_x0
        dst_x0 = 0
    if dst_y0 < 0:
        src_y0 = -dst_y0
        dst_y0 = 0
    dst_x1 = min(w, x + pw)
    dst_y1 = min(h, y + ph)
    if dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
        return  # fully off-screen

    src_x1 = src_x0 + (dst_x1 - dst_x0)
    src_y1 = src_y0 + (dst_y1 - dst_y0)

    patch_np = np.array(patch_rgba)  # H, W, RGBA
    region = patch_np[src_y0:src_y1, src_x0:src_x1]
    if region.size == 0:
        return

    rgb = region[:, :, :3][:, :, ::-1]  # RGB -> BGR
    alpha = region[:, :, 3:4].astype(float) / 255.0

    dst = frame[dst_y0:dst_y1, dst_x0:dst_x1].astype(float)
    blended = rgb.astype(float) * alpha + dst * (1 - alpha)
    frame[dst_y0:dst_y1, dst_x0:dst_x1] = blended.astype(np.uint8)


def _fallback_puttext(frame, text, pos, size, color_bgr, align) -> None:
    """cv2.putText fallback if a TTF can't be loaded for any reason."""
    scale = max(0.3, size / 32)
    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_DUPLEX, scale, 1)
    x, y = pos
    if align == "center":
        x -= tw // 2
    elif align == "right":
        x -= tw
    cv2.putText(frame, text, (x, y + size), cv2.FONT_HERSHEY_DUPLEX,
                scale, color_bgr, 1)
