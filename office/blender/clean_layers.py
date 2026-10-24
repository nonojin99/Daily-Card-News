"""레이어 투명도 정리: 그림자 잡이의 옅은 잡음(상자처럼 보임)을 지우고 진한 그림자·인형만 남긴다."""
import sys, json, os
from PIL import Image, ImageFilter
import numpy as np
D = sys.argv[1]
for f in sorted(os.listdir(D)):
    if not f.endswith(".png") or f.startswith("bg"): continue
    im = Image.open(os.path.join(D, f)).convert("RGBA"); a = np.array(im).astype(float)
    al = a[..., 3]; lum = a[..., :3].mean(axis=2)
    doll = al > 200
    near = np.array(Image.fromarray((doll * 255).astype("uint8")).filter(ImageFilter.MaxFilter(int(sys.argv[2]) if len(sys.argv) > 2 else 41))) > 0
    shadow = (~doll) & (lum < 60) & (al > 70) & near   # 인형 발밑 가까이의 해 그림자만
    keep = doll | shadow
    m = Image.fromarray((keep * 255).astype("uint8")).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    mk = np.array(m).astype(float) / 255
    a[..., 3] = np.where(doll, al, np.where(shadow, al * 0.85, al * mk * 0.0)) * np.maximum(mk, doll)
    Image.fromarray(a.clip(0, 255).astype("uint8")).save(os.path.join(D, f))
print("cleaned", D)
