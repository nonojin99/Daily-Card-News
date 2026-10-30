#!/usr/bin/env python3
"""카드 검토 하네스 1단계 — 브리프 HTML 의 카드 재료(.cn)가 README 규칙을 지키는지 기계로 검사한다.
사용: python3 tools/check_cards.py 2026-10-18_science-brief.html
FAIL 이 하나라도 있으면 종료 코드 1. WARN 은 2단계(시각 검토)에서 눈으로 판단한다.
규칙 근거: README '카드 넘겨보기' · '카드 이미지·그림 개선 규칙' · 체크리스트 16번."""
import re, sys, html
from pathlib import Path

BANNED_TOPICS = {"발견", "결과", "전망", "관측 기법", "대상 행성", "선행 연구", "배경", "기타", "분석", "의미", "연구", "개요", "요약"}
INFO = ("cn-table", "cn-ring", "cn-waffle", "cn-ticket", "cn-over", "cn-fixtures", "cn-scores", "cn-score", "cn-link", "cn-shift", "cn-steps", "cn-bars", "cn-place", "cn-when", "cn-num")
PHOTO_OK = re.compile(r"^https://(cdn\.(esawebb|esahubble)\.org/archives/images/screen/|(upload|thumb)\.wikimedia\.org/wikipedia/commons/)")
LICENSE = re.compile(r"CC0|CC BY|퍼블릭 도메인|Public domain|공공누리", re.I)
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

def text(h):
    h = re.sub(r"<br\s*/?>", "\n", h)
    return html.unescape(re.sub(r"<[^>]+>", " ", h))

def grab(cls, h, tag="p"):
    m = re.search(rf'<{tag}[^>]*class="{cls}"[^>]*>(.*?)</{tag}>', h, re.S)
    return m.group(1) if m else None

