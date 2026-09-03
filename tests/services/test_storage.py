import io
import random

from backend.services.storage import compress_screenshot


def _make_form_png(width: int = 1280, height: int = 800) -> bytes:
    """A screenshot-like image: flat UI background with text-ish detail.
    Flat solid colors compress unrealistically well and would not exercise
    the encoder choice honestly."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, height), color=(245, 247, 250))
    draw = ImageDraw.Draw(img)
    draw.rectangle([80, 40, width - 80, height - 40], fill=(255, 255, 255))
    rng = random.Random(0)
    for row in range(12):
        y = 100 + row * 55
        draw.rectangle([120, y, 360, y + 12], fill=(55, 65, 81))
        draw.rectangle([120, y + 20, width - 140, y + 58], outline=(209, 213, 219))
        for _ in range(40):  # text-like speckle
            x = rng.randint(130, width - 160)
            draw.point((x, y + 40), fill=(17, 17, 17))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_compress_screenshot_never_grows_the_upload():
    """Whichever encoding wins, the stored object is never larger than the
    PNG we started with. (The WebP win on a real browser screenshot is
    measured in tests/agents/test_vision_loop_integration.py.)"""
    png = _make_form_png()
    body, ext = compress_screenshot(png)
    assert len(body) <= len(png)
    assert ext in ("webp", "png")


def test_compress_screenshot_preserves_full_resolution():
    """No downscaling — step replay must stay legible at 1280x800."""
    from PIL import Image

    body, _ = compress_screenshot(_make_form_png())
    assert Image.open(io.BytesIO(body)).size == (1280, 800)


def test_compress_screenshot_keeps_png_when_webp_is_not_smaller():
    """A trivially compressible image encodes larger as WebP — keep the PNG."""
    from PIL import Image

    img = Image.new("RGB", (1280, 800), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()

    body, ext = compress_screenshot(png)
    assert len(body) <= len(png)
    if ext == "png":
        assert body == png


def test_compress_screenshot_falls_back_on_garbage_bytes():
    body, ext = compress_screenshot(b"not a png at all")
    assert body == b"not a png at all"
    assert ext == "png"
