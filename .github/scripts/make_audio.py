#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
브리프 HTML 의 낭독 원고로 MP3 를 만들어 레포 audio/ 폴더에 두고, 브리프에 재생기를 넣는다.

  대상  <details class="audio-script"> 가 있고 아직 class="audio-player" 가 없는 브리프
  음성  Google Cloud Text-to-Speech (Chirp 3 HD) — 문단마다 합성한 뒤 이어 붙인다
  저장  audio/YYYY-MM/YYYY-MM-DD_<type>.mp3 (48kbps 모노)
  교체  </header> 바로 뒤에 <div class="audio-player"><audio src="상대경로"></div> 삽입

왜 Releases 가 아니라 레포인가 (2026-10-13)
  Releases 파일은 application/octet-stream + attachment 로 내려와 iPhone Safari 가 재생하지 않았다.
  레포 파일은 GitHub Pages 가 audio/mpeg 로 서빙한다. 예전에 Releases 로 넣은 재생기는
  실행할 때마다 audio/ 로 옮기고 src 를 고친다(마이그레이션).

실패 원칙
  - 키(GOOGLE_TTS_API_KEY)가 없으면 아무것도 하지 않는다
  - 한 파일이 실패하면 그 파일은 건드리지 않는다 → 재생기 없이 그대로 보인다
  - 스크립트는 빌드를 실패시키지 않는다(항상 exit 0)
