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

app = Flask(__name__)
CORS(app)

DATA_DIR = "C:/Users/xhd6ct/Documents/research_data"  # starting default — can be changed from the UI

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
    num_planes = get_num_planes(filename)
    return jsonify({"numPlanes": num_planes})


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


@app.route("/api/redo/<filename>/<int:plane>", methods=["POST"])
def apply_redo(filename, plane):
    data = request.get_json(silent=True) or {}
    entry_id = data.get("id")
    layer_id = data.get("layerId")
    current_image = data.get("currentImage")
    if entry_id is None or not layer_id or current_image is None:
        return jsonify({"error": "id, layerId, currentImage required"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM action_history WHERE id = ?", (entry_id,))
    conn.execute(
        "INSERT INTO action_history (filename, plane, layer_id, image_data, stack, created_at) VALUES (?, ?, ?, ?, 'undo', ?)",
        (filename, plane, layer_id, current_image, datetime.datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)