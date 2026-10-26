#!/usr/bin/env python3
"""릴스 검수 1단계(기계) + 승인 기록 — 2026-10-25 사용자 요청: 릴스가 하루 여러 편이 되므로 '보지 않은 영상이 게시되는 일'을 막는다.

  python3 tools/check_reel.py <reels/…/x.mp4> [--caption captions/….txt]
      길이·reel.json·캡션 규칙을 검사하고 접촉 시트를 만든다 → /tmp/reel-review/<이름>/sheet.png (+ f_*.png)
      FAIL 이 있으면 종료 코드 1. 2단계(.claude/agents/reel-reviewer.md)는 이 시트를 눈으로 본다.
  python3 tools/check_reel.py <mp4> --approve --by agent|user [--note "…"]
      1단계를 다시 돌려 통과하면 <mp4 이름>.review.json 에 {verdict, sha1(MP4), by, at, note} 를 쓴다.
      게시 스크립트(publish_ig.py)는 요청 항목에 "review" 가 있으면 이 기록의 sha1 이 지금 MP4 와 같을 때만 올린다(영상이 다시 구워지면 다시 검수).
"""
import argparse, datetime, hashlib, json, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NARR_MAX, SHORT_MAX, DEEP_MAX, FLIP_MAX = 180.0, 14.5, 90.0, 20.5   # FLIP = 깊게 파는 릴스 페이지 전환형(2026-10-26~)
DATA_MAX = 30.0   # 스포츠 데이터 릴스(reels/sports/, 2026-10-26~) — 낭독 없음·배경음악, 결과판 묶음은 최대 8판


def sha1(p):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).decode().strip())


def frame(mp4, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, t):.2f}", "-i", mp4, "-frames:v", "1", "-vf", "scale=270:-1", out], check=True)


