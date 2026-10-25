#!/usr/bin/env python3
"""스포츠 데이터 검사(2026-10-25~, 사용자 승인) — 공식 기록 API 로 만든 결과판(스토리)·앞으로의 데이터 릴스가 게시되기 전에
API 값이 카드에 제대로 옮겨졌는지 기계로 확인한다. AI 없음. score_alert.py 가 결과판마다 부르고, FAIL 이면 그 판을 올리지 않는다.

  validate(board) → (fails, warns)   board = {"sport","title","rows":[{"away","home","as","hs","pending","note"}]}
  python3 tools/check_sports_data.py <board.json>   (손으로 확인할 때)
"""
import json, re, sys

RESULT = {"ufc": {"승", "패", "무"}}


def validate(bd):
    F, W = [], []
    sport, rows = bd.get("sport", ""), bd.get("rows") or []
    if not rows: F.append("경기 행이 없음")
    seen = set()
    for i, r in enumerate(rows, 1):
        a, h = (r.get("away") or "").strip(), (r.get("home") or "").strip()
        tag = f"{i}행 {a} vs {h}"
        if not a or not h: F.append(f"{tag}: 팀·선수 이름 빈칸")
        if a and a == h: F.append(f"{tag}: 양쪽 이름이 같음")
        if (a, h) in seen: F.append(f"{tag}: 같은 경기가 두 번")
        seen.add((a, h))
        sa, sh = str(r.get("as", "")), str(r.get("hs", ""))
        if r.get("pending"):
            if sa not in ("-", "") or sh not in ("-", ""): F.append(f"{tag}: 끝나지 않은 경기에 점수({sa}:{sh})")
        else:
            ok = RESULT.get(sport)
            if ok:
                if sa not in ok or sh not in ok: F.append(f"{tag}: 결과 표기 이상({sa}/{sh})")
            elif not (sa.isdigit() and sh.isdigit()):
                F.append(f"{tag}: 끝난 경기인데 점수가 숫자가 아님({sa}:{sh})")
            elif int(sa) > 200 or int(sh) > 200:
                F.append(f"{tag}: 점수가 비정상적으로 큼({sa}:{sh})")
        for n in (a, h):
            if sport not in ("lol", "ufc") and re.search(r"[A-Za-z]{3,}", n): W.append(f"{tag}: 한국어 이름 없음 '{n}' — sports/alerts/names_ko.json 에 추가")
            if len(n) > 16: W.append(f"{tag}: 이름이 길어 카드에서 잘릴 수 있음 '{n}'")
    m = re.search(r"(\d+)/(\d+)\s*종료", bd.get("title", ""))
    if m:
        fin = sum(1 for r in rows if not r.get("pending"))
        if int(m[1]) != fin or int(m[2]) != len(rows): F.append(f"제목 '{m[0]}' 과 실제 종료 {fin}/{len(rows)} 가 다름")
    return F, W


if __name__ == "__main__":
    b = json.load(open(sys.argv[1], encoding="utf-8"))
    f, w = validate(b)
    for x in f: print("FAIL", x)
    for x in w: print("WARN", x)
    print(f"합계: FAIL {len(f)} · WARN {len(w)}")
    sys.exit(1 if f else 0)
