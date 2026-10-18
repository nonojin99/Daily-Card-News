#!/usr/bin/env python3
"""push 관문 — Claude Code PreToolUse 훅(.claude/settings.json)이 Bash 명령마다 부른다.
`git push` 일 때만 동작: origin/main 에 아직 없는 브리프 HTML 이 있으면 카드 검토 하네스를 강제한다.
  1단계: tools/check_cards.py (규칙) + tools/render_cards.js (렌더·넘침) 를 직접 돌려 FAIL 이면 push 차단
  2단계: 독립 시각 검토를 통과했다는 기록 /tmp/card-review/<브리프 이름>.stage2.md 가 있고
         그 기록이 브리프 파일보다 나중이어야 통과 (검토 뒤 브리프를 고쳤다면 다시 검토)
차단은 종료 코드 2 + stderr 메시지(Claude 에게 그대로 전달된다). 무인 루틴이 규칙을 잊어도 건너뛸 수 없게 하는 장치.
README '카드 검토 하네스 — 2단계 최종 확인' 절 참고."""
import datetime, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW = Path("/tmp/card-review")
BRIEF = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z]+-brief\.html$")

def sh(*a, **k):
    return subprocess.run(a, cwd=ROOT, capture_output=True, text=True, **k)

def main():
    try:
        cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    except Exception:
        return 0
    if not re.search(r"\bgit\b[^|;&]*\bpush\b", cmd):
        return 0
    sh("git", "fetch", "-q", "origin", "main", timeout=60)
    changed = sh("git", "diff", "--name-only", "origin/main", "HEAD").stdout.split()
    # 오늘·어제(KST) 브리프만 — 옛 브리프(카드 규칙 이전)나 비교 기준이 어긋난 경우로 push 가 영원히 막히지 않게
    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    recent = {(kst - datetime.timedelta(days=d)).strftime("%Y-%m-%d") for d in (0, 1)}
    briefs = [f for f in changed if BRIEF.match(f) and f[:10] in recent and (ROOT / f).exists()]
    if not briefs:
        return 0
    problems = []
    for b in briefs:
        r = sh("python3", "tools/check_cards.py", b, timeout=60)
        if r.returncode:
            fails = [l for l in r.stdout.splitlines() if "FAIL:" in l][:8]
            problems.append(f"[1단계 규칙] {b}\n" + "\n".join(fails))
        out = REVIEW / b.replace(".html", "")
        r = sh("node", "tools/render_cards.js", b, str(out), timeout=240)
        if r.returncode:
            problems.append(f"[1단계 렌더·넘침] {b}\n{(r.stdout + r.stderr).strip()[-600:]}")
        mark = REVIEW / (b.replace(".html", "") + ".stage2.md")
        if not mark.exists():
            problems.append(f"[2단계 시각 검토 기록 없음] {b}\n  {out}/*.png 를 독립 에이전트가 보고 4축(규칙·전문성·가독성·흐름) PASS 를 낸 뒤,\n  판정 요약을 {mark} 에 적으세요.")
        elif mark.stat().st_mtime < (ROOT / b).stat().st_mtime:
            problems.append(f"[2단계 기록이 낡음] {b} 는 시각 검토 뒤에 수정됐습니다 → 고친 카드를 다시 검토하고 {mark} 를 갱신하세요.")
    if problems:
        sys.stderr.write("⛔ push 차단 — 카드 검토 하네스를 통과하지 않은 브리프가 있습니다 (README '카드 검토 하네스').\n\n"
                         + "\n\n".join(problems) + "\n\n고친 뒤 다시 push 하세요. (3회 반복해도 FAIL 이면 그 카드 그림을 빼고 정보 시트로 두되, 2단계 기록에 그 사실을 적으세요.)\n")
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
