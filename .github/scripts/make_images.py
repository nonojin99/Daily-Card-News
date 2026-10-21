#!/usr/bin/env python3
"""카드용 AI 생성 일러스트를 만든다 (Gemini API).

브리프 카드의 <div class="cn" hidden> 안에 <p class="cn-img">영문 장면 묘사</p> 가 있고 아직 이미지가 없으면
고정 화풍 문구를 붙여 이미지를 만들고 img/gen/YYYY-MM/<브리프 이름>/NN.jpg 로 저장한 뒤
같은 .cn 안에 <img class="cn-gen" loading="lazy" ...> 를 넣는다. 브리프 본문에는 보이지 않고 카드 넘겨보기에서만 쓴다.

안전장치
- 분야 태그(.topic)가 사건·사고·재난·정치 등이면 프롬프트가 있어도 만들지 않는다.
- 화풍 문구로 글자·로고·실존 인물·사진풍을 막는다. 생성 이미지는 SynthID 워터마크가 들어 있다.
- 한 번에 IMAGE_MAX(기본 8)장까지. 키가 없거나 실패하면 건너뛴다 — 카드는 정보 그림/글자 타일로 남는다.
"""
import base64, datetime, io, json, os, re, sys, urllib.request, urllib.error

KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.environ.get("IMAGE_MODEL", "gemini-3.1-flash-lite-image").strip()
MAX_N = int(os.environ.get("IMAGE_MAX", "8"))
DAYS = int(os.environ.get("IMAGE_DAYS", "3"))
FORCE = os.environ.get("IMAGE_FORCE", "").strip()
OUT = os.environ.get("GEN_OUT", "")
P = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_([a-z]+)-brief\.html$")
BANNED = re.compile(r"사건|사고|재난|참사|화재|범죄|전쟁|분쟁|정치|선거|재판|부고|지진|태풍|폭우|테러|안보|군사")
STYLE = ("Flat editorial illustration with soft paper grain, simple geometric shapes, calm composition with generous negative space, "
         "muted palette built around {accent} with cream, deep ink navy and a warm orange accent. "
         "Absolutely no text, letters, numbers, signage, logos or watermarks. No recognizable real people and no close-up faces. "
         "Not photorealistic and not a news photograph. Wide 16:9 landscape.")


def call(prompt):
    """generateContent 를 먼저, 안 되면 interactions 엔드포인트를 쓴다. JPEG/PNG 바이트를 돌려준다."""
    hdr = {"x-goog-api-key": KEY, "Content-Type": "application/json"}
    tries = [
        (f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
         {"contents": [{"parts": [{"text": prompt}]}],
          "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}}),
        ("https://generativelanguage.googleapis.com/v1beta/interactions",
         {"model": MODEL, "input": [{"type": "text", "text": prompt}],
          "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": "16:9", "image_size": "1K"}}),
    ]
    last = None
    for url, body in tries:
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=hdr, method="POST")
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            last = f"{e.code} {e.read()[:300]!r}"
            continue
        except Exception as e:  # noqa: BLE001
            last = str(e)
            continue
        for c in data.get("candidates", []):
            for part in c.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"])
        if (data.get("output_image") or {}).get("data"):
            return base64.b64decode(data["output_image"]["data"])
        for st in data.get("steps", []):
            for blk in st.get("content", []) if isinstance(st.get("content"), list) else []:
                if blk.get("type") == "image" and blk.get("data"):
                    return base64.b64decode(blk["data"])
        last = "no image in response: " + json.dumps(data)[:300]
    raise RuntimeError(last)


def save(raw, path):
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = im.size
    tw, th = (w, round(w * 10 / 16)) if w / h < 16 / 10 else (round(h * 16 / 10), h)
    left, top = (w - tw) // 2, (h - th) // 2
    im = im.crop((left, top, left + tw, top + th)).resize((1280, 800), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, "JPEG", quality=85, optimize=True, progressive=True)


def main():
    if not KEY:
        print("images: GEMINI_API_KEY not set — skip")
        return
    today = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    cutoff = (today - datetime.timedelta(days=DAYS)).strftime("%Y-%m-%d")
    made, n = [], 0
    # drafts/ — 시안: 같은 형식의 HTML 을 drafts/ 에 두면 그림만 만든다(앱·manifest 에는 안 보인다, README '카드 그림 우선순위')
    names = [(".", n) for n in sorted(os.listdir("."))] + [("drafts", n) for n in (sorted(os.listdir("drafts")) if os.path.isdir("drafts") else [])]
    for folder, name in names:
        m = P.match(name)
        if not m or (FORCE and name != FORCE) or (not FORCE and f"{m[1]}-{m[2]}-{m[3]}" < cutoff):
            continue
        fpath = name if folder == "." else f"{folder}/{name}"
        if m[4] == "sports":   # 스포츠는 실존 선수·팀·경기 장면이 되므로 만들지 않는다
            continue
        html = open(fpath, encoding="utf-8").read()
        accent = (re.search(r"--accent:\s*(#[0-9a-fA-F]{6})", html) or [None, "#3d5a4c"])[1]
        changed = False
        arts = list(re.finditer(r'<article class="card">.*?</article>', html, re.S))
        for idx, a in reversed(list(enumerate(arts, 1))):
            block = a.group(0)
            cn = re.search(r'<div class="cn" hidden>.*?</div>', block, re.S)
            pm = cn and re.search(r'<p class="cn-img">(.*?)</p>', cn.group(0), re.S)
            if not pm or 'class="cn-gen"' in cn.group(0):
                continue
            topic = re.sub(r"<[^>]+>", "", (re.search(r'<span class="topic">(.*?)</span>', block, re.S) or [None, ""])[1])
            if BANNED.search(topic):
                print(f"images: skip {name} #{idx} — topic '{topic}' is not allowed")
                continue
            if n >= MAX_N:
                print("images: IMAGE_MAX reached")
                break
            scene = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", pm.group(1))).strip()
            rel = f"img/gen/{m[1]}-{m[2]}/{'' if folder == '.' else 'drafts-'}{name[:-5]}/{idx:02d}.jpg"
            try:
                save(call(scene + ". " + STYLE.format(accent=accent)), rel)
            except Exception as e:  # noqa: BLE001
                print(f"::warning::image failed for {name} #{idx}: {e}")
                continue
            n += 1
            made.append(rel)
            tag = f'\n      <img class="cn-gen" loading="lazy" src="{rel}" alt="AI 생성 일러스트">'
            new_block = block.replace(pm.group(0), pm.group(0) + tag, 1)
            html = html[:a.start()] + new_block + html[a.end():]
            changed = True
            print(f"images: {fpath} #{idx} → {rel}")
        if changed:
            open(fpath, "w", encoding="utf-8").write(html)
            made.append(fpath)
    if OUT and made:
        with open(OUT, "w", encoding="utf-8") as fp:
            fp.write("\n".join(made) + "\n")


if __name__ == "__main__":
    main()
