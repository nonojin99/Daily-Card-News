#!/usr/bin/env python3
"""카드 검토 하네스 1단계 — 브리프 HTML 의 카드 재료(.cn)가 README 규칙을 지키는지 기계로 검사한다.
사용: python3 tools/check_cards.py 2026-10-18_science-brief.html
FAIL 이 하나라도 있으면 종료 코드 1. WARN 은 2단계(시각 검토)에서 눈으로 판단한다.
규칙 근거: README '카드 넘겨보기' · '카드 이미지·그림 개선 규칙' · 체크리스트 16번."""
import re, sys, html
from pathlib import Path

BANNED_TOPICS = {"발견", "결과", "전망", "관측 기법", "대상 행성", "선행 연구", "배경", "기타", "분석", "의미", "연구", "개요", "요약"}
INFO = ("cn-scores", "cn-score", "cn-link", "cn-shift", "cn-steps", "cn-bars", "cn-place", "cn-when", "cn-num")
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
    print(f"\n합계: FAIL {fails} · WARN {warns}")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
