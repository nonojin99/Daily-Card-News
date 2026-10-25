#!/usr/bin/env python3
"""캐러셀 검수 승인 기록 — 2026-10-25~. Actions 가 구운 실제 카드 JPG(AI 그림 포함)를 card-visual-reviewer 가 보고 통과시킨 뒤에 쓴다.

  python3 tools/approve_cards.py cards/2026-10/2026-10-26_ai-brief --by agent|user [--note "…"]
  → cards/…/review.json {verdict, sha1 = source.sha1 내용, by, at, note}. 카드가 다시 구워지면 지문이 바뀌어 다시 검수해야 게시된다(publish_ig.py review_ok).
"""
import argparse, datetime, json, os, sys

ap = argparse.ArgumentParser(); ap.add_argument("folder"); ap.add_argument("--by", choices=["agent", "user"], required=True); ap.add_argument("--note", default="")
a = ap.parse_args()
src = os.path.join(a.folder, "source.sha1")
if not os.path.exists(src): sys.exit(f"FAIL 카드 지문 없음: {src} — Actions 가 아직 카드를 굽지 않았다")
jpgs = sorted(f for f in os.listdir(a.folder) if f.endswith(".jpg"))
if len(jpgs) < 2: sys.exit(f"FAIL 카드 JPG {len(jpgs)}장")
rec = {"verdict": "PASS", "sha1": open(src, encoding="utf-8").read().strip(), "by": a.by, "cards": len(jpgs),
       "at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "note": a.note}
json.dump(rec, open(os.path.join(a.folder, "review.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"승인 기록: {os.path.join(a.folder, 'review.json')} ({len(jpgs)}장)")
