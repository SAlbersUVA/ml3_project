"""Train the U-Net on whole painted planes (random crops, flips and rotations)."""

import numpy as np
import torch

from losses import get_loss
from unet import UNet

CROP = 128    # train on 128 x 128 crops: fast on a CPU, and every crop is a different view
BATCH = 8


def make_batch_arrays(train_samples):
    """Pick BATCH random planes, cut a random square crop from each, flip and rotate it."""
    imgs, masks = [], []
    for _ in range(BATCH):
        s = train_samples[np.random.randint(len(train_samples))]
        img = s["img"].astype(np.float32)
        mask = s["mask"].astype(np.float32)
        h, w = img.shape
        c = min(CROP, h // 8 * 8, w // 8 * 8)            # the U-Net needs sizes divisible by 8
        y = np.random.randint(0, h - c + 1)
        x = np.random.randint(0, w - c + 1)
        img, mask = img[y:y + c, x:x + c], mask[y:y + c, x:x + c]
        k = np.random.randint(4)                         # rotate by 0, 90, 180 or 270 degrees
        img, mask = np.rot90(img, k), np.rot90(mask, k)
        if np.random.rand() < 0.5:                       # mirror left-right half of the time
            img, mask = img[:, ::-1], mask[:, ::-1]
        imgs.append(img.copy())
        masks.append(mask.copy())
    return np.stack(imgs)[:, None], np.stack(masks)[:, None]


def predict_unet(model, img):
    """Run the U-Net on one whole plane. Returns a 0..1 map the same size as the image."""
    img = img.astype(np.float32)
    h, w = img.shape
    padded = np.pad(img, ((0, (-h) % 8), (0, (-w) % 8)), mode="reflect")   # 300 -> 304
    model.eval()
    with torch.no_grad():
        out = torch.sigmoid(model(torch.from_numpy(padded)[None, None]))[0, 0].numpy()
    return out[:h, :w]


def mean_dice(model, samples):
    """Average Dice score on whole planes (1 = the guess matches the painting exactly)."""
    scores = []
    for s in samples:
        guess = predict_unet(model, s["img"]) >= 0.5
        truth = s["mask"] > 0
        total = guess.sum() + truth.sum()
        scores.append(1.0 if total == 0 else 2 * (guess & truth).sum() / total)
    return float(np.mean(scores))


def train_unet(train_samples, test_samples, steps=300, lr=0.001, base=16,
               loss_fn=None, on_step=None, should_stop=None):
    """Train with Adam. Each step: forward, loss, backprop, update, on a fresh random batch."""
    loss_fn = loss_fn or get_loss("bce_dice")
    torch.manual_seed(0)
    model = UNet(base=base)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    for step in range(1, steps + 1):
        if should_stop and should_stop():
            print(f"stopped at step {step}")
            break

        model.train()
        x, y = make_batch_arrays(train_samples)
        x, y = torch.from_numpy(x), torch.from_numpy(y)

        logits = model(x)                                              # forward pass
        loss = loss_fn(logits, y)
        optimizer.zero_grad()
        loss.backward()                                                # backpropagation
        optimizer.step()                                               # update the weights

        if step == 1 or step % 10 == 0 or step == steps:
            score = mean_dice(model, test_samples)
            if on_step:
                on_step(step, loss.item(), score)
            print(f"step {step:4d}   train loss {loss.item():.4f}   test Dice {score:.3f}")

    model.eval()
    return model