def main(fname):
    src = Path(fname).read_text(encoding="utf-8")
    sub = not fname.endswith("_daily-brief.html")
    cards = re.findall(r'<article class="card"([^>]*)>(.*?)</article>', src, re.S)   # [(속성, 본문)]
    fails = warns = 0
    layouts = {}
    print(f"# {fname} — 카드 {len(cards)}장 ({'서브·롱리드' if sub else '메인'})\n")
    for i, (attrs, a) in enumerate(cards, 1):
        out = []
        F = lambda m: out.append(("FAIL", m))
        W = lambda m: out.append(("WARN", m))
        cn = re.search(r'<div class="cn" hidden>(.*?)</div>\s*$', a, re.S)
        cn = cn.group(1) if cn else ""
        body = a[:a.find('<div class="cn"')] if '<div class="cn"' in a else a
        body_t = text(body)
        topic = text(grab("topic", a, "span") or "").strip()
        context = "Context" in (grab("tag", a, "span") or "")
        # 제목
        t = grab("cn-t", cn)
        if not t: F("cn-t 없음")
        else:
            lines = [x.strip() for x in text(t).split("\n")]
            if len(lines) != 2: F(f"cn-t 가 {len(lines)}줄 (2줄이어야 함)")
            for ln in lines:
                if len(ln) > 17: F(f"cn-t 줄이 깁니다 {len(ln)}자: {ln}")
                elif len(ln) < 7: W(f"cn-t 줄이 짧습니다 {len(ln)}자: {ln}")
        tt = text(t or "").replace("\n", "").replace(" ", "")
        # 요약
        s = text(grab("cn-s", cn) or "").strip()
        if not s: F("cn-s 없음")
        else:
            if not 70 <= len(s) <= 100: F(f"cn-s {len(s)}자 (70~100)")
            sents = [x for x in re.split(r"(?<=[.!?])\s+", s) if x]
            if not 2 <= len(sents) <= 3: W(f"cn-s {len(sents)}문장 (2~3)")
            if any(not x.rstrip(".!?").endswith(("요", "죠")) for x in sents): F("cn-s 가 해요체가 아님")
        # 미리 예약 카드(README '인스타그램 운영' — 다음 1~4주 예매·예약 오픈)
        if 'data-plan="ahead"' in attrs:
            if not topic.startswith("미리 예약"): F("미리 예약 카드인데 topic 이 '미리 예약 · {분야}' 가 아님")
            if not re.search(r'class="cn-when"[^>]*data-label=', cn): F("미리 예약 카드에 cn-when + data-label(예매 오픈·예약 마감) 없음")
            if "변동" not in body_t: F("미리 예약 카드에 '⚠ 변동 가능' 표기 없음")
        # 분야 태그
        if topic in BANNED_TOPICS: F(f"topic '{topic}' 은 분류어 — 카드만의 핵심어로")
        if sub and not 2 <= len(topic.replace(" ", "")) <= 8: W(f"topic '{topic}' 길이 (2~8자 권장)")
        # 그림
        has_v = 'class="cn-v"' in cn
        has_chart = 'class="chart"' in a
        ph = re.search(r'<figure class="photo"([^>]*)>(.*?)</figure>', a, re.S)
        has_info = any(f'class="{c}"' in cn for c in INFO)
        if ph:
            img = re.search(r'<img[^>]*src="([^"]+)"[^>]*data-remote="([^"]+)"', ph.group(2), re.S)
            if not img or not PHOTO_OK.match(img.group(2)): F("figure.photo 의 data-remote 가 허용 호스트(ESA /screen/ · Wikimedia Commons)가 아님")
            elif not (img.group(1) == img.group(2) or img.group(1).startswith("img/")): F("photo src 와 data-remote 불일치")
            if "data-card-cap" not in ph.group(1): F("figure.photo 에 data-card-cap(카드용 한 줄 설명) 없음")
            if 'class="credit"' not in ph.group(2): F("photo 크레디트 없음")
            elif img and "wikimedia.org" in img.group(2) and not LICENSE.search(text(ph.group(2))): F("Commons 이미지 크레디트에 라이선스 표기(CC BY·CC0·퍼블릭 도메인 등) 없음")
        if not (has_v or has_chart or ph or has_info):
            F("카드 그림 재료 없음 → 글자 타일/정보 시트로 떨어짐" if sub else "카드 그림 재료 없음")
        elif sub and not (has_v or has_chart or ph):
            W("서브 브리프인데 개념도·도표·이미지 없이 정보 그림만 — 2단계에서 충분한지 판단")
        if not sub and not context and not re.search(r'class="cn-num"', cn) and not has_chart:
            W("메인 비-맥락 카드에 cn-num 없음 (금요일 '이번 주 숫자' 재료)")
        # 제목과 같은 큰 숫자
        for v in re.findall(r'class="cn-num">([^|<]+)\|', cn):
            if v.strip().replace(" ", "") in tt: F(f"cn-num '{v.strip()}' 이 제목과 중복")
        # 순위표(2026-10-30 사용자 결정 — 시안 A, 카드 한 장 전체가 1~20위 표). 표 숫자는 출처 순위표와 대조(사실 검증)하고 여기선 형식·산수만 본다
        tb = re.search(r'<p class="cn-table"([^>]*)>(.*?)</p>', cn, re.S)
        if tb:
            rows = [[c.strip() for c in r.split("|")] for r in re.split(r"\s+/\s+", text(tb.group(2)).strip()) if r.strip()]
            if len(rows) not in (18, 20): F(f"cn-table {len(rows)}팀 — 5대 리그는 18팀(분데스·리그앙) 또는 20팀")
            prev = None
            for k, r in enumerate(rows, 1):
                if len(r) != 7: F(f"cn-table {k}위 칸 {len(r)}개 (팀|경기|승|무|패|득실|승점)"); continue
                try: gp, w, d, l, pts = (int(r[x]) for x in (1, 2, 3, 4, 6)); gd = int(r[5].replace("−", "-").replace("+", ""))
                except ValueError: F(f"cn-table {k}위 '{r[0]}' 숫자 아님"); continue
                if w + d + l != gp: F(f"cn-table {r[0]}: 승{w}+무{d}+패{l} ≠ 경기 {gp}")
                if pts != 3 * w + d: W(f"cn-table {r[0]}: 승점 {pts} ≠ 3×{w}+{d} — 승점 삭감이면 본문에 적기")
                if gd and not r[5].startswith(("+", "-", "−")): W(f"cn-table {r[0]}: 득실 '{r[5]}' 에 +/− 부호")
                if prev is not None and pts > prev: F(f"cn-table {k}위 {r[0]} 승점 {pts} 이 윗줄({prev})보다 큼 — 순서 확인")
                prev = pts
            zs = re.search(r'data-zones="([^"]*)"', tb.group(1))
            if not zs: W("cn-table data-zones 없음 — 챔스·유로파·강등 구역 색이 안 나온다")
            else:
                for z in zs.group(1).split("|"):
                    if not re.fullmatch(r"\d+(-\d+)?:[^:|]+", z.strip()): F(f"cn-table data-zones 형식 '{z}' (예: 1-4:챔스)")
            if not grab("cn-note", cn): W("cn-table 카드에 cn-note 없음 — 오른쪽 위 '몇 라운드 뒤 · 기준일'")
            if not re.search(r"\d+\s*라운드", body_t): F("cn-table 카드 본문에 'N라운드' 기준이 없음 — 언제 순위인지")
            cn = cn.replace(tb.group(0), "")
        # 숫자 출처: 카드용 문장·그림의 숫자가 같은 카드 본문·스펙 표에 있는가
        cn_t = text(cn)
        norm = lambda x: x.replace(",", "").lstrip("0") or "0"   # 08 = 8, 1,331 = 1331
        body_nums = {norm(b) for b in NUM.findall(body_t.replace(" ", ""))}
        for n in sorted(set(NUM.findall(cn_t))):
            if norm(n) not in body_nums and norm(n) != "0":   # 0 은 도표 축 눈금
                F(f"카드용 숫자 '{n}' 이 카드 본문·스펙 표에 없음")
        # 개념도 표기·구도
        if has_v:
            v = re.search(r'<svg class="cn-v"(.*?)</svg>', cn, re.S).group(0)
            if 'viewBox="0 0 400 220"' not in v: F("cn-v viewBox 가 0 0 400 220 이 아님")
            if 'aria-label=' not in v: F("cn-v aria-label 없음")
            kinds = tuple(sorted(set(re.findall(r"<(circle|ellipse|path|line|polygon|rect)", v))))
            sig = (kinds, len(re.findall(r"<circle", v)))
            if sig in layouts: W(f"cn-v 구도가 카드 {layouts[sig]}와 비슷함 — 같은 구도 반복인지 2단계에서 확인")
            layouts.setdefault(sig, i)
        nf = sum(1 for k, _ in out if k == "FAIL"); nw = len(out) - nf
        fails += nf; warns += nw
        head = f"## 카드 {i} [{topic}] — " + ("PASS" if not out else f"FAIL {nf} · WARN {nw}" if nf else f"WARN {nw}")
        print(head)
        for k, m in out: print(f"  - {k}: {m}")
    # 깊게 파는 릴스 원고(2026-10-28 사용자 반려 뒤 — GTA 6 릴스의 요점 장 3개가 카드에 이미 있는 가격·날짜를 되풀이했다)
    # README '깊게 파는 릴스': 카드를 되풀이하지 말고 한 단계 더 들어간다 → 요점 장(data-k)마다 카드 그림(cn)에 없는 새 숫자가 있어야 한다
    rn, rf, rw = reel_check(src, cards)
    fails += rf; warns += rw
    if rn: print(rn)
    print(f"\n합계: FAIL {fails} · WARN {warns}")
    return 1 if fails else 0

