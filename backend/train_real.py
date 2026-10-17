

import app
import data
import mlp_seg

# url = "http://localhost:5000/api/directory"
# app.DATA_DIR = json.load(urllib.request.urlopen(url))["path"]
# print("using folder:", app.DATA_DIR)

samples = data.collect_annotation_samples(app.DB_PATH, app.load_volume)
print(len(samples), "painted planes found")

X_train, y_train, X_test, y_test = mlp_seg.build_dataset(samples)
print("training patches:", len(X_train), " test patches:", len(X_test))

params, history = mlp_seg.train(X_train, y_train, X_test, y_test)

import numpy as np
import matplotlib.pyplot as plt

s = samples[0]                         # one of the held-out test planes
guess = mlp_seg.predict_map(params, s["img"])

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
axes[0].imshow(s["img"], cmap="gray");  axes[0].set_title("image")
axes[1].imshow(s["mask"], cmap="gray"); axes[1].set_title("painted")
axes[2].imshow(guess, cmap="gray", vmin=0, vmax=1); axes[2].set_title("network guess")
for a in axes:
    a.axis("off")
plt.tight_layout()
plt.savefig("prediction.png", dpi=120)
print("saved prediction.png")