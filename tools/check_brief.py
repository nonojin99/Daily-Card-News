#!/usr/bin/env python3
"""브리프 검토 0단계 — CLAUDE.md 3·4절 중 기계로 판정할 수 있는 규칙을 검사한다.
brief-fact-checker(LLM)에게 맡기던 형식·출처 규칙을 결정론적 체크로 옮긴 것.
사용: python3 tools/check_brief.py <브리프>.html [--pre-actions]
  --pre-actions : push 전(Actions 가 audio-player·cn-gen 을 넣기 전) 검사. 이때만 복사 금지 항목을 본다.
FAIL 이 하나라도 있으면 종료 코드 1."""
import datetime, re, sys
from collections import Counter
from urllib.parse import urlparse

BLOCKED = ("yna.co.kr", "mk.co.kr", "donga.com", "chosun.com", "hani.co.kr",
           "news.kbs.co.kr", "imnews.imbc.com", "naver.com", "olympics.com")      # 3절 403 목록
BANNED = ("wikipedia.org", "namu.wiki", "blog.", "tistory.com", "brunch.co.kr")   # 3절 위키·블로그 금지
SCRIPT_LEN = {"daily": (1000, 1800), "ai": (700, 1300), "culture": (700, 1300),
              "science": (1300, 2000), "travel": (230, 320), "activity": (230, 320),
              "money": (600, 1100), "health": (600, 1100), "ott": (600, 1100), "food": (600, 1100)}
FOOTER = {"money": "정보 제공 목적이며 투자 판단은 본인에게 있습니다",
          "health": "진단·처방이 아니며, 증상이 있으면 의료진과 상담하세요"}
DOW = "월화수목금토일"

def strip(h): return re.sub(r"<[^>]+>", "", h)

def main(path, pre):
    h = open(path, encoding="utf-8").read()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})_([a-z]+)-brief\.html$", path)
    if not m: sys.exit(f"파일명 형식이 아님: {path}")
    y, mo, d, kind = int(m[1]), int(m[2]), int(m[3]), m[4]
    date = datetime.date(y, mo, d)
    out = []
    F = lambda s: out.append(("FAIL", s)); W = lambda s: out.append(("WARN", s))

    # 날짜: <title>·og:title 에 오늘 날짜, 원고 첫 문장 요일
    dot = f"{y}.{mo:02d}.{d:02d}"
    for tag, pat in (("<title>", r"<title>(.*?)</title>"), ("og:title", r'og:title" content="([^"]*)"')):
        t = re.search(pat, h, re.S)
        if not t or dot not in t[1]: F(f"{tag} 에 오늘 날짜 {dot} 없음 → {t[1] if t else '태그 없음'}")
    sc = re.search(r'<details class="audio-script">(.*?)</details>', h, re.S)
    if not sc: F("낭독 원고(details.audio-script) 없음")
    else:
        body = re.sub(r"<summary>.*?</summary>", "", sc[1], flags=re.S)
        want = f"{mo}월 {d}일 {DOW[date.weekday()]}요일"
        if want not in strip(body)[:80]: F(f"원고 첫 문장에 '{want}' 없음(요일 확인)")
        n = len(re.sub(r"\s", "", strip(body)))
        lo, hi = SCRIPT_LEN.get(kind, (0, 10**6))
        if not lo <= n <= hi: F(f"원고 {n}자(공백 제외) — {kind} 범위 {lo}~{hi}")

    # 출처: 403 매체·위키/블로그·언론사 홈·같은 URL 3장 이상
    cards = re.findall(r'<article class="card".*?</article>', h, re.S)
    use = Counter()
    for i, c in enumerate(cards, 1):
        srcs = re.findall(r'class="source" href="([^"]+)"', c)
        if not srcs: F(f"카드 {i}: a.source 없음")
        for u in set(srcs):
            use[u] += 1
            p = urlparse(u); host = p.netloc.lower()
            if any(host == b or host.endswith("." + b) for b in BLOCKED): F(f"카드 {i}: 403 매체 출처(본문 확인 불가) {u}")
            if any(b in host for b in BANNED): F(f"카드 {i}: 위키·블로그 출처 {u}")
            if p.path.strip("/") == "" and not p.query: F(f"카드 {i}: 언론사 홈 링크 {u}")
    for u, k in use.items():
        if k >= 3: F(f"같은 URL 을 {k}개 카드에 사용: {u}")

    # 이미지(push 전만 — Actions 가 받은 뒤 src 를 로컬로 바꾼다): src·data-remote 둘 다 원격(2026-11-22)
    for tag in (re.findall(r"<img[^>]*data-remote[^>]*>", h) if pre else []):
        s = re.search(r'\ssrc="([^"]+)"', tag); r = re.search(r'data-remote="([^"]+)"', tag)
        if not (s and s[1].startswith("http") and r and r[1].startswith("http")): F(f"사진 src/data-remote 가 원격 URL 이 아님: {tag[:120]}")

    # 복사 금지(push 전만): Actions 가 넣는 요소
    if pre:
        if "<div class=\"audio-player\"" in h: F("audio-player div 를 복사함(Actions 가 넣는다)")
        if re.search(r'<img[^>]*class="cn-gen"', h): F("cn-gen img 를 직접 씀(cn-img 문장만)")

    # 날씨 한 줄(메인): 서울·최저·최고·⚠ 변동 가능·출처
    if kind == "daily":
        wx = re.search(r'<p class="weather">(.*?)</p>', h, re.S)
        if not wx: W("날씨 한 줄 없음 — footer 에 이유가 있는지 확인")
        else:
            w = wx[1]
            for need in ("서울", "최저", "최고", "⚠ 변동 가능", "href="):
                if need not in w: F(f"날씨 줄에 '{need}' 없음")
            if re.search(r"비 소식\s*\(", strip(w)) and "우산" not in w: F("날씨 줄에 '비 소식(시간대)'가 있는데 '우산 챙기세요' 없음")

    # 고정 문구·tracker
    if kind in FOOTER and FOOTER[kind] not in h: F(f"{kind} 필수 문구 없음: {FOOTER[kind]}")
    tr = re.search(r"<!-- tracker.*?-->", h, re.S)
    if not tr: F("tracker 주석 없음")
    elif not re.search(r"Firecrawl\S*\s*(호출\s*)?0회", tr[0]): F("tracker 에 'Firecrawl 0회' 기록 없음")

    nf = sum(k == "FAIL" for k, _ in out)
    print(f"# {path} — " + ("PASS" if not out else f"FAIL {nf} · WARN {len(out) - nf}"))
    for k, s in out: print(f"  - {k}: {s}")
    return 1 if nf else 0

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(max([main(a, "--pre-actions" in sys.argv) for a in args] or [0]))
