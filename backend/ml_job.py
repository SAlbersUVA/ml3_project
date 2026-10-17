"""Runs training in a background thread so the web app stays responsive."""

import threading

import numpy as np

import data
import losses
import mlp_seg

_lock = threading.Lock()
_stop = threading.Event()
_model = {"predict": None, "kind": None, "object": None, "config": {}, "test_keys": set(), "painted_keys": set()}

_job = {
    "state": "idle",      # idle | loading | training | done | stopped | error
    "step": 0,
    "steps": 0,
    "loss": None,
    "testAcc": None,
    "history": [],        # [{"step", "loss", "acc"}], one entry every 10 steps
    "loadedName": "",     # set when a saved model was loaded instead of trained
    "config": {},
    "info": {},
    "error": "",
}


def status():
    with _lock:
        return {**_job, "history": list(_job["history"]), "hasModel": _model["predict"] is not None}


def _set(**changes):
    with _lock:
        _job.update(changes)


def start(db_path, load_volume, patch, hidden, steps, lr, filename=None, model="mlp", base=16,
          loss=None, beta=0.7):
    with _lock:
        if _job["state"] in ("loading", "training"):
            raise RuntimeError("Training is already running.")
    if not filename:
        raise RuntimeError("Open an image in the viewer first, then train.")
    patch = max(3, min(31, patch)) // 2 * 2 + 1      # odd, between 3 and 31
    hidden = max(1, min(512, hidden))
    steps = max(1, min(20000, steps))
    model = "unet" if model == "unet" else "mlp"
    base = max(4, min(64, base))
    if loss not in losses.LOSSES:
        loss = "bce_dice" if model == "unet" else "bce"
    beta = max(0.05, min(0.95, beta))
    config = {"model": model, "patch": patch, "hidden": hidden, "base": base,
              "steps": steps, "lr": lr, "filename": filename,
              "loss": loss, "beta": beta}

    _stop.clear()
    _set(state="loading", step=0, steps=steps, loss=None, testAcc=None,
         history=[], config=config, info={}, error="")
    threading.Thread(target=_run, args=(db_path, load_volume, config), daemon=True).start()


def stop():
    _stop.set()


def _run(db_path, load_volume, config):
    try:
        samples = data.collect_annotation_samples(db_path, load_volume, filename=config["filename"])
        if len(samples) < 2:
            raise ValueError("Paint at least 2 planes: one to learn from and one to test on.")

        loss_fn = losses.get_loss(config["loss"], config["beta"])
        if config["model"] == "mlp" and config["loss"] == "bce":
            loss_fn = None    # the MLP uses its own hand-written cross-entropy from mlp_seg.py

        def on_step(step, loss, score):
            with _lock:
                _job.update(step=step, loss=loss, testAcc=score)
                _job["history"].append({"step": step, "loss": loss, "acc": score})

        if config["model"] == "mlp":
            mlp_seg.configure(config["patch"], config["hidden"])
            X_train, y_train, X_test, y_test = mlp_seg.build_dataset(samples)   # test planes come first
            n_test = max(1, len(samples) // 5)
            info = {"planes": len(samples), "trainPatches": len(X_train), "testPatches": len(X_test)}
            _set(state="training", info=info)
            params, _ = mlp_seg.train(X_train, y_train, X_test, y_test,
                                      steps=config["steps"], lr=config["lr"], loss_fn=loss_fn,
                                      on_step=on_step, should_stop=_stop.is_set)
            trained = params
            predict = lambda img: mlp_seg.predict_map(params, img)
        else:
            import unet_train    # imported here so the U-Net code only loads when it is used
            np.random.shuffle(samples)
            n_test = max(1, len(samples) // 5)
            test_samples, train_samples = samples[:n_test], samples[n_test:]
            _set(state="training", info={"planes": len(samples), "trainPlanes": len(train_samples),
                                         "testPlanes": len(test_samples)})
            net = unet_train.train_unet(train_samples, test_samples, steps=config["steps"],
                                        lr=config["lr"], base=config["base"], loss_fn=loss_fn,
                                        on_step=on_step, should_stop=_stop.is_set)
            trained = net
            predict = lambda img: unet_train.predict_unet(net, img)

        _model.update(predict=predict, kind=config["model"], object=trained, config=config)
        _set(loadedName="")
        _model["test_keys"] = {(s["filename"], s["plane"]) for s in samples[:n_test]}
        _model["painted_keys"] = {(s["filename"], s["plane"]) for s in samples}
        _set(state="stopped" if _stop.is_set() else "done")
    except Exception as e:
        _set(state="error", error=str(e))


def guess_fn():
    """A function that turns one downsampled image into the network's 0..1 guess, or None if untrained."""
    return _model["predict"]


def test_keys():
    return _model["test_keys"]


def painted_keys():
    return _model["painted_keys"]


def save_model(name, copy_dir=None):
    """Write the current model (just trained, or just loaded) to backend/saved_models/."""
    import model_store
    if _model["predict"] is None:
        raise RuntimeError("Train or load a model first.")
    if _model["kind"] == "mlp":
        weights = [p.detach().clone() for p in _model["object"]]
    else:
        weights = {k: v.detach().clone() for k, v in _model["object"].state_dict().items()}
    with _lock:
        metric, history = _job["testAcc"], list(_job["history"])
    saved, paths = model_store.save(name, _model["kind"], weights, _model["config"], metric, history,
                                    _model["test_keys"], _model["painted_keys"], copy_dir)
    _set(loadedName=saved)
    return saved, paths


def load_model(name):
    """Replace the current model with a saved one. No training needed."""
    import model_store
    with _lock:
        if _job["state"] in ("loading", "training"):
            raise RuntimeError("Wait for training to finish, or stop it, before loading a model.")
    checkpoint, info = model_store.load(name)
    kind, config = checkpoint["kind"], checkpoint["config"]

    if kind == "mlp":
        params = [t.clone().requires_grad_() for t in checkpoint["weights"]]
        obj, predict = params, (lambda img: mlp_seg.predict_map(params, img))
    else:
        import unet_train
        from unet import UNet
        net = UNet(base=config["base"])
        net.load_state_dict(checkpoint["weights"])
        net.eval()
        obj, predict = net, (lambda img: unet_train.predict_unet(net, img))

    _model.update(predict=predict, kind=kind, object=obj, config=config,
                  test_keys={tuple(k) for k in checkpoint["test_keys"]},
                  painted_keys={tuple(k) for k in checkpoint["painted_keys"]})
    _set(state="loaded", config=config, testAcc=info["metric"], history=info["history"],
         step=0, steps=0, loss=None, info={}, error="", loadedName=info["name"])
    return info["name"]