# 요점 문구의 숫자. 'GTA5'·'PS5' 처럼 글자에 붙은 숫자는 이름이라 뺀다
RNUM = re.compile(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?")

def reel_check(src, cards):
    out, f, w = [], 0, 0
    norm = lambda x: x.replace(",", "").lstrip("0") or "0"
    for m in re.finditer(r'<details class="reel-script"([^>]*)>(.*?)</details>', src, re.S):
        n = int((re.search(r'data-card="(\d+)"', m.group(1)) or [0, 0])[1])
        if not 1 <= n <= len(cards):
            out.append(f"  - FAIL: reel-script data-card={n} 에 해당하는 카드 없음"); f += 1; continue
        cn = re.search(r'<div class="cn" hidden>(.*?)</div>\s*$', cards[n - 1][1], re.S)
        seen = {norm(x) for x in RNUM.findall(text(re.sub(r'<svg.*?</svg>|<p class="cn-img">.*?</p>', "", cn.group(1) if cn else "", flags=re.S)))}
        pages = []
        for k in re.findall(r'<p[^>]*\bdata-k="([^"]*)"', m.group(2)):
            k = html.unescape(k); nums = {norm(x) for x in RNUM.findall(k)}
            if not nums:
                out.append(f"  - WARN: 요점 '{k}' 에 숫자 없음 — 숫자·날짜·조건이 든 요점이 강하다"); w += 1
            elif nums <= seen:
                out.append(f"  - FAIL: 요점 '{k}' 의 숫자가 모두 카드 {n} 에 이미 있음 — 카드를 되풀이하지 말고 새 정보로"); f += 1
            for i, (pk, pn) in enumerate(pages, 2):
                if nums and nums == pn:
                    out.append(f"  - FAIL: 요점 '{k}' 와 '{pk}' 의 숫자가 같음 — 장마다 다른 정보로"); f += 1
            pages.append((k, nums))
        if len(pages) < 2:
            out.append(f"  - FAIL: 카드 {n} 릴스 원고의 요점 장(data-k)이 {len(pages)}개 — 2개 이상"); f += 1
    head = "\n## 릴스 원고 — " + ("PASS" if not out else f"FAIL {f} · WARN {w}" if f else f"WARN {w}")
    return ((head + "\n" + "\n".join(out)) if out else head) if re.search(r'class="reel-script"', src) else "", f, w

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
