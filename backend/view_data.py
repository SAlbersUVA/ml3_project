import matplotlib.pyplot as plt
import numpy as np

import data
import mlp_seg

N_EXAMPLES = 6   # patches shown per strip


def patch_strip(padded, ys, xs):
    """Stack the 7 x 7 patches for the given pixels on top of each other, with a white gap between them."""
    gap = np.ones((1, mlp_seg.PATCH), dtype=np.float32)
    pieces = []
    for y, x in zip(ys, xs):
        pieces.append(padded[y:y + mlp_seg.PATCH, x:x + mlp_seg.PATCH])
        pieces.append(gap)
    return np.vstack(pieces[:-1])

def show_samples(samples, n_planes=3):
    n_planes = min(n_planes, len(samples))
    fig, axes = plt.subplots(n_planes, 4, figsize=(15, 4 * n_planes), squeeze=False)
    half = mlp_seg.HALF

    for row, sample in enumerate(np.random.permutation(len(samples))[:n_planes]):
        s = samples[sample]
        img = s["img"].astype(np.float32)
        mask = s["mask"]
        padded = np.pad(img, half, mode="reflect")

        fg_y, fg_x = s["fg"]
        pick = np.random.choice(len(fg_y), min(N_EXAMPLES, len(fg_y)), replace=False)
        py, px = fg_y[pick], fg_x[pick]
        bg_y, bg_x = np.nonzero(mask == 0)
        pick = np.random.choice(len(bg_y), min(N_EXAMPLES, len(bg_y)), replace=False)
        uy, ux = bg_y[pick], bg_x[pick]

        ax = axes[row, 0]
        ax.imshow(img, cmap="gray", vmin=0, vmax=1)
        ax.set_title(f"downsampled plane {img.shape[1]} x {img.shape[0]}")

        ax = axes[row, 1]
        ax.imshow(img, cmap="gray", vmin=0, vmax=1)
        ax.imshow(np.ma.masked_equal(mask, 0), cmap="autumn", alpha=0.45)
        for ys, xs, color in ((py, px, "lime"), (uy, ux, "cyan")):
            for y, x in zip(ys, xs):
                ax.add_patch(plt.Rectangle((x - half - 0.5, y - half - 0.5), mlp_seg.PATCH, mlp_seg.PATCH,
                                           fill=False, edgecolor=color, linewidth=1.5))
        ax.set_title("painted area (orange); sampled patches\ngreen = painted, cyan = not (true size)")

        ax = axes[row, 2]
        ax.imshow(patch_strip(padded, py, px), cmap="gray", vmin=0, vmax=1, interpolation="nearest")
        ax.set_title(f"{len(py)} painted patches ({mlp_seg.PATCH} x {mlp_seg.PATCH} pixels each)")

        ax = axes[row, 3]
        ax.imshow(patch_strip(padded, uy, ux), cmap="gray", vmin=0, vmax=1, interpolation="nearest")
        ax.set_title(f"{len(uy)} not-painted patches")

        for col in (2, 3):
            axes[row, col].set_xticks([])
            axes[row, col].set_yticks([])

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    import app

    samples = data.collect_annotation_samples(app.DB_PATH, app.load_volume)
    print(len(samples), "painted planes found")
    show_samples(samples)