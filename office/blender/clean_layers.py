"""레이어 투명도 정리: 그림자 잡이의 옅은 잡음(상자처럼 보임)을 지우고 진한 그림자·인형만 남긴다."""
import sys, json, os
from PIL import Image, ImageFilter
import numpy as np
D = sys.argv[1]
for f in sorted(os.listdir(D)):
    if not f.endswith(".png") or f.startswith("bg"): continue
    im = Image.open(os.path.join(D, f)).convert("RGBA"); a = np.array(im).astype(float)
    al = a[..., 3]; lum = a[..., :3].mean(axis=2)
    core = al > 200
    ring = np.array(Image.fromarray((core * 255).astype("uint8")).filter(ImageFilter.MaxFilter(5))) > 0
    doll = core | (ring & (al > 0) & (a[..., :3].mean(axis=2) >= 60))   # 인형 가장자리(부드러운 테두리)도 인형으로
    near = np.array(Image.fromarray((doll * 255).astype("uint8")).filter(ImageFilter.MaxFilter(int(sys.argv[2]) if len(sys.argv) > 2 else 41))) > 0
    shadow = (~doll) & (lum < 60) & (al > 70) & near   # 인형 발밑 가까이의 해 그림자만
    keep = doll | shadow
    m = Image.fromarray((keep * 255).astype("uint8")).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    mk = np.array(m).astype(float) / 255
    sh = np.array(Image.fromarray((np.where(shadow, al, 0)).astype("uint8")).filter(ImageFilter.GaussianBlur(2.5))).astype(float)
    a[..., :3] = np.where(doll[..., None], a[..., :3], 20)                 # 그림자 색은 짙은 회색 하나로
    a[..., 3] = np.where(doll, al, sh * 0.55)                              # 그림자는 부드럽고 옅게
    Image.fromarray(a.clip(0, 255).astype("uint8")).save(os.path.join(D, f))
print("cleaned", D)
