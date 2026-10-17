"""Loss functions. Each takes raw scores (logits) and 0/1 targets, and returns one number to minimize."""

import torch
import torch.nn.functional as F

SMOOTH = 1.0   # keeps the Dice and Tversky fractions away from 0 / 0 on empty crops


def _counts(logits, target):
    """Soft true positives, false positives and false negatives.
    Images (N, 1, H, W) are scored one image at a time; a flat batch of patches is scored as one set."""
    p = torch.sigmoid(logits)
    dims = (1, 2, 3) if p.dim() == 4 else tuple(range(p.dim()))
    tp = (p * target).sum(dims)           # painted, and guessed painted
    fp = (p * (1 - target)).sum(dims)     # not painted, but guessed painted
    fn = ((1 - p) * target).sum(dims)     # painted, but guessed not painted
    return tp, fp, fn


def bce_loss(logits, target):
    """Binary cross-entropy: every pixel counts equally."""
    return F.binary_cross_entropy_with_logits(logits, target)


def tversky_loss(logits, target, beta=0.7):
    """Tversky loss. beta is the penalty for missing painted pixels, alpha = 1 - beta for extra ones.
    beta above 0.5 pushes the network to find more of the painted area."""
    alpha = 1 - beta
    tp, fp, fn = _counts(logits, target)
    return (1 - (tp + SMOOTH) / (tp + alpha * fp + beta * fn + SMOOTH)).mean()


def dice_loss(logits, target):
    """Dice loss. This is Tversky with both penalties equal (beta = 0.5)."""
    return tversky_loss(logits, target, beta=0.5)


LOSSES = ("bce", "dice", "tversky", "bce_dice")


def get_loss(name, beta=0.7):
    if name == "dice":
        return dice_loss
    if name == "tversky":
        return lambda logits, target: tversky_loss(logits, target, beta)
    if name == "bce_dice":
        return lambda logits, target: bce_loss(logits, target) + dice_loss(logits, target)
    return bce_loss