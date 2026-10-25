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
"""
import datetime, glob, os, re, subprocess, sys

SLOTS = ["0730", "1210", "1840", "2107"]


def files_for(day, slot):
    out = sorted(glob.glob(f"publish/slots/{day}_{slot}_*.json"))
    if slot == "2107":
        out += sorted(glob.glob(f"publish/evening/{day}_*.json"))
    return out


def run(f):
    print(f"== {f}", flush=True)
    p = subprocess.run([sys.executable, ".github/scripts/publish_ig.py"], env={**os.environ, "REQUEST": f}, capture_output=True, text=True)
    sys.stdout.write(p.stdout); sys.stderr.write(p.stderr)
    return p.returncode, "PUBLISHED" in p.stdout


def main():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    base = now - datetime.timedelta(hours=4) if now.hour < 4 else now
    day = base.strftime("%Y-%m-%d")
    slot = os.environ.get("SLOT", "").strip()
    if slot not in SLOTS:
        hm = "2400" if now.hour < 4 else now.strftime("%H%M")
        slot = max([s for s in SLOTS if s <= hm] or ["0730"])
    print(f"slot {day} {slot}")
    fail = 0
    for f in files_for(day, slot):
        code, _ = run(f); fail |= code != 0
    for s in SLOTS[:SLOTS.index(slot)]:
        caught = False
        for f in files_for(day, s):
            code, pub = run(f); fail |= code != 0
            if pub:
                print(f"::notice::따라잡기 1건 게시 — {f} (나머지는 다음 시간대)"); caught = True; break
        if caught:
            break
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
