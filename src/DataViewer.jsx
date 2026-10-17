import { useEffect, useRef, useState } from "react";

const API = "http://localhost:5000";

const styles = {
  overlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(15, 23, 42, 0.55)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
  },
  modal: {
    background: "#ffffff",
    borderRadius: 14,
    width: "min(1100px, 94vw)",
    maxHeight: "90vh",
    display: "flex",
    flexDirection: "column",
    boxShadow: "0 20px 60px rgba(15, 23, 42, 0.35)",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    padding: "14px 20px",
    borderBottom: "1px solid #e2e8f0",
  },
  title: { margin: 0, fontSize: "1.1rem", color: "#1e3a8a" },
  headerButtons: { display: "flex", gap: 8, alignItems: "center" },
  body: { overflowY: "auto", padding: "16px 20px 24px" },
  note: { color: "#475569", fontSize: "0.9rem", margin: "0 0 12px" },
  row: {
    display: "flex",
    gap: 24,
    alignItems: "flex-start",
    flexWrap: "wrap",
    padding: "16px 0",
    borderTop: "1px solid #e2e8f0",
  },
  rowTitle: { fontWeight: 600, color: "#1e3a8a", margin: "0 0 8px" },
  imageWrap: { position: "relative", width: 340, background: "#000" },
  stripColumn: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 6,
  },
  stripLabel: { fontSize: "0.8rem", color: "#475569", textAlign: "center" },
  button: {
    padding: "6px 12px",
    borderRadius: 8,
    border: "1px solid #2563eb",
    background: "#ffffff",
    color: "#2563eb",
    cursor: "pointer",
    fontSize: "0.9rem",
  },
  panel: {
    border: "1px solid #e2e8f0",
    borderRadius: 10,
    padding: "12px 14px",
    marginBottom: 12,
    background: "#f8fafc",
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: 2,
    fontSize: "0.8rem",
    color: "#334155",
  },
  input: {
    width: 80,
    padding: "4px 6px",
    borderRadius: 6,
    border: "1px solid #cbd5e1",
  },
  primary: {
    padding: "7px 16px",
    borderRadius: 8,
    border: "1px solid #2563eb",
    background: "#2563eb",
    color: "#ffffff",
    cursor: "pointer",
    fontSize: "0.9rem",
  },
  toggle: {
    fontSize: "0.85rem",
    color: "#334155",
    display: "flex",
    gap: 4,
    alignItems: "center",
  },
};

