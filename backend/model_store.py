"""Saves trained models to disk and loads them back.

Each model is two files in backend/saved_models/:
  <name>.pt    the weights (and which planes were held out)
  <name>.json  a short description: model type, settings, final score, loss curve
"""

import json
import os
import re
import shutil
import time

import torch

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_models")


def safe_name(name):
    """Keep file names simple: letters, numbers, dash and underscore."""
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", name or "").strip("_") or "model"


def save(name, kind, weights, config, metric, history, test_keys, painted_keys, copy_dir=None):
    os.makedirs(SAVE_DIR, exist_ok=True)
    name = safe_name(name)
    torch.save(
        {
            "kind": kind,                          # "mlp" or "unet"
            "weights": weights,                    # MLP: [W1, b1, W2, b2]   U-Net: its state_dict
            "config": config,
            "test_keys": [list(k) for k in sorted(test_keys)],        # planes held out from training
            "painted_keys": [list(k) for k in sorted(painted_keys)],  # every plane that was painted
        },
        os.path.join(SAVE_DIR, name + ".pt"),
    )
    info = {
        "name": name,
        "kind": kind,
        "config": config,
        "metric": metric,
        "history": history,
        "saved": time.strftime("%Y-%m-%d %H:%M"),
    }
    with open(os.path.join(SAVE_DIR, name + ".json"), "w") as f:
        json.dump(info, f)

    paths = [SAVE_DIR]
    if copy_dir and os.path.isdir(copy_dir):          # also keep a copy next to the images
        extra = os.path.join(copy_dir, "saved_models")
        os.makedirs(extra, exist_ok=True)
        for ext in (".pt", ".json"):
            shutil.copy2(os.path.join(SAVE_DIR, name + ext), os.path.join(extra, name + ext))
        paths.append(extra)
    return name, paths


def weights_path(name):
    """Full path of a saved model's weights file, for downloading."""
    path = os.path.join(SAVE_DIR, safe_name(name) + ".pt")
    if not os.path.exists(path):
        raise FileNotFoundError(f"No saved model called {name}.")
    return path


def list_models():
    """Short descriptions of every saved model, newest first."""
    if not os.path.isdir(SAVE_DIR):
        return []
    models = []
    for file in os.listdir(SAVE_DIR):
        if file.endswith(".json") and os.path.exists(os.path.join(SAVE_DIR, file[:-5] + ".pt")):
            with open(os.path.join(SAVE_DIR, file)) as f:
                info = json.load(f)
            models.append({k: info[k] for k in ("name", "kind", "config", "metric", "saved")})
    return sorted(models, key=lambda m: m["saved"], reverse=True)


def load(name):
    """Returns (checkpoint, info) for a saved model."""
    name = safe_name(name)
    pt, js = os.path.join(SAVE_DIR, name + ".pt"), os.path.join(SAVE_DIR, name + ".json")
    if not (os.path.exists(pt) and os.path.exists(js)):
        raise FileNotFoundError(f"No saved model called {name}.")
    with open(js) as f:
        info = json.load(f)
    return torch.load(pt, weights_only=True), info