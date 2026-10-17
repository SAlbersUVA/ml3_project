import base64
import io
import json
import sqlite3

import numpy as np
from PIL import Image

MAX_FG_POINTS = 2000
DOWNSCALE = 4  # 1200 x 1200 becomes 300 x 300. Use 1 for no shrinking.


def normalize(arr):
    """Scale one plane to 0..1, ignoring the very darkest and brightest pixels."""
    arr = arr.astype(np.float32)
    lo, hi = np.percentile(arr, [1, 99.5])
    if hi <= lo:
        hi = lo + 1
    return np.clip((arr - lo) / (hi - lo), 0, 1)


def shrink(arr, factor):
    """Shrink a 2D array by averaging each factor x factor block into one pixel."""
    if factor == 1:
        return arr.astype(np.float32)
    h = arr.shape[0] // factor * factor   # drop leftover rows/columns if the size
    w = arr.shape[1] // factor * factor   # isn't an exact multiple of factor
    blocks = arr[:h, :w].astype(np.float32).reshape(h // factor, factor, w // factor, factor)
    return blocks.mean(axis=(1, 3))


def grow(arr, factor, out_shape):
    """Blow a small array back up to the original size (each pixel becomes a factor x factor block)."""
    big = np.repeat(np.repeat(arr, factor, axis=0), factor, axis=1)
    out = np.zeros(out_shape, dtype=big.dtype)
    h, w = min(out_shape[0], big.shape[0]), min(out_shape[1], big.shape[1])
    out[:h, :w] = big[:h, :w]
    return out


def make_sample(img, mask, source, factor=DOWNSCALE):
    """Shrink one plane and its mask, then bundle them into the form the trainer uses."""
    small_img = shrink(img, factor)
    small_mask = (shrink((mask > 0).astype(np.float32), factor) >= 0.5).astype(np.uint8)

    ys, xs = np.nonzero(small_mask)
    if len(ys) > MAX_FG_POINTS:
        keep = np.random.choice(len(ys), MAX_FG_POINTS, replace=False)
        ys, xs = ys[keep], xs[keep]
    return {
        "img": normalize(small_img).astype(np.float16),
        "mask": small_mask,
        "fg": (ys, xs),
        "source": source,
    }


def decode_alpha_mask(data_url):
    """A painted layer is a transparent PNG; any pixel with alpha > 0 is painted."""
    _, encoded = data_url.split(",", 1)
    img = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGBA")
    return np.array(img)[:, :, 3] > 0


def collect_annotation_samples(db_path, load_volume, layer_ids=None, factor=DOWNSCALE, filename=None):
    """One sample per plane that has painting on the chosen layers (all layers if none given).
    If filename is given, only that image's planes are used.
    Unpainted planes are skipped, because 'nothing painted' does not mean 'nothing there'."""
    samples = []
    conn = sqlite3.connect(db_path)
    if filename:
        rows = conn.execute(
            "SELECT filename, plane, image_data FROM annotations WHERE filename = ?", (filename,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT filename, plane, image_data FROM annotations").fetchall()
    conn.close()

    for filename, plane, image_data in rows:
        try:
            layers = json.loads(image_data)
        except (json.JSONDecodeError, TypeError):
            continue

        union = None
        for lid in (layer_ids or list(layers.keys())):
            url = layers.get(lid)
            if not url:
                continue
            m = decode_alpha_mask(url)
            union = m if union is None else (union | m if m.shape == union.shape else union)

        if union is None or not union.any():
            continue

        try:
            vol = load_volume(filename)
        except Exception as e:
            print(f"Could not load {filename}: {e}")
            continue
        if plane >= vol.shape[0] or vol[plane].shape != union.shape:
            continue

        sample = make_sample(vol[plane], union, "annotation", factor)
        sample["filename"] = filename
        sample["plane"] = plane
        samples.append(sample)
    return samples