function PlaneRow({
  plane,
  patchSize,
  showMask,
  showBoxes,
  guessAsMask,
  showPatches = true,
}) {
  const stripScale = 8; // each patch pixel is drawn 8 x 8 screen pixels

  return (
    <div style={styles.row}>
      <div>
        <p style={styles.rowTitle}>
          {plane.filename} · plane {plane.plane + 1}
        </p>
        <div style={styles.imageWrap}>
          <img
            src={plane.image}
            alt="downsampled plane"
            style={{
              width: "100%",
              display: "block",
              imageRendering: "pixelated",
            }}
          />
          {showMask && plane.mask && (
            <img
              src={plane.mask}
              alt="painted mask"
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                opacity: 0.45,
                imageRendering: "pixelated",
              }}
            />
          )}
          {showBoxes && showPatches && (
            <svg
              viewBox={`0 0 ${plane.width} ${plane.height}`}
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
              }}
            >
              {plane.unpainted.map((p, i) => (
                <rect
                  key={`u${i}`}
                  x={p.x}
                  y={p.y}
                  width={patchSize}
                  height={patchSize}
                  fill="none"
                  stroke="#22d3ee"
                  strokeWidth="2"
                  vectorEffect="non-scaling-stroke"
                />
              ))}
              {plane.painted.map((p, i) => (
                <rect
                  key={`p${i}`}
                  x={p.x}
                  y={p.y}
                  width={patchSize}
                  height={patchSize}
                  fill="none"
                  stroke="#84cc16"
                  strokeWidth="2"
                  vectorEffect="non-scaling-stroke"
                />
              ))}
            </svg>
          )}
        </div>
        <div style={{ ...styles.stripLabel, marginTop: 6 }}>
          {plane.width} × {plane.height} px (downsampled)
        </div>
      </div>

      {showPatches && plane.paintedStrip && (
        <div style={styles.stripColumn}>
          <img
            src={plane.paintedStrip}
            alt="painted patches"
            style={{
              width: patchSize * stripScale,
              imageRendering: "pixelated",
              border: "2px solid #84cc16",
            }}
          />
          <div style={styles.stripLabel}>
            painted
            <br />
            {plane.painted.length} patches
          </div>
        </div>
      )}

      {showPatches && plane.unpaintedStrip && (
        <div style={styles.stripColumn}>
          <img
            src={plane.unpaintedStrip}
            alt="not painted patches"
            style={{
              width: patchSize * stripScale,
              imageRendering: "pixelated",
              border: "2px solid #22d3ee",
            }}
          />
          <div style={styles.stripLabel}>
            not painted
            <br />
            {plane.unpainted.length} patches
          </div>
        </div>
      )}

      {plane.guess && (
        <div style={styles.stripColumn}>
          <div
            style={{
              ...styles.imageWrap,
              border: "2px solid #f97316",
              boxSizing: "content-box",
            }}
          >
            <img
              src={guessAsMask ? plane.image : plane.guess}
              alt="network guess"
              style={{
                width: "100%",
                display: "block",
                imageRendering: "pixelated",
              }}
            />
            {guessAsMask && (
              <img
                src={plane.guessMask}
                alt="guess as mask"
                style={{
                  position: "absolute",
                  inset: 0,
                  width: "100%",
                  height: "100%",
                  opacity: 0.45,
                  imageRendering: "pixelated",
                }}
              />
            )}
          </div>
          <div style={styles.stripLabel}>
            Predictions on held out plane
            {plane.dice != null && (
              <>
                <br />
                overlap with your painting (Dice): {plane.dice.toFixed(2)}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function LossCurve({ history }) {
  if (history.length < 2) return null;
  const W = 420,
    H = 110;
  const maxStep = history[history.length - 1].step;
  const maxLoss = Math.max(...history.map((h) => h.loss), 0.01);
  const x = (s) => (s / maxStep) * W;
  const line = (value, top) =>
    history.map((h) => `${x(h.step)},${H - (value(h) / top) * H}`).join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{
        width: W,
        maxWidth: "100%",
        height: H,
        background: "#fff",
        border: "1px solid #e2e8f0",
        borderRadius: 6,
      }}
    >
      <polyline
        points={line((h) => h.loss, maxLoss)}
        fill="none"
        stroke="#2563eb"
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
      <polyline
        points={line((h) => h.acc, 1)}
        fill="none"
        stroke="#16a34a"
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export default function DataViewer({ onClose, filename }) {
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showMask, setShowMask] = useState(true);
  const [showBoxes, setShowBoxes] = useState(true);
  const [guessAsMask, setGuessAsMask] = useState(true);

  const [model, setModel] = useState("mlp");
  const [base, setBase] = useState(16);
  const [loss, setLoss] = useState("bce");
  const [beta, setBeta] = useState(0.7);
  const [patch, setPatch] = useState(31);
  const [hidden, setHidden] = useState(32);
  const [steps, setSteps] = useState(500);
  const [lr, setLr] = useState(0.05);
  const [job, setJob] = useState({ state: "idle", history: [] });
  const [saveName, setSaveName] = useState("");
  const [savedModels, setSavedModels] = useState([]);
  const [pick, setPick] = useState("");
  const [modelMsg, setModelMsg] = useState("");

  function load(p = patch) {
    setLoading(true);
    setError("");
    fetch(
      `${API}/api/ml/preview?planes=3&patch=${p}&filename=${encodeURIComponent(filename || "")}`,
    )
      .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          setError(data.error || "Could not load the training data");
          return;
        }
        setPreview(data);
      })
      .catch(() => setError("Could not reach the backend"))
      .finally(() => setLoading(false));
  }

  function refreshStatus() {
    return fetch(`${API}/api/ml/train/status`)
      .then((res) => res.json())
      .then(setJob)
      .catch(() => {});
  }

  function startTraining() {
    setError("");
    fetch(`${API}/api/ml/train`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        base,
        patch,
        hidden,
        steps,
        lr,
        loss,
        beta,
        filename,
      }),
    })
      .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) setError(data.error || "Could not start training");
        else setJob(data);
      })
      .catch(() => setError("Could not reach the backend"));
  }

  function stopTraining() {
    fetch(`${API}/api/ml/train/stop`, { method: "POST" }).catch(() => {});
  }

  function refreshModels() {
    fetch(`${API}/api/ml/models`)
      .then((res) => res.json())
      .then((list) => {
        setSavedModels(list);
        setPick((p) => p || (list[0] ? list[0].name : ""));
      })
      .catch(() => {});
  }

  function saveModel() {
    setModelMsg("");
    fetch(`${API}/api/ml/model/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name:
          saveName ||
          `${model}_${new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "")}`,
      }),
    })
      .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          setModelMsg(data.error || "Could not save the model");
          return;
        }
        setModelMsg(`Saved ${data.saved}.pt to: ${data.paths.join("  and  ")}`);
        setSaveName("");
        setPick(data.saved);
        refreshModels();
        refreshStatus();
      })
      .catch(() => setModelMsg("Could not reach the backend"));
  }

  function loadModel() {
    if (!pick) return;
    setModelMsg("");
    fetch(`${API}/api/ml/model/load`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: pick }),
    })
      .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          setModelMsg(data.error || "Could not load the model");
          return;
        }
        setJob(data);
        const c = data.config || {}; // make the controls match the loaded model
        if (c.model) setModel(c.model);
        if (c.base) setBase(c.base);
        if (c.patch) setPatch(c.patch);
        if (c.hidden) setHidden(c.hidden);
        if (c.steps) setSteps(c.steps);
        if (c.lr) setLr(c.lr);
        if (c.loss) setLoss(c.loss);
        if (c.beta) setBeta(c.beta);
        setModelMsg(`Loaded ${data.loadedName}`);
        load(c.patch || patch);
      })
      .catch(() => setModelMsg("Could not reach the backend"));
  }

  const running = job.state === "loading" || job.state === "training";

  useEffect(() => {
    load();
    refreshStatus();
    refreshModels();
  }, []);

  // while training, ask for progress once a second
  useEffect(() => {
    if (!running) return;
    const id = setInterval(refreshStatus, 1000);
    return () => clearInterval(id);
  }, [running]);

  // when a run finishes, reload the planes so they include the network's guess
  const wasRunning = useRef(false);
  useEffect(() => {
    if (wasRunning.current && !running && job.state !== "error") {
      load(patch);
    }
    wasRunning.current = running;
  }, [running]);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const isUnet = job.config && job.config.model === "unet";
  const metricName = isUnet ? "test Dice" : "test accuracy";
  const fmtMetric = (m) => (isUnet ? m.toFixed(2) : `${(m * 100).toFixed(1)}%`);
  const pct = job.steps ? Math.round((job.step / job.steps) * 100) : 0;
  const stateText = {
    idle: "Not trained yet.",
    loading: "Collecting painted planes...",
    training: `Training: step ${job.step} of ${job.steps} (${pct}%)`,
    done: `Done: ${job.step} steps.`,
    loaded: `Loaded saved model "${job.loadedName}".`,
    stopped: `Stopped at step ${job.step}.`,
    error: `Error: ${job.error}`,
  }[job.state];

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>Training data</h2>
          <div style={styles.headerButtons}>
            <label style={styles.toggle}>
              <input
                type="checkbox"
                checked={showMask}
                onChange={() => setShowMask((v) => !v)}
              />
              Mask
            </label>
            {model === "mlp" && (
              <label style={styles.toggle}>
                <input
                  type="checkbox"
                  checked={showBoxes}
                  onChange={() => setShowBoxes((v) => !v)}
                />
                Patch boxes
              </label>
            )}
            <label style={styles.toggle}>
              <input
                type="checkbox"
                checked={guessAsMask}
                onChange={() => setGuessAsMask((v) => !v)}
              />
              Guess as mask
            </label>
            <button
              style={styles.button}
              onClick={() => load()}
              disabled={loading}
            >
              Show other planes
            </button>
            <button style={styles.button} onClick={onClose}>
              Close
            </button>
          </div>
        </div>

        <div style={styles.body}>
          <div style={styles.panel}>
            <div
              style={{
                display: "flex",
                gap: 14,
                alignItems: "flex-end",
                flexWrap: "wrap",
              }}
            >
              <label style={styles.field}>
                Model
                <select
                  style={{ ...styles.input, width: 150 }}
                  value={model}
                  disabled={running}
                  onChange={(e) => {
                    const m = e.target.value;
                    setModel(m);
                    setSteps(m === "unet" ? 300 : 500); // sensible starting values for each model
                    setLr(m === "unet" ? 0.001 : 0.05);
                    setLoss(m === "unet" ? "bce_dice" : "bce");
                  }}
                >
                  <option value="mlp">MLP (patches)</option>
                  <option value="unet">U-Net (whole planes)</option>
                </select>
              </label>
              {model === "mlp" && (
                <>
                  <label style={styles.field}>
                    Patch size
                    <select
                      style={styles.input}
                      value={patch}
                      disabled={running}
                      onChange={(e) => {
                        const p = Number(e.target.value);
                        setPatch(p);
                        load(p);
                      }}
                    >
                      {[3, 5, 7, 9, 11, 15, 21, 31].map((p) => (
                        <option key={p} value={p}>
                          {p} × {p}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label style={styles.field}>
                    Hidden units
                    <input
                      style={styles.input}
                      type="number"
                      min="1"
                      max="512"
                      value={hidden}
                      disabled={running}
                      onChange={(e) => setHidden(Number(e.target.value))}
                    />
                  </label>
                </>
              )}
              {model === "unet" && (
                <label style={styles.field}>
                  Base channels
                  <select
                    style={styles.input}
                    value={base}
                    disabled={running}
                    onChange={(e) => setBase(Number(e.target.value))}
                  >
                    {[8, 16, 32].map((b) => (
                      <option key={b} value={b}>
                        {b}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label style={styles.field}>
                Steps
                <input
                  style={styles.input}
                  type="number"
                  min="1"
                  max="20000"
                  value={steps}
                  disabled={running}
                  onChange={(e) => setSteps(Number(e.target.value))}
                />
              </label>
              <label style={styles.field}>
                Learning rate
                <input
                  style={styles.input}
                  type="number"
                  step="0.01"
                  min="0.0001"
                  value={lr}
                  disabled={running}
                  onChange={(e) => setLr(Number(e.target.value))}
                />
              </label>
              <label style={styles.field}>
                Loss function
                <select
                  style={{ ...styles.input, width: 150 }}
                  value={loss}
                  disabled={running}
                  onChange={(e) => setLoss(e.target.value)}
                >
                  <option value="bce">Cross-entropy</option>
                  <option value="dice">Dice</option>
                  <option value="tversky">Tversky</option>
                  <option value="bce_dice">Cross-entropy + Dice</option>
                </select>
              </label>
              {loss === "tversky" && (
                <label
                  style={styles.field}
                  title="Penalty for missing painted pixels. Extra pixels are penalized 1 - this value."
                >
                  Tversky β (misses)
                  <input
                    style={styles.input}
                    type="number"
                    step="0.05"
                    min="0.05"
                    max="0.95"
                    value={beta}
                    disabled={running}
                    onChange={(e) => setBeta(Number(e.target.value))}
                  />
                </label>
              )}
              {running ? (
                <button style={styles.button} onClick={stopTraining}>
                  Stop
                </button>
              ) : (
                <button
                  style={styles.primary}
                  onClick={startTraining}
                  disabled={!filename}
                >
                  Train
                </button>
              )}
            </div>

            <div
              style={{
                display: "flex",
                gap: 10,
                alignItems: "flex-end",
                flexWrap: "wrap",
                marginTop: 10,
              }}
            >
              <label style={styles.field}>
                Save current model as
                <input
                  style={{ ...styles.input, width: 170 }}
                  type="text"
                  placeholder="name (optional)"
                  value={saveName}
                  disabled={running || !job.hasModel}
                  onChange={(e) => setSaveName(e.target.value)}
                />
              </label>
              <button
                style={styles.button}
                onClick={saveModel}
                disabled={running || !job.hasModel}
              >
                Save model
              </button>
              <label style={{ ...styles.field, marginLeft: 12 }}>
                Saved models
                <select
                  style={{ ...styles.input, width: 230 }}
                  value={pick}
                  disabled={running || savedModels.length === 0}
                  onChange={(e) => setPick(e.target.value)}
                >
                  {savedModels.length === 0 && (
                    <option value="">none saved yet</option>
                  )}
                  {savedModels.map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.name} · {m.kind === "unet" ? "U-Net" : "MLP"}
                      {m.metric != null
                        ? ` · ${m.kind === "unet" ? m.metric.toFixed(2) : `${(m.metric * 100).toFixed(0)}%`}`
                        : ""}
                    </option>
                  ))}
                </select>
              </label>
              <button
                style={styles.button}
                onClick={loadModel}
                disabled={running || !pick}
              >
                Load model
              </button>
              {pick && !running && (
                <a
                  style={{
                    ...styles.button,
                    textDecoration: "none",
                    display: "inline-block",
                  }}
                  href={`${API}/api/ml/model/download/${encodeURIComponent(pick)}`}
                >
                  Download weights (.pt)
                </a>
              )}
            </div>
            {modelMsg && (
              <p style={{ ...styles.note, margin: "6px 0 0" }}>{modelMsg}</p>
            )}

            <p style={{ ...styles.note, margin: "10px 0 6px" }}>
              <b>
                {filename
                  ? `Training on: ${filename}`
                  : "No image open. Open one in the viewer to train."}
              </b>
              {job.config && job.config.loss && (
                <span>
                  {" "}
                  · {job.config.model === "unet" ? "U-Net" : "MLP"} ·{" "}
                  {
                    {
                      bce: "cross-entropy",
                      dice: "Dice",
                      tversky: `Tversky (β ${job.config.beta})`,
                      bce_dice: "cross-entropy + Dice",
                    }[job.config.loss]
                  }{" "}
                  loss
                </span>
              )}
              <br />
              {stateText}
              {job.state === "training" &&
                job.testAcc != null &&
                `  loss ${job.loss.toFixed(4)}  ·  ${metricName} ${fmtMetric(job.testAcc)}`}
              {job.state !== "training" &&
                job.testAcc != null &&
                job.state !== "error" &&
                `  Final ${metricName} ${fmtMetric(job.testAcc)}`}
            </p>
            {job.info && job.info.planes && (
              <p style={{ ...styles.note, margin: "0 0 6px" }}>
                {job.info.trainPatches
                  ? `${job.info.planes} painted planes · ${job.info.trainPatches} training patches · ${job.info.testPatches} test patches`
                  : `${job.info.planes} painted planes · ${job.info.trainPlanes} training planes · ${job.info.testPlanes} test planes`}
              </p>
            )}
            <LossCurve history={job.history || []} />
            {(job.history || []).length > 1 && (
              <p
                style={{
                  ...styles.note,
                  margin: "4px 0 0",
                  fontSize: "0.78rem",
                }}
              >
                <span style={{ color: "#2563eb" }}>blue: loss</span> ·{" "}
                <span style={{ color: "#16a34a" }}>green: {metricName}</span>
              </p>
            )}
          </div>

          {loading && (
            <p style={styles.note}>
              Loading... the first time can take up to 30 seconds.
            </p>
          )}
          {error && <p style={{ ...styles.note, color: "#b91c1c" }}>{error}</p>}

          {preview && !loading && (
            <>
              <p style={styles.note}>
                {preview.totalPlanes} painted planes found. Images are shrunk{" "}
                {preview.downscale}×. The
                {model === "mlp"
                  ? `network reads one ${preview.patchSize} × ${preview.patchSize} patch at a time and decides whether its center pixel is painted. Green boxes are painted samples, cyan are not painted (true size).`
                  : "U-Net looks at whole planes. During training it sees random 128 × 128 crops that are flipped and rotated."}
              </p>
              {preview.planes.length === 0 && (
                <p style={styles.note}>
                  No painted planes yet. Paint on a few planes or load a mask,
                  then open this again.
                </p>
              )}
              {preview.planes.map((plane, i) => (
                <PlaneRow
                  key={`${plane.filename}-${plane.plane}-${i}`}
                  plane={plane}
                  patchSize={preview.patchSize}
                  showMask={showMask}
                  showBoxes={showBoxes}
                  guessAsMask={guessAsMask}
                  showPatches={model === "mlp"}
                />
              ))}

              {preview.predictions && preview.predictions.length > 0 && (
                <>
                  <h3
                    style={{
                      ...styles.title,
                      margin: "24px 0 4px",
                      borderTop: "2px solid #cbd5e1",
                      paddingTop: 16,
                    }}
                  >
                    Held-out planes
                  </h3>
                  <p style={styles.note}>
                    The network never trained on these planes. Planes with a
                    painting show how closely its guess matches it.
                  </p>
                  {preview.predictions.map((plane, i) => (
                    <PlaneRow
                      key={`pred-${plane.filename}-${plane.plane}-${i}`}
                      plane={plane}
                      patchSize={preview.patchSize}
                      showMask={showMask}
                      showBoxes={false}
                      guessAsMask={guessAsMask}
                    />
                  ))}
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
