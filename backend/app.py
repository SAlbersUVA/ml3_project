from flask import Flask, send_file, jsonify, request
import json
from flask_cors import CORS
from SBReadFile import SBReadFile
import numpy as np
from PIL import Image
import tifffile as tiff
import io
import os
import sqlite3
import datetime
import base64
import zipfile

app = Flask(__name__)
CORS(app)

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
DEFAULT_DATA_DIR = "C:/Users/xhd6ct/Documents/research_data"  # only used until you press Set in the app


def load_saved_directory():
    """The folder you last set from the text box, if it still exists."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            path = json.load(f).get("dataDir")
        if path and os.path.isdir(path):
            return path
    except (OSError, ValueError):
        pass
    return None


DATA_DIR = load_saved_directory() or DEFAULT_DATA_DIR

SUPPORTED_EXTENSIONS = (".sldy", ".tif", ".tiff", ".png", ".jpg", ".jpeg")

histogram_cache = {}
volume_cache = {}
DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS annotations (
            filename TEXT NOT NULL,
            plane INTEGER NOT NULL,
            image_data TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (filename, plane)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS layer_defs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            color TEXT NOT NULL,
            sort_order INTEGER NOT NULL
        )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS action_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        plane INTEGER NOT NULL,
        layer_id TEXT NOT NULL,
        image_data TEXT NOT NULL,
        stack TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
""")
    conn.commit()
    conn.close()


init_db()

def get_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".sldy":
        return "sldy"
    elif ext in (".tif", ".tiff"):
        return "tiff"
    else:
        return "image"


def load_volume(filename):
    if filename in volume_cache:
        return volume_cache[filename]

    filetype = get_file_type(filename)
    path = os.path.join(DATA_DIR, filename)

    if filetype == "sldy":
        reader = SBReadFile()
        reader.Open(path)
        num_planes = reader.GetNumZPlanes(0)
        planes = []
        for p in range(num_planes):
            raw = reader.ReadImagePlaneBuf(0, 0, 0, p, 0, True)
            planes.append(np.array(raw))
        volume = np.stack(planes)

    elif filetype == "tiff":
        volume = tiff.imread(path)
        if volume.ndim == 2:
            volume = volume[np.newaxis, ...]

    else:
        img = Image.open(path).convert("L")
        volume = np.array(img)[np.newaxis, ...]

    volume_cache[filename] = volume
    return volume

def read_plane_array(filename, plane):
    volume = load_volume(filename)
    return volume[plane]



def get_num_planes(filename):
    volume = load_volume(filename)
    return volume.shape[0]


@app.route("/api/files")
def list_files():
    files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(SUPPORTED_EXTENSIONS)]
    return jsonify(files)


@app.route("/api/info/<filename>")
def file_info(filename):
    volume = load_volume(filename)
    return jsonify({
        "numPlanes": volume.shape[0],
        "height": volume.shape[1],
        "width": volume.shape[2],
    })

