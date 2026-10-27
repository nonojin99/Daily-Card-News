#!/usr/bin/env python3
"""시간대 게시(2026-10-26~, 사용자 승인) — 릴스를 하루 여러 시간대에 나눠 올린다.

  시간대: 0730(출근) · 1210(점심) · 1840(퇴근) · 2107(저녁). 워크플로 'Publish scheduled reels' 가 시간대마다 예약 실행한다.
  요청 파일: publish/slots/<게시 날짜>_<HHMM>_<이름>.json  (형식은 publish/request.json 과 같은 {"requests":[…]})
            publish/evening/<게시 날짜>_<이름>.json        = 2107 시간대(예전 방식, 그대로 쓴다)

  한 번 실행에서:
   1) 이 시간대 파일을 모두 처리한다.
   2) 오늘 더 이른 시간대 파일 중 아직 안 올라간 것(검수 대기였다가 승인됐거나, 예약 실행이 건너뛰어진 것)을 **최대 1건만** 따라잡는다
      — 한 시간대에 릴스가 몰리지 않게. 이미 올라간 캡션은 publish_ig.py 가 컨테이너를 만들기 전에 건너뛴다.
  SLOT 환경변수(워크플로가 예약 식으로 정함)가 없으면 지금 KST 기준 지난 가장 가까운 시간대. 새벽 4시 전이면 전날로 본다(예약 지연).

  2026-10-26~(사용자 요청 '올리는 시점·흐름이 중요'): 이 저장소의 예약 실행은 몇 시간씩 늦어(21:07 → 00:51) 시간대가 무너졌다.
  그래서 **주 경로는 결과 알림 이어 달리기**(score_alert.py --watch, 5분마다)가 부르는 tick() — 시간대가 되면 5분 안에 올린다.
  처리한 시간대는 publish/slots/.done.json 에 적고, 예약 실행(워크플로)은 예비로만 — 이미 처리된 시간대는 건너뛴다.
"""
import datetime, glob, json, os, re, subprocess, sys, time

SLOTS = ["0730", "1210", "1840", "2107"]
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DONE = os.path.join(ROOT, "publish/slots/.done.json")
SPORTS_Q = os.path.join(ROOT, "sports/reels/queue.json")


def note_sports_reel(f):
    """스포츠 계정 릴스를 올렸으면 데이터 릴스 대기열의 마지막 게시 시각을 맞춘다 — 같은 계정 릴스 간격 30분(2026-10-26 사용자 결정)이 코너 릴스까지 지켜지게."""
    try:
        reqs = json.load(open(os.path.join(ROOT, f), encoding="utf-8")).get("requests", [])
        if not any(r.get("account") == "sports" and r.get("kind") == "reel" for r in reqs) or not os.path.exists(SPORTS_Q):
            return False
        q = json.load(open(SPORTS_Q, encoding="utf-8"))
        q["last_post"] = time.time()
        json.dump(q, open(SPORTS_Q, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"::warning::sports queue last_post update failed: {e}")
        return False


def load_done():
    try:
        return json.load(open(DONE, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def mark_done(key, now, fail, waiting=()):
    d = load_done()
    d[key] = {"at_kst": now.strftime("%Y-%m-%d %H:%M"), "fail": bool(fail)}
    if waiting:
        d[key]["waiting"] = list(waiting)   # 검수 대기로 못 올린 항목 — check_slots.py 가 알림(Actions 실패 메일)으로 바꾼다
    cut = (now - datetime.timedelta(days=4)).strftime("%Y-%m-%d")
    d = {k: v for k, v in d.items() if k[:10] >= cut}
    os.makedirs(os.path.dirname(DONE), exist_ok=True)
    json.dump(d, open(DONE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def kst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def current(now):
    """(게시 날짜, 지금 시간대) — 새벽 4시 전이면 전날 2107. 오늘 첫 시간대 전이면 None."""
    if now.hour < 4:
        return (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d"), "2107"
    hm = now.strftime("%H%M")
    due = [s for s in SLOTS if s <= hm]
    return (now.strftime("%Y-%m-%d"), due[-1]) if due else (None, None)


def files_for(day, slot):
    out = sorted(glob.glob(os.path.join(ROOT, f"publish/slots/{day}_{slot}_*.json")))
    if slot == "2107":
        out += sorted(glob.glob(os.path.join(ROOT, f"publish/evening/{day}_*.json")))
    return [os.path.relpath(f, ROOT) for f in out]


def run(f):
    print(f"== {f}", flush=True)
    p = subprocess.run([sys.executable, os.path.join(ROOT, ".github/scripts/publish_ig.py")], env={**os.environ, "REQUEST": f}, capture_output=True, text=True, cwd=ROOT)
    sys.stdout.write(p.stdout); sys.stderr.write(p.stderr)
    waits = [l.split("검수 대기 —", 1)[1].strip() for l in p.stdout.splitlines() if "검수 대기 —" in l]   # 검수 기록이 없거나 지문이 달라 건너뛴 항목
    return p.returncode, "PUBLISHED" in p.stdout, waits


def process(day, slot):
    """이 시간대 파일 전부 + 더 이른 시간대에서 못 올린 것 최대 1건. (실패가 있으면 True, 검수 대기로 건너뛴 항목 목록)."""
    print(f"slot {day} {slot}", flush=True)
    fail, waiting = False, []
    for f in files_for(day, slot):
        code, pub, waits = run(f); fail |= code != 0
        waiting += [f"{os.path.basename(f)}: {w[:90]}" for w in waits]
        if pub: note_sports_reel(f)
    for s in SLOTS[:SLOTS.index(slot)]:
        caught = False
        for f in files_for(day, s):
            code, pub, waits = run(f); fail |= code != 0
            if pub:
                note_sports_reel(f)
                print(f"::notice::따라잡기 1건 게시 — {f} (나머지는 다음 시간대)"); caught = True; break
        if caught:
            break
    return fail, waiting


def tick():
    """이어 달리기 루프용(5분마다). 지금 시간대가 아직 처리되지 않았으면 처리하고 .done.json 을 고친다. 고친 파일 목록을 돌려준다."""
    now = kst_now()
    day, slot = current(now)
    if not day or f"{day}_{slot}" in load_done():
        return []
    fail, waiting = process(day, slot)
    mark_done(f"{day}_{slot}", now, fail, waiting)
    return [os.path.relpath(DONE, ROOT), os.path.relpath(SPORTS_Q, ROOT)]


def main():
    now = kst_now()
    day, slot = current(now)
    env_slot = os.environ.get("SLOT", "").strip()
    if env_slot in SLOTS:
        slot = env_slot
        day = (now - datetime.timedelta(days=1) if now.hour < 4 else now).strftime("%Y-%m-%d")
    if not day:
        print("오늘 첫 시간대 전 — 할 일 없음"); return
    key = f"{day}_{slot}"
    if key in load_done() and os.environ.get("FORCE", "") != "1":
        print(f"{key} 는 이어 달리기가 이미 처리함({load_done()[key]['at_kst']}) — 예비 실행은 건너뜀"); return
    fail, waiting = process(day, slot)
    mark_done(key, now, fail, waiting)
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
