#!/usr/bin/env python3
"""음악 브리프의 '들어 보기' 구간(figure.listen)을 검사한다 — README '음악 브리프 — 음원·주요 구절'.

  python3 tools/check_youtube.py YYYY-MM-DD_music-brief.html     # FAIL 있으면 종료 코드 1

검사
- iframe src 가 https://www.youtube-nocookie.com/embed/<11자 ID>?start=<초>&end=<초> 형식인가 (구간 15~90초)
- YouTube oEmbed 가 200 인가 (401 = 퍼가기 금지, 404 = 비공개·삭제 → 앱에서 재생 안 됨)
- figcaption 에 oEmbed 의 채널 이름(author_name)과 유튜브 원본 링크가 있는가
- data-basis(구간 근거)가 있는가 — 설명란 챕터·기사 문장 등. 근거 없이 '주요 구절'을 고르지 않는다
공식 채널인지는 기계로 다 못 가린다 — 출력된 채널 이름을 보고 작성자가 판단한다(아티스트·소속사·레이블·악단 공식 채널만).
"""
import html, json, re, sys, urllib.parse, urllib.request

FIG = re.compile(r'<figure class="listen"([^>]*)>(.*?)</figure>', re.S)
SRC = re.compile(r'^https://www\.youtube-nocookie\.com/embed/([A-Za-z0-9_-]{11})\?(.+)$')


def oembed(vid):
    u = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}", safe="")
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Daily-Card-News checker"}), timeout=15) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, {}


def main(path):
    doc = open(path, encoding="utf-8").read()
    figs = FIG.findall(doc)
    if not figs:
        print(f"{path}: figure.listen 없음")
        return 0
    fails = 0
    for i, (attrs, body) in enumerate(figs, 1):
        out = []
        m = re.search(r'<iframe[^>]*src="([^"]+)"', body)
        src = html.unescape(m.group(1)) if m else ""
        sm = SRC.match(src)
        if not sm:
            out.append("FAIL: iframe src 가 youtube-nocookie.com/embed/ID?start=…&end=… 형식이 아님")
        else:
            vid, q = sm.group(1), urllib.parse.parse_qs(sm.group(2))
            try:
                st, en = int(q["start"][0]), int(q["end"][0])
                if not 15 <= en - st <= 90:
                    out.append(f"FAIL: 구간 {en - st}초 (15~90초)")
            except (KeyError, ValueError):
                out.append("FAIL: start·end(초)가 없음")
            code, meta = oembed(vid)
            cap = re.sub(r"<[^>]+>", " ", (re.search(r"<figcaption>(.*?)</figcaption>", body, re.S) or [None, ""])[1])
            if code != 200:
                out.append(f"FAIL: oEmbed {code} — 퍼가기 금지·비공개·삭제 영상")
            else:
                print(f"  #{i} {vid} · 채널 '{meta.get('author_name')}' · {meta.get('title')}")
                if meta.get("author_name") and meta["author_name"] not in html.unescape(cap):
                    out.append(f"FAIL: 캡션에 채널 이름 '{meta['author_name']}' 이 없음")
            if f"youtube.com/watch?v={vid}" not in body:
                out.append("FAIL: 유튜브 원본 링크(youtube.com/watch?v=ID) 없음")
        if "data-basis=" not in attrs:
            out.append("FAIL: data-basis(구간을 고른 근거) 없음")
        for x in out:
            print(f"  #{i} {x}")
        fails += sum(x.startswith("FAIL") for x in out)
    print(f"{path}: 들어 보기 {len(figs)}개 · FAIL {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(max(main(p) for p in sys.argv[1:]) if sys.argv[1:] else 2)