def check(mp4, caption):
    out = []   # (FAIL|WARN, 메시지)
    F = lambda m: out.append(("FAIL", m)); W = lambda m: out.append(("WARN", m))
    name = os.path.basename(mp4)[:-4]
    short = name.endswith("_short") or name.endswith("_lib")
    data = "/reels/sports/" in mp4.replace(os.sep, "/")   # 스포츠 데이터 릴스 — 낭독 없음(AI 음성 표시 불필요), reel.json 대신 sports/reels/queue.json
    spec_p = mp4[:-4] + ".reel.json"
    spec = json.load(open(spec_p, encoding="utf-8")) if os.path.exists(spec_p) else {}
    if not spec and not data: W("reel.json 없음 — 구간·오프닝을 확인할 수 없음")
    d = dur(mp4)
    deep = spec.get("kind") == "deep"   # 깊게 파는 릴스(…_cN.mp4, 2026-10-26~) — 90초 이내, 사건·사고 검사는 그 카드만
    narr = bool(spec.get("audio"))   # 낭독판만 원고 MP3 를 쓴다 — 짧은판·10초판·라이브러리판·페이지 전환형·데이터 릴스는 배경음악만
    lim = DATA_MAX if data else SHORT_MAX if short else (DEEP_MAX if narr else FLIP_MAX) if deep else NARR_MAX
    if d > lim: F(f"길이 {d:.1f}초 > {lim}초")
    if d < 6: F(f"길이 {d:.1f}초 — 너무 짧음(만들다 실패?)")
    brief = spec.get("brief", "")
    html = open(os.path.join(ROOT, brief), encoding="utf-8").read() if brief and os.path.exists(os.path.join(ROOT, brief)) else ""
    arts = re.findall(r'<article class="card"[^>]*>(.*?)</article>', html, re.S) if html else []
    scope = [arts[spec["card"] - 1]] if deep and len(arts) >= spec.get("card", 0) > 0 else [html]
    if html and any(re.search(r'class="tag">\s*(Context|맥락)', x) for x in scope): F("맥락 읽기(사건·사고) 카드" + (" — 이 카드는" if deep else "가 있는 브리프 —") + " 릴스 금지")
    # 접촉 시트: 첫 2초(0·0.7·1.4·2.1초) + 구간 가운데 + 끝 1초
    D = os.path.join("/tmp/reel-review", name); os.makedirs(D, exist_ok=True)
    for f in os.listdir(D):
        if f.startswith("f_"): os.remove(os.path.join(D, f))
    ts = [0, 0.7, 1.4, 2.1]
    sp = spec.get("speed", 1) or 1
    if spec.get("segments") and narr:
        t = 0
        for s, e, *_ in spec["segments"][:12]:
            L = (e - s) / sp; ts.append(t + L / 2); t += L
    else:
        ts += [d * k / 6 for k in range(1, 6)]
    ts.append(d - 1)
    ts = sorted({round(min(max(0, x), d - 0.05), 2) for x in ts})
    frames = []
    for i, t in enumerate(ts):
        p = os.path.join(D, f"f_{i:02d}_{t:06.2f}s.png"); frame(mp4, t, p); frames.append(p)
    cols = 6
    rows = [frames[i:i + cols] for i in range(0, len(frames), cols)]
    row_files = []
    for r, fs in enumerate(rows):
        while len(fs) < cols: fs = fs + [fs[-1]]
        rp = os.path.join(D, f"row{r}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", *sum([["-i", x] for x in fs], []), "-filter_complex", f"hstack=inputs={cols}", rp], check=True)
        row_files.append(rp)
    sheet = os.path.join(D, "sheet.png")
    if len(row_files) == 1:
        os.replace(row_files[0], sheet)
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", *sum([["-i", x] for x in row_files], []), "-filter_complex", f"vstack=inputs={len(row_files)}", sheet], check=True)
    # 캡션
    if caption:
        if not os.path.exists(caption): F(f"캡션 파일 없음: {caption}")
        else:
            c = open(caption, encoding="utf-8").read().strip()
            first = c.split("\n")[0]
            if len(c) > 2200: F(f"캡션 {len(c)}자 > 2200")
            if c.count("#") > 5: F(f"해시태그 {c.count('#')}개 > 5")
            if first.startswith("🎧"): F("캡션 첫 줄이 '🎧 N분 듣는…' — 첫 줄은 구체적인 장소·숫자부터(CLAUDE.md)")
            if not re.match(r"^\[", first): W("캡션 첫 줄이 [분야] 로 시작하지 않음")
            if "▶" not in c: W("'▶ … 앱에서' 줄 없음")
            if narr and not data and "AI 음성" not in c: F("낭독판인데 캡션에 'AI 음성' 표시 없음")
            if spec and not narr and "AI 음성" in c: F("낭독이 없는 릴스인데 캡션에 'AI 음성' 표시가 있음")
            if deep and not narr and spec.get("credit") and spec["credit"].split(" — ")[0] not in c: F(f"배경음악 크레디트가 캡션에 없음: {spec['credit']}")
            if html and 'class="cn-gen"' in html and not re.search(r"AI (생성|개념도|그림)", c): F("AI 그림이 있는데 캡션에 AI 그림 표시 없음")
            m = re.search(r'<figure class="photo"[\s\S]*?class="credit">([\s\S]*?)</span>', html or "")
            if m:
                cr = re.sub(r"<[^>]+>", "", m.group(1)).replace("이미지:", "").split("·")[0].strip()
                if cr and cr not in c: F(f"사진 크레디트 원문이 캡션에 없음: {cr[:60]}")
    return out, {"duration": round(d, 2), "opening": spec.get("opening", "static"), "sheet": sheet, "frames": frames, "brief": brief}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4"); ap.add_argument("--caption"); ap.add_argument("--approve", action="store_true")
    ap.add_argument("--by", choices=["agent", "user"]); ap.add_argument("--note", default="")
    a = ap.parse_args()
    mp4 = a.mp4 if os.path.isabs(a.mp4) else os.path.join(ROOT, a.mp4)
    if not os.path.exists(mp4): sys.exit(f"FAIL MP4 없음: {a.mp4}")
    out, info = check(mp4, a.caption and (a.caption if os.path.isabs(a.caption) else os.path.join(ROOT, a.caption)))
    print(f"# {os.path.relpath(mp4, ROOT)} — {info['duration']}초 · 오프닝 {info['opening']} · 브리프 {info['brief'] or '?'}")
    for k, m in out: print(f"  - {k}: {m}")
    nf = sum(1 for k, _ in out if k == "FAIL")
    print(f"접촉 시트: {info['sheet']} (프레임 {len(info['frames'])}장)\n합계: FAIL {nf} · WARN {len(out) - nf}")
    if a.approve:
        if nf: sys.exit("승인 거부 — 1단계 FAIL 이 남아 있다")
        if not a.by: sys.exit("--by agent|user 가 필요하다")
        rec = {"verdict": "PASS", "sha1": sha1(mp4), "by": a.by, "at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "note": a.note}
        json.dump(rec, open(mp4[:-4] + ".review.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"승인 기록: {os.path.relpath(mp4[:-4] + '.review.json', ROOT)}")
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())
