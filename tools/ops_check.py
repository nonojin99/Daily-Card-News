#!/usr/bin/env python3
"""운영 점검 보조(ops-monitor 가 먼저 돌린다, 2026-10-25~) — 게시 요청의 검수 대기·산출물 누락을 계산해 사람이 읽을 목록으로 낸다. 아무것도 고치지 않는다."""
import datetime, glob, hashlib, json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
days = [(kst - datetime.timedelta(days=d)).strftime("%Y-%m-%d") for d in (0, 1)]
out = []


def review_state(kind, media, need):
    if kind == "reel":
        rec_p = media[:-4] + ".review.json"
        if not os.path.exists(media): return "MP4 없음"
        h = hashlib.sha1(open(media, "rb").read()).hexdigest()
    else:
        rec_p, src = os.path.join(media, "review.json"), os.path.join(media, "source.sha1")
        if not os.path.exists(src): return "카드 미생성"
        h = open(src, encoding="utf-8").read().strip()
    if not os.path.exists(rec_p): return "검수 기록 없음"
    r = json.load(open(rec_p, encoding="utf-8"))
    if r.get("sha1") != h: return "검수 뒤 파일 바뀜(재검수 필요)"
    if need == "human" and r.get("by") != "user": return "사용자 승인 대기"
    return "OK"


reqs = [("publish/request.json", json.load(open("publish/request.json", encoding="utf-8")))] if os.path.exists("publish/request.json") else []
for d in days:
    for f in sorted(glob.glob(f"publish/evening/{d}_*.json")):
        reqs.append((f, json.load(open(f, encoding="utf-8"))))
for f, j in reqs:
    for it in j.get("requests", []):
        kind, media, need = it.get("kind"), it.get("media", ""), str(it.get("review", "")).lower()
        if kind == "reel" and str(it.get("ab", "")).lower() == "short": media = media[:-4] + "_short.mp4"   # 짧은판 고정 요청은 _short.mp4 를 올린다
        line = f"{f} · {kind} · {media}"
        if kind == "reel" and not os.path.exists(media): out.append(("높음", line + " — MP4 없음")); continue
        if need in ("required", "human"):
            st = review_state(kind, media, need)
            if kind == "reel" and str(it.get("ab", "")) == "auto":
                st2 = review_state(kind, media[:-4] + "_short.mp4", need) if os.path.exists(media[:-4] + "_short.mp4") else "짧은판 없음"
                st = f"낭독판 {st} / 짧은판 {st2}"
            if "OK" != st and "낭독판 OK / 짧은판 OK" != st:
                out.append(("중간" if "승인 대기" in st else "높음", f"{line} — {st}"))
for d in days:
    for b in sorted(glob.glob(f"{d}_*-brief.html")):
        h = open(b, encoding="utf-8").read()
        if 'class="audio-script"' in h and 'class="audio-player"' not in h: out.append(("중간", f"{b} — 낭독 MP3 없음"))
        m = re.match(r"(\d{4})-(\d{2})-\d{2}_", b)
        if not os.path.exists(f"cards/{m[1]}-{m[2]}/{b[:-5]}/source.sha1"): out.append(("중간", f"{b} — 카드 JPG 미생성"))
ins = json.load(open("insights/latest.json", encoding="utf-8")) if os.path.exists("insights/latest.json") else {}
for a in ins.get("accounts", []):
    for e in a.get("errors", []):
        out.append(("높음" if str(e.get("code")) in ("190", "10", "200") else "중간", f"인사이트 {a.get('account')}: {e.get('step')} {e.get('code')} {e.get('message', '')[:80]}"))
print(f"# 운영 점검 보조 — {kst:%Y-%m-%d %H:%M} KST (오늘·어제)")
for s, m in out: print(f"- [{s}] {m}")
if not out: print("- 이상 없음(요청 검수·산출물·인사이트 오류 기준)")
