"""Builds the data shown in the app's 'Training data' pop-up."""

import base64
import io

import numpy as np
from PIL import Image

import data


def png_url(array, mode):
    """Encode a numpy array as a PNG data URL the browser can show directly."""
    buf = io.BytesIO()
    Image.fromarray(array, mode).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def patch_strip(padded, ys, xs, patch):
    """Stack the patches for the given pixels on top of each other, 1 white pixel apart."""
    gap = np.ones((1, patch), dtype=np.float32)
    pieces = []
    for y, x in zip(ys, xs):
        pieces.append(padded[y:y + patch, x:x + patch])
        pieces.append(gap)
    if not pieces:
        return np.zeros((patch, patch), dtype=np.float32)
    return np.vstack(pieces[:-1])


def guess_outputs(guess_map, true_mask=None):
    """The network's 0..1 map, a yes/no version (>= 0.5) and, if we know the answer, its Dice score."""
    g = np.clip(guess_map, 0, 1)
    yes = g >= 0.5
    overlay = np.zeros((*g.shape, 4), dtype=np.uint8)
    overlay[yes] = [255, 140, 0, 255]
    dice = None
    if true_mask is not None:
        truth = true_mask > 0
        total = yes.sum() + truth.sum()
        dice = 1.0 if total == 0 else float(2 * (yes & truth).sum() / total)
    return png_url((g * 255).astype(np.uint8), "L"), png_url(overlay, "RGBA"), dice


def training_row(s, patch, n_patches):
    """A plane the network trains on: the image, the painting, and sampled patches. No predictions."""
    half = patch // 2
    img = s["img"].astype(np.float32)
    mask = s["mask"]
    padded = np.pad(img, half, mode="reflect")

    fg_y, fg_x = s["fg"]
    pick = np.random.choice(len(fg_y), min(n_patches, len(fg_y)), replace=False)
    py, px = fg_y[pick], fg_x[pick]
    bg_y, bg_x = np.nonzero(mask == 0)
    pick = np.random.choice(len(bg_y), min(n_patches, len(bg_y)), replace=False)
    uy, ux = bg_y[pick], bg_x[pick]

    overlay = np.zeros((*mask.shape, 4), dtype=np.uint8)
    overlay[mask > 0] = [255, 140, 0, 255]

    return {
        "filename": s["filename"],
        "plane": int(s["plane"]),
        "width": int(img.shape[1]),
        "height": int(img.shape[0]),
        "image": png_url((img * 255).astype(np.uint8), "L"),
        "mask": png_url(overlay, "RGBA"),
        # top-left corner of each sampled patch, in downsampled-image pixels
        "painted": [{"x": int(x - half), "y": int(y - half)} for y, x in zip(py, px)],
        "unpainted": [{"x": int(x - half), "y": int(y - half)} for y, x in zip(uy, ux)],
        "paintedStrip": png_url((patch_strip(padded, py, px, patch) * 255).astype(np.uint8), "L"),
        "unpaintedStrip": png_url((patch_strip(padded, uy, ux, patch) * 255).astype(np.uint8), "L"),
        "guess": None, "guessMask": None, "dice": None,
    }


def prediction_row(s, guess_fn):
    """A held-out plane: the image, your painting, the network's guess and the overlap score."""
    img = s["img"].astype(np.float32)
    mask = s["mask"]
    overlay = np.zeros((*mask.shape, 4), dtype=np.uint8)
    overlay[mask > 0] = [255, 140, 0, 255]
    guess, guess_mask, dice = guess_outputs(guess_fn(img), mask)
    return {
        "filename": s["filename"],
        "plane": int(s["plane"]),
        "width": int(img.shape[1]),
        "height": int(img.shape[0]),
        "image": png_url((img * 255).astype(np.uint8), "L"),
        "mask": png_url(overlay, "RGBA"),
        "painted": [], "unpainted": [], "paintedStrip": None, "unpaintedStrip": None,
        "guess": guess, "guessMask": guess_mask, "dice": dice,
    }


def unpainted_rows(load_volume, filename, painted_keys, guess_fn, n_planes):
    """Planes of the image that were never painted, so the network has never seen them."""
    vol = load_volume(filename)
    free = [z for z in range(vol.shape[0]) if (filename, z) not in painted_keys]
    rows = []
    for z in np.random.permutation(free)[:n_planes]:
        img = data.normalize(data.shrink(vol[int(z)], data.DOWNSCALE))
        guess, guess_mask, _ = guess_outputs(guess_fn(img))
        rows.append({
            "filename": filename,
            "plane": int(z),
            "width": int(img.shape[1]),
            "height": int(img.shape[0]),
            "image": png_url((img * 255).astype(np.uint8), "L"),
            "mask": None,
            "painted": [], "unpainted": [], "paintedStrip": None, "unpaintedStrip": None,
            "guess": guess, "guessMask": guess_mask, "dice": None,
        })
    return rows


def build_preview(db_path, load_volume, n_planes=3, n_patches=6, patch=7,
                  guess_fn=None, test_keys=(), painted_keys=(), mode=None, filename=None):
    """Returns two lists: 'planes' (training planes, no predictions) and
    'predictions' (held-out planes and never-painted planes, with the network's guesses)."""
    patch = max(3, min(31, patch)) // 2 * 2 + 1   # keep it odd, between 3 and 31

    samples = data.collect_annotation_samples(db_path, load_volume, filename=filename)
    is_held = lambda s: (s["filename"], int(s["plane"])) in test_keys

    if guess_fn is not None:
        train_samples = [s for s in samples if not is_held(s)]
        held_samples = [s for s in samples if is_held(s)]
    else:
        train_samples, held_samples = samples, []

    chosen = np.random.permutation(len(train_samples))[:n_planes]
    planes = [training_row(train_samples[int(i)], patch, n_patches) for i in chosen]

    predictions = []
    if guess_fn is not None:
        predictions = [prediction_row(s, guess_fn) for s in held_samples]
        names = [filename] if filename else sorted({f for f, _ in painted_keys})
        if names:
            predictions += unpainted_rows(load_volume, names[0], painted_keys, guess_fn, n_planes)

    return {
        "downscale": data.DOWNSCALE,
        "patchSize": patch,
        "totalPlanes": len(samples),
        "planes": planes,
        "predictions": predictions,
    }