import { useState, useEffect, useRef } from "react";
import "./App.css";

function hexToRgba(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return [r, g, b, 255];
}

function colorsMatch(a, b) {
  return a[0] === b[0] && a[1] === b[1] && a[2] === b[2] && a[3] === b[3];
}

function floodFill(ctx, startX, startY, fillColorHex, width, height) {
  if (startX < 0 || startX >= width || startY < 0 || startY >= height) return;

  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;
  const startIdx = (startY * width + startX) * 4;
  const startColor = [
    data[startIdx],
    data[startIdx + 1],
    data[startIdx + 2],
    data[startIdx + 3],
  ];
  const fillColor = hexToRgba(fillColorHex);

  if (colorsMatch(startColor, fillColor)) return;

  const stack = [[startX, startY]];
  while (stack.length) {
    const [x, y] = stack.pop();
    if (x < 0 || x >= width || y < 0 || y >= height) continue;
    const idx = (y * width + x) * 4;
    const current = [data[idx], data[idx + 1], data[idx + 2], data[idx + 3]];
    if (!colorsMatch(current, startColor)) continue;

    data[idx] = fillColor[0];
    data[idx + 1] = fillColor[1];
    data[idx + 2] = fillColor[2];
    data[idx + 3] = fillColor[3];

    stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
  }

  ctx.putImageData(imageData, 0, 0);
}

const DEFAULT_COLORS = [
  "#ff3b30",
  "#2563eb",
  "#f59e0b",
  "#10b981",
  "#a855f7",
  "#ec4899",
];

