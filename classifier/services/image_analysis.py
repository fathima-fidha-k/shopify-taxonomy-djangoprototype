import io
from urllib.parse import urlparse

import requests
from PIL import Image

REQUEST_TIMEOUT = 5  # seconds -- fail fast on a broken/slow image (Q8)

# A small named-color palette to map extracted RGB values onto the same
# controlled vocabulary used by the text-based attribute extractor, so
# image-derived and text-derived "color" values are directly comparable.
_NAMED_COLORS = {
    "white": (255, 255, 255), "black": (20, 20, 20), "gray": (128, 128, 128),
    "grey": (128, 128, 128), "beige": (222, 202, 165), "brown": (101, 67, 33),
    "walnut": (94, 63, 39), "natural": (205, 175, 130), "blue": (30, 60, 140),
    "navy": (20, 30, 80), "green": (40, 100, 60), "red": (150, 30, 30),
    "gold": (180, 150, 60), "brass": (160, 130, 70), "bronze": (120, 90, 50),
    "chrome": (190, 190, 195),
}


def _nearest_color_name(rgb):
    best_name, best_dist = None, float("inf")
    for name, ref_rgb in _NAMED_COLORS.items():
        dist = sum((a - b) ** 2 for a, b in zip(rgb, ref_rgb))
        if dist < best_dist:
            best_name, best_dist = name, dist
    return best_name


def analyze_image(image_url):
    """
    Downloads the image and extracts its dominant color.

    Returns:
        {"processed": True, "color": "gray", "rgb": (r,g,b)}   on success
        {"processed": False, "error": "..."}                    on any failure

    Never raises -- a broken/missing/unreachable image must not stop the
    batch (Q8). All failure modes (bad URL, timeout, 404, corrupt file,
    unsupported format) are caught and reported, not propagated.
    """
    if not image_url:
        return {"processed": False, "error": "no_image_url"}

    parsed = urlparse(image_url)
    if parsed.scheme not in ("http", "https"):
        return {"processed": False, "error": "invalid_url_scheme"}

    try:
        response = requests.get(image_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"processed": False, "error": f"fetch_failed: {exc.__class__.__name__}"}

    try:
        img = Image.open(io.BytesIO(response.content))
        img = img.convert("RGB")
        img.thumbnail((50, 50))  # downsample for a cheap average-color read

        pixels = list(img.getdata())
        avg_rgb = tuple(sum(channel) // len(pixels) for channel in zip(*pixels))
        color_name = _nearest_color_name(avg_rgb)

        return {"processed": True, "color": color_name, "rgb": avg_rgb}

    except Exception as exc:  # noqa: BLE001 - corrupt/unsupported image must not stop the batch
        return {"processed": False, "error": f"decode_failed: {exc.__class__.__name__}"}