@app.route("/api/slice/<filename>/<axis>/<int:index>")
def get_slice(filename, axis, index):
    volume = load_volume(filename)

    if axis == "xy":
        arr = volume[index]
    elif axis == "xz":
        arr = volume[:, index, :]
    elif axis == "yz":
        arr = volume[:, :, index]
    else:
        return jsonify({"error": "invalid axis"}), 400

    arr = arr.astype(np.float32)

    black = request.args.get("min", type=float)
    white = request.args.get("max", type=float)
    if black is None:
        black = arr.min()
    if white is None:
        white = arr.max()
    if white <= black:
        white = black + 1

    arr = np.clip((arr - black) / (white - black) * 255, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.route("/api/plane/<filename>/<int:plane>")
def get_plane(filename, plane):
    arr = read_plane_array(filename, plane).astype(np.float32)

    black = request.args.get("min", type=float)
    white = request.args.get("max", type=float)
    if black is None:
        black = arr.min()
    if white is None:
        white = arr.max()
    if white <= black:
        white = black + 1

    arr = np.clip((arr - black) / (white - black) * 255, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/api/histogram/<filename>")
def get_histogram(filename):
    if filename in histogram_cache:
        return jsonify(histogram_cache[filename])

    num_planes = get_num_planes(filename)

    global_min = None
    global_max = None
    total_counts = np.zeros(256, dtype=np.int64)

    for p in range(num_planes):
        arr = read_plane_array(filename, p)
        plane_min = arr.min()
        plane_max = arr.max()
        if global_min is None or plane_min < global_min:
            global_min = plane_min
        if global_max is None or plane_max > global_max:
            global_max = plane_max

    for p in range(num_planes):
        arr = read_plane_array(filename, p)
        counts, _ = np.histogram(arr, bins=256, range=(global_min, global_max))
        total_counts += counts

    result = {
        "counts": total_counts.tolist(),
        "min": int(global_min),
        "max": int(global_max),
    }
    histogram_cache[filename] = result
    return jsonify(result)


@app.route("/api/directory", methods=["GET"])
def get_directory():
    return jsonify({"path": DATA_DIR})


@app.route("/api/directory", methods=["POST"])
def set_directory():
    global DATA_DIR
    data = request.get_json()
    new_path = data.get("path", "").strip()

    if not new_path:
        return jsonify({"error": "No path provided"}), 400
    if not os.path.isdir(new_path):
        return jsonify({"error": "That folder doesn't exist"}), 400

    DATA_DIR = new_path
    histogram_cache.clear()
    volume_cache.clear()
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump({"dataDir": DATA_DIR}, f)
    except OSError as e:
        print(f"Could not save the folder setting: {e}")
    return jsonify({"path": DATA_DIR})


@app.route("/api/annotations/<filename>/<int:plane>", methods=["GET"])
def get_annotation(filename, plane):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT image_data FROM annotations WHERE filename = ? AND plane = ?",
        (filename, plane),
    ).fetchone()
    conn.close()
    if row:
        try:
            return jsonify({"layers": json.loads(row[0])})
        except (json.JSONDecodeError, TypeError):
            return jsonify({"layers": {}})
    return jsonify({"layers": {}})


@app.route("/api/annotations/<filename>/<int:plane>", methods=["POST"])
def save_annotation(filename, plane):
    data = request.get_json(silent=True) or {}
    layers = data.get("layers", {})

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO annotations (filename, plane, image_data, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(filename, plane) DO UPDATE SET
            image_data = excluded.image_data,
            updated_at = excluded.updated_at
        """,
        (filename, plane, json.dumps(layers), datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})


@app.route("/api/layers", methods=["GET"])
def get_layers():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, name, color FROM layer_defs ORDER BY sort_order"
    ).fetchall()
    conn.close()
    layers = [{"id": r[0], "name": r[1], "color": r[2]} for r in rows]
    return jsonify({"layers": layers})


@app.route("/api/layers", methods=["POST"])
def save_layers():
    data = request.get_json(silent=True) or {}
    layers = data.get("layers", [])

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM layer_defs")
    for i, layer in enumerate(layers):
        conn.execute(
            "INSERT INTO layer_defs (id, name, color, sort_order) VALUES (?, ?, ?, ?)",
            (layer["id"], layer["name"], layer["color"], i),
        )
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})

@app.route("/api/history/<filename>/<int:plane>", methods=["POST"])
def push_history(filename, plane):
    data = request.get_json(silent=True) or {}
    layer_id = data.get("layerId")
    image = data.get("image")
    if not layer_id or not image:
        return jsonify({"error": "layerId and image required"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO action_history (filename, plane, layer_id, image_data, stack, created_at) VALUES (?, ?, ?, ?, 'undo', ?)",
        (filename, plane, layer_id, image, datetime.datetime.now().isoformat()),
    )
    conn.execute(
        "DELETE FROM action_history WHERE filename = ? AND plane = ? AND stack = 'redo'",
        (filename, plane),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "saved"})


@app.route("/api/undo/<filename>/<int:plane>", methods=["GET"])
def peek_undo(filename, plane):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, layer_id, image_data FROM action_history WHERE filename = ? AND plane = ? AND stack = 'undo' ORDER BY id DESC LIMIT 1",
        (filename, plane),
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"available": False})
    return jsonify({"available": True, "id": row[0], "layerId": row[1], "image": row[2]})


@app.route("/api/undo/<filename>/<int:plane>", methods=["POST"])
def apply_undo(filename, plane):
    data = request.get_json(silent=True) or {}
    entry_id = data.get("id")
    layer_id = data.get("layerId")
    current_image = data.get("currentImage")
    if entry_id is None or not layer_id or current_image is None:
        return jsonify({"error": "id, layerId, currentImage required"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM action_history WHERE id = ?", (entry_id,))
    conn.execute(
        "INSERT INTO action_history (filename, plane, layer_id, image_data, stack, created_at) VALUES (?, ?, ?, ?, 'redo', ?)",
        (filename, plane, layer_id, current_image, datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/redo/<filename>/<int:plane>", methods=["GET"])
def peek_redo(filename, plane):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, layer_id, image_data FROM action_history WHERE filename = ? AND plane = ? AND stack = 'redo' ORDER BY id DESC LIMIT 1",
        (filename, plane),
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"available": False})
    return jsonify({"available": True, "id": row[0], "layerId": row[1], "image": row[2]})


@app.route("/api/export/<filename>", methods=["POST"])
def export_annotations(filename):
    data = request.get_json(silent=True) or {}
    layer_ids = data.get("layerIds", [])
    layer_names = data.get("layerNames", {})

    if not layer_ids:
        return jsonify({"error": "No layers provided"}), 400

    volume = load_volume(filename)
    num_planes = volume.shape[0]
    height = volume.shape[1]
    width = volume.shape[2]

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT plane, image_data FROM annotations WHERE filename = ?",
        (filename,),
    ).fetchall()
    conn.close()

    # plane_data[plane] = { layerId: dataUrl, ... }
    plane_data = {}
    for plane_num, image_data in rows:
        try:
            plane_data[plane_num] = json.loads(image_data)
        except (json.JSONDecodeError, TypeError):
            plane_data[plane_num] = {}

    stacks = {layer_id: [] for layer_id in layer_ids}

    for p in range(num_planes):
        layers_for_plane = plane_data.get(p, {})
        for layer_id in layer_ids:
            data_url = layers_for_plane.get(layer_id)
            if data_url:
                header, encoded = data_url.split(",", 1)
                raw = base64.b64decode(encoded)
                img = Image.open(io.BytesIO(raw)).convert("RGBA")
                arr = np.array(img)
                mask = (arr[:, :, 3] > 0).astype(np.uint8) * 255
            else:
                mask = np.zeros((height, width), dtype=np.uint8)
            stacks[layer_id].append(Image.fromarray(mask, mode="L"))

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for layer_id in layer_ids:
            pages = stacks[layer_id]
            tiff_buf = io.BytesIO()
            pages[0].save(
                tiff_buf,
                format="TIFF",
                save_all=True,
                append_images=pages[1:],
            )
            tiff_buf.seek(0)

            safe_name = layer_names.get(layer_id, layer_id).replace(" ", "_")
            zf.writestr(f"{safe_name}.tiff", tiff_buf.read())

    zip_buf.seek(0)

    base_name = os.path.splitext(filename)[0]
    download_name = f"{base_name}_annotations.zip"

    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=download_name,
    )

def parse_hex_color(color):
    try:
        c = color.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (255, 59, 48)


def store_mask_as_layer(filename, mask, layer_id, color):
    """Save a (planes, height, width) mask into the annotations table as one layer.
    Returns (painted_plane_count, error_message). Other layers are left untouched."""
    volume = load_volume(filename)
    mask = np.squeeze(mask)
    if mask.ndim == 2:
        mask = mask[np.newaxis, ...]

    if mask.shape != volume.shape:
        return 0, (
            f"Mask shape {mask.shape} doesn't match the image {volume.shape} "
            f"(planes, height, width)"
        )

    r, g, b = parse_hex_color(color)
    conn = sqlite3.connect(DB_PATH)
    painted_planes = 0
    for p in range(mask.shape[0]):
        painted = mask[p] > 0
        if not painted.any():
            continue

        rgba = np.zeros((*painted.shape, 4), dtype=np.uint8)
        rgba[painted] = [r, g, b, 255]
        buf = io.BytesIO()
        Image.fromarray(rgba, "RGBA").save(buf, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

        row = conn.execute(
            "SELECT image_data FROM annotations WHERE filename = ? AND plane = ?",
            (filename, p),
        ).fetchone()
        try:
            layers = json.loads(row[0]) if row else {}
        except (json.JSONDecodeError, TypeError):
            layers = {}
        layers[layer_id] = data_url

        conn.execute(
            """
            INSERT INTO annotations (filename, plane, image_data, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(filename, plane) DO UPDATE SET
                image_data = excluded.image_data,
                updated_at = excluded.updated_at
            """,
            (filename, p, json.dumps(layers), datetime.datetime.now().isoformat()),
        )
        painted_planes += 1

    conn.commit()
    conn.close()
    return painted_planes, None


@app.route("/api/mask/import/<filename>", methods=["POST"])
def import_mask(filename):
    """Load a mask TIFF (one page per plane, nonzero = painted) into a layer."""
    upload = request.files.get("file")
    layer_id = request.form.get("layerId", "").strip()
    color = request.form.get("color", "#ff3b30")

    if upload is None or not layer_id:
        return jsonify({"error": "A mask file and a layerId are required"}), 400

    try:
        mask = tiff.imread(io.BytesIO(upload.read()))
    except Exception:
        return jsonify({"error": "Could not read that file as a TIFF"}), 400

    count, error = store_mask_as_layer(filename, mask, layer_id, color)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"status": "imported", "paintedPlanes": count})


def open_sldy(filename):
    reader = SBReadFile()
    reader.Open(os.path.join(DATA_DIR, filename))
    return reader




@app.route("/api/mask/sldy/<filename>", methods=["GET"])
def list_sldy_masks(filename):
    """Names of the masks stored inside an .sldy file."""
    if get_file_type(filename) != "sldy":
        return jsonify({"masks": []})
    try:
        names = list(open_sldy(filename).GetMaskNames(0) or [])
    except Exception as e:
        return jsonify({"error": f"Could not read masks: {e}"}), 500
    return jsonify({"masks": names})


@app.route("/api/mask/import-sldy/<filename>", methods=["POST"])
def import_sldy_mask(filename):
    """Copy one mask stored inside an .sldy file into a new layer."""
    if get_file_type(filename) != "sldy":
        return jsonify({"error": "This is not an .sldy file"}), 400

    data = request.get_json(silent=True) or {}
    layer_id = (data.get("layerId") or "").strip()
    mask_index = data.get("maskIndex", 0)
    color = data.get("color", "#ff3b30")
    if not layer_id:
        return jsonify({"error": "layerId is required"}), 400

    try:
        reader = open_sldy(filename)
        names = list(reader.GetMaskNames(0) or [])
        if not names:
            return jsonify({"error": "This file has no masks"}), 400
        if not isinstance(mask_index, int) or not 0 <= mask_index < len(names):
            return jsonify({"error": "Invalid mask index"}), 400
        mask = np.array(reader.ReadMaskBuf(0, mask_index, 0, True))
    except Exception as e:
        return jsonify({"error": f"Could not read the mask: {e}"}), 500

    count, error = store_mask_as_layer(filename, mask, layer_id, color)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"status": "imported", "paintedPlanes": count, "name": names[mask_index]})


@app.route("/api/ml/preview")
def ml_preview():
    import data_preview
    import ml_job
    n_planes = request.args.get("planes", 3, type=int)
    patch = request.args.get("patch", 7, type=int)
    mode = request.args.get("mode", "painted")
    filename = request.args.get("filename") or None
    try:
        return jsonify(data_preview.build_preview(
            DB_PATH, load_volume, n_planes, patch=patch,
            guess_fn=ml_job.guess_fn(), test_keys=ml_job.test_keys(),
            painted_keys=ml_job.painted_keys(), mode=mode, filename=filename))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ml/train", methods=["POST"])
def ml_train():
    import ml_job
    body = request.get_json(silent=True) or {}
    try:
                ml_job.start(DB_PATH, load_volume,
                     int(body.get("patch", 7)), int(body.get("hidden", 32)),
                     int(body.get("steps", 500)), float(body.get("lr", 0.05)),
                     body.get("filename"),
                     body.get("model", "mlp"), int(body.get("base", 16)),
                     body.get("loss"), float(body.get("beta", 0.7)))
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(ml_job.status())


@app.route("/api/ml/train/status")
def ml_train_status():
    import ml_job
    return jsonify(ml_job.status())


@app.route("/api/ml/train/stop", methods=["POST"])
def ml_train_stop():
    import ml_job
    ml_job.stop()
    return jsonify({"ok": True})

@app.route("/api/ml/model/save", methods=["POST"])
def ml_model_save():
    import ml_job
    body = request.get_json(silent=True) or {}
    try:
        return jsonify({"saved": ml_job.save_model(body.get("name", ""))})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/ml/models")
def ml_models():
    import model_store
    return jsonify(model_store.list_models())


@app.route("/api/ml/model/load", methods=["POST"])
def ml_model_load():
    import ml_job
    body = request.get_json(silent=True) or {}
    try:
        ml_job.load_model(body.get("name", ""))
        return jsonify(ml_job.status())
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    app.run(debug=True, port=5000)