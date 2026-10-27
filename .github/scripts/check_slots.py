#!/usr/bin/env python3
"""예정 시각에 안 올라간 슬롯 게시를 알린다(2026-10-27, 사용자 요청 — 운영 감시는 밤 11시라 텀이 너무 길다).

시간대(07:30·12:10·18:40·21:07 KST)가 지나고 25~100분 사이에, 그 시간대 요청 파일이 있는데
  · publish/slots/.done.json 에 처리 기록이 없거나(감시가 끊김) · 게시에 실패했거나 · 검수 대기로 건너뛴 항목이 있으면
종료 코드 1 로 끝난다 → 이 워크플로의 실패 메일(GitHub 알림)이 알림이다. 매시 35분에 돈다(25~100분 창이라 길게 못 알려도 1~2번).
이미 따라잡기로 올라간 항목은 .done.json 에 남은 대기 기록과 구분하지 못하니, 메일을 받으면 인스타에서 확인한다.
"""
import datetime, glob, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
import publish_slots as ps


def main():
    now = ps.kst_now()
    done = ps.load_done()
    problems = []
    for day in {now.strftime("%Y-%m-%d"), (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")}:
        for slot in ps.SLOTS:
            at = datetime.datetime.strptime(f"{day} {slot}", "%Y-%m-%d %H%M")
            age = (now - at).total_seconds() / 60
            if not 25 <= age <= 100:
                continue
            files = ps.files_for(day, slot)
            if not files:
                continue
            key, names = f"{day}_{slot}", ", ".join(os.path.basename(f) for f in files)
            rec = done.get(key)
            if rec is None:
                problems.append(f"{key} ({int(age)}분 지남): 처리 기록 없음 — 이어 달리기가 끊겼을 수 있음 [{names}]")
            elif rec.get("fail"):
                problems.append(f"{key}: 게시 실패 기록 [{names}]")
            elif rec.get("waiting"):
                problems.append(f"{key}: 검수 대기로 건너뜀 — " + " / ".join(rec["waiting"]))
    if problems:
        print("::error::예정대로 안 올라간 게시가 있습니다")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print("예정 시간대 게시 이상 없음")


if __name__ == "__main__":
    main()
