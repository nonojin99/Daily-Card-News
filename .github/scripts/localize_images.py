#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
브리프 HTML 안의 원격 이미지를 저장소로 내려받아 로컬 경로로 바꾼다.

  대상  <img ... src="https://..." data-remote="https://..."> 중 src 가 아직 원격인 것
  저장  <HTML 이 있는 폴더>/img/<YYYY-MM-DD>/<파일명>
  교체  src 만 로컬 상대경로로 바꾸고, data-remote 는 출처 추적용으로 남긴다

실패 원칙
  - 어떤 이미지든 실패하면 그 이미지는 건드리지 않는다 → 핫링크로 계속 보인다
  - 스크립트는 빌드를 실패시키지 않는다(항상 exit 0)

허용 호스트는 라이선스를 이미지 페이지에서 직접 확인한 곳만 둔다.
  cdn.esawebb.org    ESA/Webb   CC BY 4.0 — 크레디트 문구 그대로 표기
  cdn.esahubble.org  ESA/Hubble CC BY 4.0 — 크레디트 문구 그대로 표기
NASA 이미지 라이브러리(images.nasa.gov)는 페이지가 JS 로 그려져 무인 실행에서
크레디트·제3자 표시를 확인할 수 없어 넣지 않았다.
"""
import html, os, re, sys, urllib.parse, urllib.request

ALLOWED_HOSTS = {"cdn.esawebb.org", "cdn.esahubble.org"}
# screen JPEG 는 약 400KB, publication 은 약 3MB. 같은 이미지의 large JPEG 는
# 286MB 인 사례를 확인했다 — 실수로 그 URL 이 들어와도 저장소에 커밋되지 않게 막는다.
MAX_BYTES = 8 * 1024 * 1024
MAX_WIDTH = 1600
TIMEOUT = 30

IMG_TAG = re.compile(r"<img\b[^>]*>", re.I | re.S)
ATTR = r'\b{}\s*=\s*"([^"]*)"'
DATE_IN_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_")
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")

MAGIC = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF8", ".gif"),
)


def attr(tag, name):
    m = re.search(ATTR.format(re.escape(name)), tag, re.I)
    return html.unescape(m.group(1)) if m else None


def sniff(data):
    for sig, ext in MAGIC:
        if data.startswith(sig):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def allowed(url):
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and (p.hostname or "").lower() in ALLOWED_HOSTS


def fetch(url):
    """원격 이미지 바이트를 가져온다. 상한을 넘으면 중간에 끊는다."""
    req = urllib.request.Request(url, headers={"User-Agent": "Daily-Card-News image localizer"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        ctype = r.headers.get("Content-Type", "")
        if not ctype.lower().startswith("image/"):
            raise ValueError(f"이미지가 아님: Content-Type={ctype!r}")
        declared = r.headers.get("Content-Length")
        if declared and int(declared) > MAX_BYTES:
            raise ValueError(f"용량 초과(선언): {int(declared):,} bytes")
        buf = r.read(MAX_BYTES + 1)
    if len(buf) > MAX_BYTES:
        raise ValueError(f"용량 초과(실측): {MAX_BYTES:,} bytes 이상")
    return buf


def shrink(data, ext):
    """폭이 MAX_WIDTH 를 넘으면 줄인다. Pillow 가 없거나 실패하면 원본 그대로."""
    try:
        from io import BytesIO
        from PIL import Image
    except ImportError:
        return data
    try:
        im = Image.open(BytesIO(data))
        if im.width <= MAX_WIDTH:
            return data
        h = round(im.height * MAX_WIDTH / im.width)
        im = im.resize((MAX_WIDTH, h), Image.LANCZOS)
        out = BytesIO()
        if ext == ".jpg":
            im.convert("RGB").save(out, "JPEG", quality=85, optimize=True, progressive=True)
        elif ext == ".png":
            im.save(out, "PNG", optimize=True)
        else:
            return data
        return out.getvalue()
    except Exception as e:  # 리사이즈 실패는 치명적이지 않다
        print(f"    ! 리사이즈 생략: {e}")
        return data


def localize_file(path, fetcher=fetch):
    """HTML 하나를 처리한다. 바뀐 파일 경로 목록을 돌려준다."""
    with open(path, encoding="utf-8") as f:
        src_html = f.read()
    if "data-remote" not in src_html:
        return []

    base = os.path.dirname(path)
    m = DATE_IN_NAME.match(os.path.basename(path))
    day = m.group(1) if m else "misc"
    changed, out, pos = [], [], 0

    for tm in IMG_TAG.finditer(src_html):
        tag = tm.group(0)
        remote = attr(tag, "data-remote")
        src = attr(tag, "src")
        if not remote:
            continue
        if src and not re.match(r"https?://", src, re.I):
            continue  # 이미 로컬 — 멱등
        if not allowed(remote):
            print(f"  - 건너뜀(허용 호스트 아님): {remote}")
            continue

        stem = SAFE_NAME.sub("_", os.path.splitext(os.path.basename(urllib.parse.urlparse(remote).path))[0]) or "image"
        rel_dir = f"img/{day}"
        abs_dir = os.path.join(base, rel_dir)

        # 이전 실행에서 파일만 받고 HTML 교체가 안 된 경우 — 다시 받지 않는다
        existing = None
        if os.path.isdir(abs_dir):
            for n in os.listdir(abs_dir):
                if os.path.splitext(n)[0] == stem:
                    existing = n
                    break

        try:
            if existing:
                fname = existing
                print(f"  = 기존 파일 재사용: {rel_dir}/{fname}")
            else:
                data = fetcher(remote)
                ext = sniff(data)
                if not ext:
                    raise ValueError("파일 서명이 이미지가 아님")
                data = shrink(data, ext)
                fname = stem + ext
                os.makedirs(abs_dir, exist_ok=True)
                with open(os.path.join(abs_dir, fname), "wb") as f:
                    f.write(data)
                changed.append(os.path.join(abs_dir, fname))
                print(f"  + 저장: {rel_dir}/{fname} ({len(data):,} bytes)")
        except Exception as e:
            print(f"  ! 실패 — 핫링크 유지: {remote} ({e})")
            continue

        new_src = f"{rel_dir}/{fname}"
        new_tag = re.sub(ATTR.format("src"), f'src="{new_src}"', tag, count=1, flags=re.I)
        out.append(src_html[pos:tm.start()])
        out.append(new_tag)
        pos = tm.end()

    if not out:
        return changed
    out.append(src_html[pos:])
    new_html = "".join(out)
    if new_html != src_html:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_html)
        changed.append(path)
    return changed


def main(root="."):
    changed = []
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "img"]
        for n in sorted(names):
            if n.lower().endswith(".html") and not n.lower().startswith("index"):
                p = os.path.join(dirpath, n)
                try:
                    c = localize_file(p)
                except Exception as e:  # 파일 하나의 문제로 전체를 멈추지 않는다
                    print(f"! {p}: {e}")
                    continue
                if c:
                    print(f"{p}: {len(c)}개 변경")
                    changed += c
    out = os.environ.get("LOCALIZE_OUT")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(os.path.relpath(c, root) for c in changed) + ("\n" if changed else ""))
    print(f"완료: {len(changed)}개 경로 변경")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
