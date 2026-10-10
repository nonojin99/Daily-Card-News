#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
브리프 HTML 의 낭독 원고로 MP3 를 만들어 GitHub Releases 에 올리고, 브리프에 재생기를 넣는다.

  대상  <details class="audio-script"> 가 있고 아직 class="audio-player" 가 없는 브리프
  음성  Google Cloud Text-to-Speech (Chirp 3 HD) — 문단마다 합성한 뒤 이어 붙인다
  저장  Releases 태그 audio-YYYY-MM 에 YYYY-MM-DD_<type>.mp3 로 업로드
  교체  </header> 바로 뒤에 <div class="audio-player"><audio ...></div> 삽입

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
                    "-ac", "1", "-b:a", "64k", mp3_path], check=True)
    os.unlink(wav_path)
    return len(pcm) / 2 / SAMPLE_RATE


def upload(mp3_path, tag):
    if DRY_RUN:
        return
    if subprocess.run(["gh", "release", "view", tag], capture_output=True).returncode != 0:
        subprocess.run(["gh", "release", "create", tag, "--title", tag,
                        "--notes", "데일리 브리프 낭독 MP3 (자동 생성)"], check=True)
    subprocess.run(["gh", "release", "upload", tag, mp3_path, "--clobber"], check=True)


def player(url, seconds):
    mins = max(1, round(seconds / 60))
    return ('\n  <div class="audio-player">'
            '<span class="label">🎧 듣기 · 약 %d분</span>'
            '<audio controls preload="none" src="%s"></audio></div>\n' % (mins, html.escape(url)))


def process(path, name_match, changed):
    with open(path, encoding="utf-8") as f:
        doc = f.read()
    if 'class="audio-player"' in doc or "</header>" not in doc:
        return
    paras = paragraphs(doc)
    if not paras:
        return
    y, mo, d, kind = name_match.groups()
    tag = "audio-%s-%s" % (y, mo)
    mp3_name = "%s-%s-%s_%s.mp3" % (y, mo, d, kind.lower())
    with tempfile.TemporaryDirectory() as td:
        mp3_path = os.path.join(td, mp3_name)
        seconds = build_mp3(paras, mp3_path)
        upload(mp3_path, tag)
    url = "https://github.com/%s/releases/download/%s/%s" % (REPO, tag, mp3_name)
    doc = doc.replace("</header>", "</header>" + player(url, seconds), 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    changed.append(path)
    print("audio:", path, "→", url, "(%.0fs)" % seconds)


def main():
    if not API_KEY and not DRY_RUN:
        print("GOOGLE_TTS_API_KEY 가 없어 오디오 생성을 건너뜁니다.")
        return
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
                process(path, m, changed)
            except Exception as e:             # 한 파일 실패가 다른 파일을 막지 않게
                print("::warning::audio failed for %s: %s" % (path, e))
    if OUT_LIST and changed:
        with open(OUT_LIST, "w", encoding="utf-8") as f:
            f.write("\n".join(changed) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("::warning::make_audio crashed: %s" % e)
    sys.exit(0)
