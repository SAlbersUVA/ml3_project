import torch
import torch.nn as nn
import torch.nn.functional as F

class doubleconv(nn.Module):
    def __init__(self, c_in, c_out):
        super().__init__()
        self.net=nn.Sequential(
            nn.Conv2d(c_in, c_out, 3, padding=1),
            nn.BatchNorm2d(c_out),
            nn.ReLU(inplace=True),
            nn.Conv2d(c_out, c_out, 3, padding=1),
            nn.BatchNorm2d(c_out),
            nn.ReLU(inplace=True),
        )
    def forward(self,x):
        return self.net(x)


class UNet(nn.Module):
    def __init__(self, base=16):
        super().__init__()
        self.d1=doubleconv(1, base)
        self.d2=doubleconv(base,base*2)
        self.d3=doubleconv(base*2,base*4)
        self.bottom=doubleconv(base*4, base*8)
        self.up3=nn.ConvTranspose2d(base*8, base*4, 2, stride=2)
        self.u3=doubleconv(base*8, base*4)
        self.up2=nn.ConvTranspose2d(base*4, base*2, 2, stride=2)
        self.u2 = doubleconv(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.u1 = doubleconv(base * 2, base)
        self.out = nn.Conv2d(base, 1, 1)

    def forward(self, x):
        c1 = self.d1(x)
        c2 = self.d2(F.max_pool2d(c1, 2))
        c3 = self.d3(F.max_pool2d(c2, 2))
        b = self.bottom(F.max_pool2d(c3, 2))
        x = self.u3(torch.cat([self.up3(b), c3], 1))
        x = self.u2(torch.cat([self.up2(x), c2], 1))
        x = self.u1(torch.cat([self.up1(x), c1], 1))
        return self.out(x)

def dice_loss(logits, target):
    """0 when the predicted mask matches the painted mask perfectly, up to 1 when it doesn't overlap."""
    p = torch.sigmoid(logits)
    inter = (p * target).sum((1, 2, 3))
    denom = p.sum((1, 2, 3)) + target.sum((1, 2, 3))
    return 1 - ((2 * inter + 1) / (denom + 1)).mean()