"""
import base64, html, io, json, os, re, subprocess, sys, tempfile, urllib.request, wave

API_KEY = os.environ.get("GOOGLE_TTS_API_KEY", "").strip()
VOICE = os.environ.get("TTS_VOICE", "ko-KR-Chirp3-HD-Kore")
RATE = float(os.environ.get("TTS_RATE", "1.0"))
REPO = os.environ.get("GITHUB_REPOSITORY", "nonojin99/Daily-Card-News")
AUDIO_DIR = "audio"
BITRATE = "48k"
RELEASE_SRC = re.compile(r'(<audio\b[^>]*\bsrc=")https://github\.com/[^/]+/[^/]+/releases/download/([^/"]+)/([^"]+\.mp3)(")')
OUT_LIST = os.environ.get("AUDIO_OUT")          # 바뀐 HTML 경로 목록(커밋 스텝이 읽음)
DRY_RUN = os.environ.get("AUDIO_DRY_RUN") == "1"  # 로컬 테스트용: API·업로드 대신 무음
ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
SAMPLE_RATE = 24000
PAUSE_SEC = 0.7          # 문단 사이 쉼
MAX_BYTES = 4500         # 요청당 입력 한도(5,000바이트)보다 여유 있게

NAME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_([a-z]+)-brief\.html$", re.I)
SCRIPT_BLOCK = re.compile(r'<details\b[^>]*class="audio-script"[^>]*>(.*?)</details>', re.I | re.S)
PARA = re.compile(r"<p\b[^>]*>(.*?)</p>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")


def paragraphs(doc):
    m = SCRIPT_BLOCK.search(doc)
    if not m:
        return []
    out = []
    for p in PARA.findall(m.group(1)):
        t = re.sub(r"\s+", " ", html.unescape(TAG.sub("", p))).strip()
        if t:
            out.append(t)
    return out


def chunks(text):
    """요청 한도를 넘는 문단은 문장 단위로 나눈다."""
    if len(text.encode("utf-8")) <= MAX_BYTES:
        return [text]
    out, cur = [], ""
    for s in re.split(r"(?<=[.?!])\s+", text):
        if cur and len((cur + " " + s).encode("utf-8")) > MAX_BYTES:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def synth(text):
    """LINEAR16 PCM(바이트)을 돌려준다."""
    if DRY_RUN:
        return b"\x00\x00" * int(SAMPLE_RATE * 0.05 * max(1, len(text) // 10))
    body = json.dumps({
        "input": {"text": text},
        "voice": {"languageCode": "ko-KR", "name": VOICE},
        "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": SAMPLE_RATE,
                        "speakingRate": RATE},
    }).encode("utf-8")
    req = urllib.request.Request(ENDPOINT + "?key=" + API_KEY, data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=120) as r:
        audio = base64.b64decode(json.load(r)["audioContent"])
    if audio[:4] == b"RIFF":                       # WAV 헤더가 붙어 오면 PCM 만 꺼낸다
        with wave.open(io.BytesIO(audio)) as w:
            if w.getframerate() != SAMPLE_RATE or w.getnchannels() != 1:
                raise RuntimeError("unexpected wav format")
            return w.readframes(w.getnframes())
    return audio


def build_mp3(paras, mp3_path):
    pcm = bytearray()
    pause = b"\x00\x00" * int(SAMPLE_RATE * PAUSE_SEC)
    for p in paras:
        for c in chunks(p):
            pcm += synth(c)
        pcm += pause
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE); w.writeframes(bytes(pcm))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path,
                    "-ac", "1", "-b:a", BITRATE, mp3_path], check=True)
    os.unlink(wav_path)
    return len(pcm) / 2 / SAMPLE_RATE


def audio_path(y, mo, mp3_name):
    d = os.path.join(AUDIO_DIR, "%s-%s" % (y, mo))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, mp3_name)


def rel_src(html_path, mp3_path):
    return os.path.relpath(mp3_path, os.path.dirname(html_path) or ".").replace(os.sep, "/")


def migrate(path, doc, changed):
    """Releases URL 재생기 → 레포 audio/ 로 옮기고 src 교체."""
    m = RELEASE_SRC.search(doc)
    if not m:
        return doc
    tag, mp3_name = m.group(2), m.group(3)
    nm = re.match(r"^(\d{4})-(\d{2})-", mp3_name)
    if not nm:
        return doc
    dest = audio_path(nm.group(1), nm.group(2), mp3_name)
    if not os.path.exists(dest):
        if DRY_RUN:
            open(dest, "wb").close()
        else:
            subprocess.run(["gh", "release", "download", tag, "-R", REPO, "-p", mp3_name,
                            "-D", os.path.dirname(dest), "--clobber"], check=True)
        changed.append(dest)
    doc = doc[:m.start()] + m.group(1) + rel_src(path, dest) + m.group(4) + doc[m.end():]
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    changed.append(path)
    print("migrated:", path, "→", dest)
    return doc


def player(url, seconds):
    mins = max(1, round(seconds / 60))
    return ('\n  <div class="audio-player">'
            '<span class="label">🎧 듣기 · 약 %d분</span>'
            '<audio controls preload="none" src="%s"></audio></div>\n' % (mins, html.escape(url)))


def process(path, name_match, changed):
    with open(path, encoding="utf-8") as f:
        doc = f.read()
    doc = migrate(path, doc, changed)
    if 'class="audio-player"' in doc or "</header>" not in doc:
        return
    paras = paragraphs(doc)
    if not paras:
        return
    y, mo, d, kind = name_match.groups()
    mp3_name = "%s-%s-%s_%s.mp3" % (y, mo, d, kind.lower())
    mp3_path = audio_path(y, mo, mp3_name)
    seconds = build_mp3(paras, mp3_path)
    url = rel_src(path, mp3_path)
    doc = doc.replace("</header>", "</header>" + player(url, seconds), 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    changed.extend([mp3_path, path])
    print("audio:", path, "→", url, "(%.0fs)" % seconds)


def main():
    if not API_KEY and not DRY_RUN:
        print("GOOGLE_TTS_API_KEY 가 없어 새 오디오 생성은 건너뜁니다(마이그레이션만 수행).")
    changed = []
    for root, dirs, names in os.walk("."):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        rel = os.path.relpath(root, ".")
        if rel != "." and not re.fullmatch(r"\d{4}-\d{2}", rel):
            continue
        for n in sorted(names):
            m = NAME.match(n)
            if not m:
                continue
            path = n if rel == "." else os.path.join(rel, n)
            try:
                if API_KEY or DRY_RUN:
                    process(path, m, changed)
                else:
                    with open(path, encoding="utf-8") as f:
                        migrate(path, f.read(), changed)
            except Exception as e:             # 한 파일 실패가 다른 파일을 막지 않게
                print("::warning::audio failed for %s: %s" % (path, e))
    if OUT_LIST and changed:
        with open(OUT_LIST, "w", encoding="utf-8") as f:
            f.write("\n".join(dict.fromkeys(changed)) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("::warning::make_audio crashed: %s" % e)
    sys.exit(0)