function App() {
  const [files, setFiles] = useState([]);
  const [directory, setDirectory] = useState("");
  const [directoryInput, setDirectoryInput] = useState("");
  const [directoryError, setDirectoryError] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [plane, setPlane] = useState(0);
  const [numPlanes, setNumPlanes] = useState(1);
  const isDragging = useRef(false);
  const lastPos = useRef({ x: 0, y: 0 });
  const [histogram, setHistogram] = useState(null);
  const [draggingHandle, setDraggingHandle] = useState(null);
  const histContainerRef = useRef(null);
  const [blackPoint, setBlackPoint] = useState(0);
  const [whitePoint, setWhitePoint] = useState(255);
  const histCanvasRef = useRef(null);

  const [annotationTool, setAnnotationTool] = useState("brush");
  const [drawingEnabled, setDrawingEnabled] = useState(false);
  const [brushSize, setBrushSize] = useState(12);
  const [imageSize, setImageSize] = useState(null);
  const imageFrameRef = useRef(null);
  const baseCanvasRef = useRef(null);
  const canvasRefs = useRef({}); // { layerId: canvasElement }
  const isPaintingRef = useRef(false);
  const lastPointRef = useRef({ x: 0, y: 0 });
  const currentPlaneRef = useRef(null);
  const nextLayerNum = useRef(2);
  const layersLoadedRef = useRef(false);
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);

  const [layers, setLayers] = useState([
    { id: "layer-1", name: "Layer 1", color: DEFAULT_COLORS[0], visible: true },
  ]);
  const [activeLayerId, setActiveLayerId] = useState("layer-1");
  const [baseVisible, setBaseVisible] = useState(true);

  const activeLayer = layers.find((l) => l.id === activeLayerId) || layers[0];

  function addLayer() {
    const n = nextLayerNum.current++;
    const newLayer = {
      id: `layer-${Date.now()}`,
      name: `Layer ${n}`,
      color: DEFAULT_COLORS[(n - 1) % DEFAULT_COLORS.length],
      visible: true,
    };
    setLayers((prev) => [...prev, newLayer]);
    setActiveLayerId(newLayer.id);
  }

  function removeLayer(id) {
    setLayers((prev) => {
      const remaining = prev.filter((l) => l.id !== id);
      if (remaining.length === 0) return prev; // keep at least one layer
      if (activeLayerId === id) setActiveLayerId(remaining[0].id);
      return remaining;
    });
    delete canvasRefs.current[id];
  }

  function renameLayer(id, name) {
    setLayers((prev) => prev.map((l) => (l.id === id ? { ...l, name } : l)));
  }

  function setLayerColor(id, color) {
    setLayers((prev) => prev.map((l) => (l.id === id ? { ...l, color } : l)));
  }

  function toggleLayerVisible(id) {
    setLayers((prev) =>
      prev.map((l) => (l.id === id ? { ...l, visible: !l.visible } : l)),
    );
  }

  useEffect(() => {
    fetch("http://localhost:5000/api/directory")
      .then((res) => res.json())
      .then((data) => {
        setDirectory(data.path);
        setDirectoryInput(data.path);
      })
      .catch((err) => console.error("Failed to fetch directory:", err));
  }, []);

  useEffect(() => {
    fetch("http://localhost:5000/api/layers")
      .then((res) => res.json())
      .then((data) => {
        if (data.layers && data.layers.length > 0) {
          setLayers(data.layers.map((l) => ({ ...l, visible: true })));
          setActiveLayerId(data.layers[0].id);
          nextLayerNum.current = data.layers.length + 1;
        }
        layersLoadedRef.current = true;
      })
      .catch((err) => {
        console.error("Failed to fetch layers:", err);
        layersLoadedRef.current = true;
      });
  }, []);

  useEffect(() => {
    if (!layersLoadedRef.current) return;
    fetch("http://localhost:5000/api/layers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        layers: layers.map(({ id, name, color }) => ({ id, name, color })),
      }),
    }).catch((err) => console.error("Failed to save layers:", err));
  }, [layers]);

  useEffect(() => {
    if (!selectedFile) return;
    let ignore = false;
    fetch(`http://localhost:5000/api/info/${selectedFile}`)
      .then((res) => res.json())
      .then((data) => {
        if (ignore) return;
        setNumPlanes(data.numPlanes);
      })
      .catch((err) => console.error("Failed to fetch file info:", err));
    return () => {
      ignore = true;
    };
  }, [selectedFile]);

  useEffect(() => {
    if (!selectedFile) return;
    let ignore = false;
    fetch(`http://localhost:5000/api/histogram/${selectedFile}`)
      .then((res) => res.json())
      .then((data) => {
        if (ignore) return;
        setHistogram(data);
        setBlackPoint(data.min);
        setWhitePoint(data.max);
      })
      .catch((err) => console.error("Failed to fetch histogram:", err));
    return () => {
      ignore = true;
    };
  }, [selectedFile]);

  useEffect(() => {
    if (!histogram || !histCanvasRef.current) return;
    const canvas = histCanvasRef.current;
    const ctx = canvas.getContext("2d");
    const { counts, min, max } = histogram;
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    const maxCount = Math.max(...counts);
    const barWidth = w / counts.length;

    ctx.fillStyle = "#8a97a8";
    counts.forEach((count, i) => {
      const barHeight = maxCount > 0 ? (count / maxCount) * h : 0;
      ctx.fillRect(i * barWidth, h - barHeight, barWidth, barHeight);
    });

    const range = max - min || 1;
    const blackX = ((blackPoint - min) / range) * w;
    const whiteX = ((whitePoint - min) / range) * w;

    ctx.strokeStyle = "#5b6b82";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(blackX, h);
    ctx.lineTo(whiteX, 0);
    ctx.stroke();
  }, [histogram, blackPoint, whitePoint]);

  useEffect(() => {
    if (!draggingHandle || !histogram) return;

    function handleMove(e) {
      const rect = histContainerRef.current.getBoundingClientRect();
      const x = Math.min(Math.max(e.clientX - rect.left, 0), rect.width);
      const value =
        histogram.min + (x / rect.width) * (histogram.max - histogram.min);

      if (draggingHandle === "black") {
        setBlackPoint(Math.min(value, whitePoint - 1));
      } else {
        setWhitePoint(Math.max(value, blackPoint + 1));
      }
    }

    function handleUp() {
      setDraggingHandle(null);
    }

    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [draggingHandle, histogram, blackPoint, whitePoint]);

  // Load base image + all layer canvases whenever file/plane/contrast changes
  useEffect(() => {
    if (!selectedFile) return;
    let cancelled = false;

    const isNewPlane =
      !currentPlaneRef.current ||
      currentPlaneRef.current.file !== selectedFile ||
      currentPlaneRef.current.plane !== plane;

    // Save current layers' pixel data for the plane we're leaving
    if (isNewPlane && currentPlaneRef.current) {
      const { file: prevFile, plane: prevPlane } = currentPlaneRef.current;
      const layerData = {};
      Object.entries(canvasRefs.current).forEach(([id, canvas]) => {
        if (canvas) layerData[id] = canvas.toDataURL();
      });
      fetch(`http://localhost:5000/api/annotations/${prevFile}/${prevPlane}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ layers: layerData }),
      }).catch((err) => console.error("Failed to save annotations:", err));
    }

    const url = `http://localhost:5000/api/plane/${selectedFile}/${plane}?min=${blackPoint}&max=${whitePoint}`;

    const img = new Image();
    img.onload = () => {
      if (cancelled) return;
      setImageSize({ width: img.naturalWidth, height: img.naturalHeight });

      const baseCanvas = baseCanvasRef.current;
      if (baseCanvas) {
        baseCanvas.width = img.naturalWidth;
        baseCanvas.height = img.naturalHeight;
        const ctx = baseCanvas.getContext("2d");
        ctx.clearRect(0, 0, baseCanvas.width, baseCanvas.height);
        ctx.drawImage(img, 0, 0);
      }

      if (isNewPlane) {
        // Resize + clear every layer canvas
        Object.values(canvasRefs.current).forEach((canvas) => {
          if (!canvas) return;
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
        });

        // Load saved layer data for the new plane, if any
        fetch(`http://localhost:5000/api/annotations/${selectedFile}/${plane}`)
          .then((res) => res.json())
          .then((data) => {
            if (cancelled) return;
            Object.entries(data.layers || {}).forEach(([id, dataUrl]) => {
              const canvas = canvasRefs.current[id];
              if (!canvas) return;
              const ctx = canvas.getContext("2d");
              const savedImg = new Image();
              savedImg.onload = () => {
                ctx.drawImage(savedImg, 0, 0);
              };
              savedImg.src = dataUrl;
            });
          })
          .catch((err) => console.error("Failed to load annotations:", err));

        currentPlaneRef.current = { file: selectedFile, plane };
        refreshUndoRedoState();
      }
    };
    img.onerror = () => {
      console.error("Failed to load image:", url);
    };
    img.src = url;

    return () => {
      cancelled = true;
    };
  }, [selectedFile, plane, blackPoint, whitePoint]);

  function handleSetDirectory(e) {
    e.preventDefault();
    fetch("http://localhost:5000/api/directory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: directoryInput }),
    })
      .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          setDirectoryError(data.error);
          return;
        }
        setDirectoryError("");
        setDirectory(data.path);
        setSelectedFile(null);
        setHistogram(null);
        return fetch("http://localhost:5000/api/files")
          .then((res) => res.json())
          .then((files) => setFiles(files));
      })
      .catch((err) => console.error("Failed to set directory:", err));
  }

  function handleSelectFile(file) {
    setSelectedFile(file);
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setPlane(0);
  }

  function handleWheel(e) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setZoom((z) => Math.min(Math.max(z + delta, 0.2), 5));
  }

  function handleMouseDown(e) {
    isDragging.current = true;
    lastPos.current = { x: e.clientX, y: e.clientY };
  }

  function handleMouseMove(e) {
    if (!isDragging.current) return;
    const dx = e.clientX - lastPos.current.x;
    const dy = e.clientY - lastPos.current.y;
    lastPos.current = { x: e.clientX, y: e.clientY };
    setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
  }

  function handleMouseUp() {
    isDragging.current = false;
  }

  function zoomIn() {
    setZoom((z) => Math.min(z + 0.2, 5));
  }

  function zoomOut() {
    setZoom((z) => Math.max(z - 0.2, 0.2));
  }

  function previousPlane() {
    setPlane((p) => Math.max(p - 1, 0));
  }

  function nextPlane() {
    setPlane((p) => Math.min(p + 1, numPlanes - 1));
  }

  function getCanvasPoint(e, canvas) {
    const rect = canvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * canvas.width;
    const y = ((e.clientY - rect.top) / rect.height) * canvas.height;
    return { x, y };
  }

  function handleCanvasMouseDown(e) {
    e.stopPropagation();
    pushHistory(activeLayerId);

    const canvas = canvasRefs.current[activeLayerId];
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const point = getCanvasPoint(e, canvas);

    if (annotationTool === "fill") {
      floodFill(
        ctx,
        Math.floor(point.x),
        Math.floor(point.y),
        activeLayer.color,
        canvas.width,
        canvas.height,
      );
      return;
    }

    isPaintingRef.current = true;
    lastPointRef.current = point;

    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = brushSize;
    ctx.globalCompositeOperation =
      annotationTool === "eraser" ? "destination-out" : "source-over";
    ctx.strokeStyle = activeLayer.color;

    ctx.beginPath();
    ctx.moveTo(point.x, point.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
  }

  function handleCanvasMouseMove(e) {
    if (!isPaintingRef.current) return;
    e.stopPropagation();
    const canvas = canvasRefs.current[activeLayerId];
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const point = getCanvasPoint(e, canvas);

    ctx.beginPath();
    ctx.moveTo(lastPointRef.current.x, lastPointRef.current.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();

    lastPointRef.current = point;
  }

  function handleCanvasMouseUp() {
    isPaintingRef.current = false;
  }

  function handleClearActiveLayer() {
    pushHistory(activeLayerId);
    const canvas = canvasRefs.current[activeLayerId];
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  function handleToolClick(tool) {
    if (annotationTool === tool && drawingEnabled) {
      setDrawingEnabled(false);
    } else {
      setAnnotationTool(tool);
      setDrawingEnabled(true);
    }
  }

  async function pushHistory(layerId) {
    const canvas = canvasRefs.current[layerId];
    if (!canvas || !selectedFile) return;
    const dataUrl = canvas.toDataURL();
    try {
      await fetch(
        `http://localhost:5000/api/history/${selectedFile}/${plane}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ layerId, image: dataUrl }),
        },
      );
      setCanUndo(true);
      setCanRedo(false);
    } catch (err) {
      console.error("Failed to push history:", err);
    }
  }

  async function refreshUndoRedoState() {
    if (!selectedFile) return;
    try {
      const [u, r] = await Promise.all([
        fetch(`http://localhost:5000/api/undo/${selectedFile}/${plane}`).then(
          (res) => res.json(),
        ),
        fetch(`http://localhost:5000/api/redo/${selectedFile}/${plane}`).then(
          (res) => res.json(),
        ),
      ]);
      setCanUndo(u.available);
      setCanRedo(r.available);
    } catch (err) {
      console.error("Failed to refresh undo/redo state:", err);
    }
  }

  async function handleUndo() {
    if (!selectedFile || !canUndo) return;
    const peek = await fetch(
      `http://localhost:5000/api/undo/${selectedFile}/${plane}`,
    ).then((res) => res.json());
    if (!peek.available) {
      setCanUndo(false);
      return;
    }
    const { id, layerId, image } = peek;
    const canvas = canvasRefs.current[layerId];
    if (!canvas) return;
    const currentImage = canvas.toDataURL();

    await fetch(`http://localhost:5000/api/undo/${selectedFile}/${plane}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, layerId, currentImage }),
    });

    const ctx = canvas.getContext("2d");
    const img = new Image();
    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
    };
    img.src = image;

    refreshUndoRedoState();
  }

  async function handleRedo() {
    if (!selectedFile || !canRedo) return;
    const peek = await fetch(
      `http://localhost:5000/api/redo/${selectedFile}/${plane}`,
    ).then((res) => res.json());
    if (!peek.available) {
      setCanRedo(false);
      return;
    }
    const { id, layerId, image } = peek;
    const canvas = canvasRefs.current[layerId];
    if (!canvas) return;
    const currentImage = canvas.toDataURL();

    await fetch(`http://localhost:5000/api/redo/${selectedFile}/${plane}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, layerId, currentImage }),
    });

    const ctx = canvas.getContext("2d");
    const img = new Image();
    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
    };
    img.src = image;

    refreshUndoRedoState();
  }

  return (
    <div className="app">
      <div className="sidebar">
        <form className="directory-form" onSubmit={handleSetDirectory}>
          <label className="directory-label">Image folder</label>
          <div className="directory-row">
            <input
              type="text"
              className="directory-input"
              value={directoryInput}
              onChange={(e) => setDirectoryInput(e.target.value)}
              placeholder="C:\Users\you\Documents\data"
            />
            <button type="submit" className="directory-button">
              Set
            </button>
          </div>
          {directoryError && (
            <p className="directory-error">{directoryError}</p>
          )}
        </form>
        <div className="viewer-dropdown">
          <div className="viewer-dropdown-trigger">
            <h1>Image Viewer</h1>
            <span className="chevron">▸</span>
          </div>
          <ul className="file-list dropdown-list">
            {files.map((file) => (
              <li
                key={file}
                onClick={() => handleSelectFile(file)}
                className={`file-item ${file === selectedFile ? "selected" : ""}`}
              >
                {file === selectedFile && <span className="dot" />}
                {file}
              </li>
            ))}
          </ul>
        </div>

        {histogram && (
          <div className="histogram-panel">
            <p className="histogram-title">{selectedFile}</p>

            <div className="histogram-container" ref={histContainerRef}>
              <canvas
                ref={histCanvasRef}
                width={220}
                height={90}
                className="histogram-canvas"
              />
              <div
                className="histogram-handle"
                style={{
                  left: `${((blackPoint - histogram.min) / (histogram.max - histogram.min)) * 100}%`,
                }}
                onMouseDown={() => setDraggingHandle("black")}
              />
              <div
                className="histogram-handle"
                style={{
                  left: `${((whitePoint - histogram.min) / (histogram.max - histogram.min)) * 100}%`,
                }}
                onMouseDown={() => setDraggingHandle("white")}
              />
            </div>

            <div className="histogram-row">
              <input
                type="number"
                className="histogram-input"
                value={Math.round(blackPoint)}
                min={histogram.min}
                max={histogram.max}
                onChange={(e) =>
                  setBlackPoint(
                    Math.min(Number(e.target.value), whitePoint - 1),
                  )
                }
              />
              <input
                type="number"
                className="histogram-input"
                value={Math.round(whitePoint)}
                min={histogram.min}
                max={histogram.max}
                onChange={(e) =>
                  setWhitePoint(
                    Math.max(Number(e.target.value), blackPoint + 1),
                  )
                }
              />
            </div>
          </div>
        )}

        {selectedFile && (
          <div className="layers-panel">
            <p className="layers-title">Layers</p>

            <label className="layer-row">
              <input
                type="checkbox"
                checked={baseVisible}
                onChange={() => setBaseVisible((v) => !v)}
              />
              Base image
            </label>

            {layers.map((layer) => (
              <div
                key={layer.id}
                className={`layer-item ${layer.id === activeLayerId ? "active" : ""}`}
                onClick={() => setActiveLayerId(layer.id)}
              >
                <input
                  type="checkbox"
                  checked={layer.visible}
                  onChange={(e) => {
                    e.stopPropagation();
                    toggleLayerVisible(layer.id);
                  }}
                  onClick={(e) => e.stopPropagation()}
                />
                <input
                  type="color"
                  className="layer-color-input"
                  value={layer.color}
                  onChange={(e) => setLayerColor(layer.id, e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                />
                <input
                  type="text"
                  className="layer-name-input"
                  value={layer.name}
                  onChange={(e) => renameLayer(layer.id, e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                />
                {layers.length > 1 && (
                  <button
                    className="layer-remove-button"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeLayer(layer.id);
                    }}
                    title="Delete layer"
                  >
                    ×
                  </button>
                )}
              </div>
            ))}

            <button className="add-layer-button" onClick={addLayer}>
              + Add layer
            </button>
          </div>
        )}
      </div>

      <div className="viewer">
        <div className="toolbar">
          <button onClick={zoomOut}>−</button>
          <span className="zoom-level">{Math.round(zoom * 100)}%</span>
          <button onClick={zoomIn}>+</button>

          {selectedFile && numPlanes > 1 && (
            <>
              <div className="divider" />
              <button onClick={previousPlane} disabled={plane === 0}>
                ←
              </button>
              <span className="plane-label">
                Plane {plane + 1} / {numPlanes}
              </span>
              <input
                type="range"
                min="0"
                max={numPlanes - 1}
                value={plane}
                onChange={(e) => setPlane(Number(e.target.value))}
              />
              <button onClick={nextPlane} disabled={plane === numPlanes - 1}>
                →
              </button>
            </>
          )}
        </div>

        {selectedFile && (
          <div className="annotation-toolbar">
            <button
              className={`tool-button ${annotationTool === "brush" && drawingEnabled ? "active" : ""}`}
              onClick={() => handleToolClick("brush")}
            >
              Brush
            </button>
            <button
              className={`tool-button ${annotationTool === "fill" && drawingEnabled ? "active" : ""}`}
              onClick={() => handleToolClick("fill")}
            >
              Fill
            </button>
            <button
              className={`tool-button ${annotationTool === "eraser" && drawingEnabled ? "active" : ""}`}
              onClick={() => handleToolClick("eraser")}
            >
              Eraser
            </button>

            {annotationTool !== "fill" && (
              <>
                <div className="divider" />
                <label className="brush-size-label">
                  Size: {brushSize}px
                  <input
                    type="range"
                    min="2"
                    max="60"
                    value={brushSize}
                    onChange={(e) => setBrushSize(Number(e.target.value))}
                  />
                </label>
              </>
            )}

            <div className="divider" />
            <button onClick={handleUndo} disabled={!canUndo} title="Undo">
              ↶ Undo
            </button>
            <button onClick={handleRedo} disabled={!canRedo} title="Redo">
              ↷ Redo
            </button>

            <div className="divider" />
            <span className="active-layer-label">
              Drawing on: <strong>{activeLayer.name}</strong>
            </span>

            <div className="divider" />
            <button className="tool-button" onClick={handleClearActiveLayer}>
              Clear layer
            </button>
          </div>
        )}

        <div
          ref={imageFrameRef}
          className={`image-frame ${isDragging.current ? "dragging" : ""}`}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {selectedFile ? (
            <div
              className="image-annotate-wrapper"
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                transformOrigin: "center",
                width: imageSize ? `${imageSize.width}px` : undefined,
                height: imageSize ? `${imageSize.height}px` : undefined,
                maxWidth: "100%",
                maxHeight: "100%",
              }}
            >
              <canvas
                ref={baseCanvasRef}
                className="base-canvas"
                style={{ display: baseVisible ? "block" : "none" }}
              />
              {layers.map((layer) => (
                <canvas
                  key={layer.id}
                  ref={(el) => {
                    if (el) canvasRefs.current[layer.id] = el;
                  }}
                  className="annotate-canvas"
                  style={{
                    display: layer.visible ? "block" : "none",
                    pointerEvents:
                      layer.id === activeLayerId && drawingEnabled
                        ? "auto"
                        : "none",
                  }}
                  onMouseDown={handleCanvasMouseDown}
                  onMouseMove={handleCanvasMouseMove}
                  onMouseUp={handleCanvasMouseUp}
                  onMouseLeave={handleCanvasMouseUp}
                />
              ))}
            </div>
          ) : (
            <p className="placeholder">
              Select an image from the list to view it.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
