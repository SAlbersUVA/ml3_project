import numpy as np
import torch
from numpy.lib.stride_tricks import sliding_window_view

PATCH = 31                  # each pixel is described by the 7 x 7 square around it
HALF = PATCH // 2          # 3 pixels on each side of the center
PIXELS_PER_PLANE = 2000    # how many pixels we pull from each painted plane

def configure(patch, hidden):
    """Change the patch size and hidden-layer size before building data and training."""
    global PATCH, HALF, N_INPUT, N_HIDDEN
    PATCH = patch
    HALF = patch // 2
    N_INPUT = patch * patch
    N_HIDDEN = hidden


def get_patches(sample, n):
    """Pick about n pixels from one plane (half painted, half not) and cut out their patches.
    Returns patches of shape (n, 49) and labels of shape (n, 1)."""
    img = sample["img"].astype(np.float32)
    mask = sample["mask"]

    # pad the edges so pixels near the border still have a full 7 x 7 neighborhood
    padded = np.pad(img, HALF, mode="reflect")

    # painted pixels (label 1)
    fg_y, fg_x = sample["fg"]
    n_fg = min(n // 2, len(fg_y))
    pick = np.random.choice(len(fg_y), n_fg, replace=False)
    ys, xs = fg_y[pick], fg_x[pick]

    # unpainted pixels (label 0), the same number as painted
    bg_y, bg_x = np.nonzero(mask == 0)
    pick = np.random.choice(len(bg_y), min(n_fg, len(bg_y)), replace=False)
    ys = np.concatenate([ys, bg_y[pick]])
    xs = np.concatenate([xs, bg_x[pick]])
    labels = np.concatenate([np.ones(n_fg), np.zeros(len(pick))])

    # cut the patches: rows ys..ys+6 and columns xs..xs+6 of the padded image
    offsets = np.arange(PATCH)
    rows = ys[:, None, None] + offsets[None, :, None]
    cols = xs[:, None, None] + offsets[None, None, :]
    patches = padded[rows, cols].reshape(len(ys), PATCH * PATCH)

    return patches.astype(np.float32), labels.astype(np.float32)[:, None]


def build_dataset(samples):
    """Turn painted planes into training and test sets. The split is by plane, not by pixel,
    because neighboring pixels look alike and would leak between the two sets."""
    if len(samples) < 2:
        raise ValueError("Paint at least 2 planes: one to learn from and one to test on.")

    np.random.shuffle(samples)
    n_test = max(1, len(samples) // 5)
    test_samples, train_samples = samples[:n_test], samples[n_test:]

    def collect(group):
        parts = [get_patches(s, PIXELS_PER_PLANE) for s in group]
        X = np.concatenate([p[0] for p in parts])
        y = np.concatenate([p[1] for p in parts])
        return torch.from_numpy(X), torch.from_numpy(y)

    X_train, y_train = collect(train_samples)
    X_test, y_test = collect(test_samples)
    return X_train, y_train, X_test, y_test

N_INPUT = PATCH * PATCH   # 961 numbers go in
N_HIDDEN = 32             # the hidden layer has 32 units


def init_params():
    """Create the network's weights and biases with small random starting values."""
    torch.manual_seed(0)  # same starting values every run, so results are repeatable

    W1 = (torch.randn(N_INPUT, N_HIDDEN) * 0.1).requires_grad_()  # input -> hidden
    b1 = torch.zeros(N_HIDDEN, requires_grad=True)                # hidden biases
    W2 = (torch.randn(N_HIDDEN, 1) * 0.1).requires_grad_()        # hidden -> output
    b2 = torch.zeros(1, requires_grad=True)                       # output bias

    return W1, b1, W2, b2

def forward(X, params):
    """Run patches through the network. X has shape (N, 49); the result has shape (N, 1)."""
    W1, b1, W2, b2 = params
    hidden = torch.relu(X @ W1 + b1)   # (N, 49) x (49, 32) -> (N, 32)
    logits = hidden @ W2 + b2          # (N, 32) x (32, 1)  -> (N, 1)
    return logits

def bce_loss(logits, y):
    """Binary cross-entropy: how far the predicted probabilities are from the true 0/1 labels."""
    p = torch.sigmoid(logits)   # squash raw scores into probabilities between 0 and 1
    eps = 1e-7                  # keeps log() away from log(0)
    loss = -(y * torch.log(p + eps) + (1 - y) * torch.log(1 - p + eps))
    return loss.mean()          # average over all patches

def compute_gradients(params, X, y, loss_fn=None):
    """Run the network, measure the loss, and work out how the loss depends on every parameter."""
    loss_fn = loss_fn or bce_loss          # your hand-written cross-entropy is the default
    for p in params:
        p.grad = None                      # clear gradients left over from the previous step

    loss = loss_fn(forward(X, params), y)  # forward pass + loss
    loss.backward()                        # backpropagation: fills in p.grad for every parameter
    return loss.item()

def update_params(params, lr):
    """Nudge every parameter a small step in the direction that lowers the loss."""
    with torch.no_grad():
        for p in params:
            p -= lr * p.grad

def accuracy(params, X, y):
    """Fraction of patches the network labels correctly (probability above 0.5 counts as painted)."""
    with torch.no_grad():
        predicted = (torch.sigmoid(forward(X, params)) > 0.5).float()
        return (predicted == y).float().mean().item()


def train(X_train, y_train, X_test, y_test, steps=500, lr=0.05, on_step=None, should_stop=None):
    """Train the network with plain gradient descent. Returns the learned parameters and loss history."""
    params = init_params()
    history = []

    for step in range(1, steps + 1):
        if should_stop and should_stop():                    # the Stop button was pressed
            print(f"stopped at step {step}")
            break

        loss = compute_gradients(params, X_train, y_train, loss_fn)   # forward, loss, backward

        if step == 1 or step % 10 == 0 or step == steps:
            test_acc = accuracy(params, X_test, y_test)
            if on_step:
                on_step(step, loss, test_acc)                # report progress to the web app
            if step == 1 or step % 50 == 0:
                print(f"step {step:4d}   train loss {loss:.4f}   test accuracy {test_acc:.3f}")

        if len(history) > 1 and abs(history[-2] - loss) < 1e-7:
            print(f"converged at step {step}")
            break

    return params, history

def predict_map(params, small_img):
    """Run the network on every pixel of one plane. Returns a 0..1 map the same size as the image."""
    patch = int(round(params[0].shape[0] ** 0.5))    # W1 has patch*patch rows
    half = patch // 2
    img = small_img.astype(np.float32)
    padded = np.pad(img, half, mode="reflect")
    windows = sliding_window_view(padded, (patch, patch))        # (h, w, patch, patch)
    h, w = img.shape
    X = windows.reshape(h * w, patch * patch)
    out = []
    with torch.no_grad():
        for i in range(0, len(X), 10000):                        # chunks keep memory small
            logits = forward(torch.from_numpy(np.ascontiguousarray(X[i:i + 10000])), params)
            out.append(torch.sigmoid(logits).numpy().ravel())
    return np.concatenate(out).reshape(h, w)