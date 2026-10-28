#!/usr/bin/env python3
"""카카오톡 '나에게 보내기' 알림(2026-10-29~, 사용자 요청).

보내는 것 (workflows/kakao-alert.yml 이 부른다):
  ① Actions 실패 — 같은 워크플로는 성공하기 전까지 6시간에 한 번만
  ② tools/ops_check.py 의 '사용자 승인 대기' — 새 항목이 보이면 바로
  ③ tools/ops_check.py 의 [높음] — 20분 넘게 남아 있을 때(빌드 직후 잠깐 비는 산출물은 무시)
  ④ 루틴 결과 — 루틴이 push 한 alerts/outbox/<YYYY-MM-DD_HHMM>_<루틴>.txt (오늘·어제 파일만, CLAUDE.md '카카오 알림')
게시 성공 알림은 게시 스크립트(publish_ig.py · score_alert.py)가 kakao.notify 로 바로 보낸다.
같은 항목은 한 번만 보낸다. 상태는 STATE 파일(actions/cache 로 이어 받음).

환경 변수: KAKAO_REST_KEY · KAKAO_CLIENT_SECRET · KAKAO_REFRESH_TOKEN (필수)
           KAKAO_SECRETS_PAT (선택 — 있으면 새 refresh token 을 Secret 에 자동 저장)
           MODE=run|test · TEST_MSG · WF_NAME · WF_CONCLUSION · WF_URL · WF_TITLE · STATE · GITHUB_REPOSITORY
"""
import datetime, glob, hashlib, json, os, re, subprocess, sys

from kakao import APP, access_token, send
NOW = datetime.datetime.now(datetime.timezone.utc)
KST = NOW + datetime.timedelta(hours=9)
STATE = os.environ.get("STATE", "kakao-state/state.json")


def clip(lines, head):
    """200자 안에 들어가는 만큼만 넣고 나머지는 '외 N건'."""
    out, left = head, len(lines)
    for ln in lines:
        cand = out + "\n· " + ln
        if len(cand) > 185:
            break
        out, left = cand, left - 1
    return out + (f"\n외 {left}건" if left else "")


def ops_items():
    r = subprocess.run([sys.executable, "tools/ops_check.py"], capture_output=True, text=True)
    items = {}
    for ln in r.stdout.splitlines():
        m = re.match(r"- \[(높음|중간)\] (.+)", ln)
        if m and (m[1] == "높음" or "승인 대기" in m[2]):
            items[hashlib.sha1(m[2].encode()).hexdigest()[:12]] = (m[1], m[2])
    return items


def main():
    if os.environ.get("MODE") == "test":
        try:
            at, warn = access_token()
        except RuntimeError as e:
            sys.exit(str(e))
        sys.exit(0 if send(at, (os.environ.get("TEST_MSG") or "카카오 알림 테스트 ✅") + warn, APP) else 1)

    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    fails, seen = st.setdefault("fail", {}), st.setdefault("items", {})
    msgs = []

    # ① 워크플로 실패
    wf, concl = os.environ.get("WF_NAME", ""), os.environ.get("WF_CONCLUSION", "")
    if wf and concl == "success":
        fails.pop(wf, None)
    elif wf and concl == "failure":
        last = fails.get(wf)
        if not last or NOW - datetime.datetime.fromisoformat(last) > datetime.timedelta(hours=6):
            title = os.environ.get("WF_TITLE", "").splitlines()[0][:60] if os.environ.get("WF_TITLE") else ""
            msgs.append((f"⚠ [Actions 실패] {wf}\n{title}\n{KST:%m/%d %H:%M} KST", os.environ.get("WF_URL") or APP, wf, "fail"))

    # ②③ 승인 대기 · 높음
    now_items = ops_items()
    new = []
    for k, (lvl, text) in now_items.items():
        rec = seen.setdefault(k, {"first": NOW.isoformat(), "sent": False})
        if rec["sent"]:
            continue
        aged = NOW - datetime.datetime.fromisoformat(rec["first"]) > datetime.timedelta(minutes=20)
        if "승인 대기" in text or aged:
            new.append((k, ("🔔 " if "승인 대기" in text else "⚠ ") + text))
    for k in list(seen):   # 사라진 항목은 잊는다(다시 생기면 다시 알림)
        if k not in now_items:
            del seen[k]
    if new:
        msgs.append((clip([t for _, t in new], f"🔔 [승인·점검] {len(new)}건"), APP, [k for k, _ in new], "items"))

    # ④ 루틴 결과(outbox)
    sent_box = st.setdefault("outbox", [])
    days = {(KST - datetime.timedelta(days=d)).strftime("%Y-%m-%d") for d in (0, 1)}
    for f in sorted(glob.glob("alerts/outbox/*.txt")):
        name = os.path.basename(f)
        if name[:10] in days and name not in sent_box:
            text = open(f, encoding="utf-8").read().strip()
            if text:
                msgs.append((text, APP, name, "outbox"))
    st["outbox"] = [n for n in sent_box if n[:10] in days]

    if msgs:
        try:
            at, warn = access_token()
        except RuntimeError as e:
            sys.exit(str(e))
        for text, link, key, kind in msgs:
            if send(at, text + warn, link):
                warn = ""
                if kind == "fail":
                    fails[key] = NOW.isoformat()
                elif kind == "outbox":
                    st["outbox"].append(key)
                else:
                    for k in key:
                        seen[k]["sent"] = True
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
