#!/usr/bin/env python3
"""⚾ 경기 결과 알림(2026-10-23~) — 경기가 끝나면 AI·토큰 없이 KBO 공식 기록만으로 점수 카드를 만들어 @hannun.sports 에 올린다.

  python3 score_alert.py --check   새로 끝난 경기가 있으면 GITHUB_OUTPUT 에 has_new=1 (브라우저 설치를 아끼려고 먼저 확인만)
  python3 score_alert.py           카드 JPG(tools/score_card.js) → 커밋·push → 공개 주소 확인 → 단일 이미지 게시 → 기록

- 데이터: koreabaseball.com 스코어보드 JSON(GetKboGameList). GAME_STATE_SC "3" + 정상경기 = 종료. 오늘(KST), 새벽 3시 전이면 어제도 본다.
- 이미 올린 경기는 sports/alerts/posted.json 에 G_ID 로 남긴다(중복 게시 방지). 한 번에 끝난 경기는 카드 한 장에 묶는다(최대 5경기).
- 해설·기사 검증은 하지 않는다 — 그건 밤 23:30 야구 나이트 루틴의 몫. 캡션도 기록 값만 쓴다.
- 끄기: 저장소 변수 SCORE_ALERT=off · 게시 없이 카드만: SCORE_ALERT=dry
"""
import datetime, json, os, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
POSTED = os.path.join(ROOT, "sports/alerts/posted.json")
API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
PAGES = "https://nonojin99.github.io/Daily-Card-News/"
MODE = os.environ.get("SCORE_ALERT", "on").strip().lower() or "on"
STAGE = {"준PO": "준플레이오프", "PO": "플레이오프", "KS": "한국시리즈", "WC": "와일드카드 결정전"}


def kst():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def kbo_games(day):
    data = urllib.parse.urlencode({"leId": "1", "srId": "0,1,3,4,5,6,7,8,9", "date": day.strftime("%Y%m%d")}).encode()
    req = urllib.request.Request("https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList", data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.koreabaseball.com/Schedule/ScoreBoard.aspx", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("game") or []


def stage_of(g):
    m = re.match(r"(준PO|PO|KS|WC)(\d+)", g.get("GAME_SC_NM") or "")
    return (f"{STAGE[m[1]]} {m[2]}차전", f"{m[1]} {m[2]}차전") if m else ("정규시즌", "")


def load_posted():
    return json.load(open(POSTED, encoding="utf-8")) if os.path.exists(POSTED) else {"posted": {}}


def finished_new():
    now, posted = kst(), load_posted()["posted"]
    days = [now.date()] + ([now.date() - datetime.timedelta(days=1)] if now.hour < 3 else [])
    out = []
    for d in days:
        try:
            games = kbo_games(d)
        except Exception as e:  # noqa: BLE001 — KBO 사이트가 막히거나 바뀌면 이번 회차는 건너뛴다
            print(f"::warning::KBO scoreboard {d}: {e}")
            continue
        for g in games:
            if str(g.get("GAME_STATE_SC")) == "3" and str(g.get("CANCEL_SC_ID")) == "0" and g["G_ID"] not in posted:
                out.append(g)
    return out


def git(*a):
    subprocess.run(["git", *a], cwd=ROOT, check=True)


def push(msg, paths):
    git("add", *paths)
    if subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=ROOT).returncode == 0:
        return
    git("commit", "-q", "-m", msg)
    for i in range(3):
        if subprocess.run(["git", "push", "-q"], cwd=ROOT).returncode == 0:
            return
        git("pull", "-q", "--rebase", "--autostash", "origin", "main")
    sys.exit("::error::push failed")


def ig(method, path, token, **params):
    params["access_token"] = token
    body = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    req = urllib.request.Request(url + ("?" + body.decode() if method == "GET" else ""), data=None if method == "GET" else body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} → HTTP {e.code}: {e.read().decode(errors='replace')[:400]}")


def main():
    if MODE == "off":
        print("score alert: off"); return
    new = finished_new()
    if "--check" in sys.argv:
        print(f"score alert: {len(new)} newly finished game(s)")
        with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
            f.write(f"has_new={1 if new else 0}\n")
        return
    if not new:
        print("score alert: nothing new"); return
    new = new[:5]
    gdate = datetime.datetime.strptime(new[0]["G_DT"], "%Y%m%d").date()
    games, lines = [], []
    for g in new:
        a, h, sa, sh = g["AWAY_NM"].strip(), g["HOME_NM"].strip(), str(g["T_SCORE_CN"]), str(g["B_SCORE_CN"])
        long_, short = stage_of(g)
        tie = sa == sh
        win, lose, sv = ((g.get(k) or "").strip() for k in ("W_PIT_P_NM", "L_PIT_P_NM", "SV_PIT_P_NM"))
        note = short or (f"{g.get('GAME_INN_NO')}회 무승부" if tie else "")
        games.append({"away": a, "home": h, "as": sa, "hs": sh, "venue": g.get("S_NM", ""), "note": note, "win": win, "lose": lose, "save": sv})
        pit = " · ".join(x for x in (win and f"승 {win}", lose and f"패 {lose}", sv and f"세 {sv}") if x)
        lines.append(f"{a} {sa}:{sh} {h} ({g.get('S_NM', '')}{', ' + long_ if short else ''}){' · ' + pit if pit else ''}{' · 무승부' if tie else ''}")
    if len(new) == 1:
        g, x = new[0], games[0]
        long_, short = stage_of(g)
        w = x["away"] if int(x["as"]) > int(x["hs"]) else x["home"]
        title = f"{x['away']}·{x['home']} 무승부" if x["as"] == x["hs"] else (f"{w}, {long_} 승리" if short else f"{w} 승리")
        first = f"[⚾ 경기 종료] {x['away']} {x['as']}:{x['hs']} {x['home']}" + (f" · {long_}" if short else "")
    else:
        title = f"오늘 KBO {len(new)}경기 결과"
        first = f"[⚾ 경기 종료] 오늘 KBO {len(new)}경기 결과"
    post_season = any(stage_of(g)[1] for g in new)
    caption = "\n".join([first, "", *lines, "", "기록: KBO 공식 기록 · 자세한 해설은 오늘 밤 ⚾ 야구 나이트에서",
                         "#KBO #야구 #경기결과 " + ("#가을야구" if post_season else "#프로야구")])
    stamp = kst().strftime("%H%M")
    rel = f"sports/alerts/{gdate:%Y-%m}/{gdate}_{stamp}.jpg"
    os.makedirs(os.path.dirname(os.path.join(ROOT, rel)), exist_ok=True)
    spec = os.path.join(ROOT, "sports/alerts/.games.json")
    json.dump({"date": str(gdate), "title": title, "games": games}, open(spec, "w", encoding="utf-8"), ensure_ascii=False)
    subprocess.run(["node", os.path.join(ROOT, "tools/score_card.js"), spec, os.path.join(ROOT, rel)], check=True)
    os.remove(spec)
    db = load_posted()
    for g in new:
        db["posted"][g["G_ID"]] = {"image": rel, "status": "dry" if MODE == "dry" else "pending", "at_kst": kst().strftime("%Y-%m-%d %H:%M")}
    json.dump(db, open(POSTED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    push(f"⚾ 경기 결과 알림 카드 {gdate} ({len(new)}경기) [skip ci]", [rel, POSTED])
    print(caption)
    if MODE == "dry":
        print("score alert: dry — 게시하지 않음"); return
    token, uid = os.environ.get("IG_SPORTS_ACCESS_TOKEN", "").strip(), os.environ.get("IG_SPORTS_USER_ID", "").strip()
    expect = os.environ.get("EXPECT_SPORTS_USERNAME", "hannun.sports").strip().lstrip("@")
    status = "failed"
    try:
        if not token or not uid:
            raise RuntimeError("IG_SPORTS_ACCESS_TOKEN / IG_SPORTS_USER_ID 없음")
        me = ig("GET", "me", token, fields="user_id,username")
        if str(me.get("user_id")) != uid or (expect and me.get("username") != expect):
            raise RuntimeError(f"토큰 계정이 @{expect} 가 아님 — 중단")
        url, t0 = PAGES + rel, time.time()
        while True:   # Pages 배포(보통 1~2분)를 기다린다
            try:
                with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
                    if r.status == 200: break
            except Exception:
                pass
            if time.time() - t0 > 900: raise RuntimeError(f"공개 주소에 이미지가 안 뜸: {url}")
            time.sleep(20)
        cid = ig("POST", f"{uid}/media", token, image_url=url, caption=caption)["id"]
        for _ in range(30):
            st = ig("GET", cid, token, fields="status_code").get("status_code")
            if st == "FINISHED": break
            if st in ("ERROR", "EXPIRED"): raise RuntimeError(f"container {st}")
            time.sleep(5)
        pid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
        link = ig("GET", pid, token, fields="permalink").get("permalink")
        status = "published"
        print(f"published: {link}")
    except Exception as e:  # noqa: BLE001
        print(f"::error::score alert publish failed: {e}")
        link = str(e)[:200]
    db = load_posted()
    for g in new:
        db["posted"][g["G_ID"]].update(status=status, result=link)
    json.dump(db, open(POSTED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    push(f"⚾ 경기 결과 알림 {status} {gdate} [skip ci]", [POSTED])
    if status != "published":
        sys.exit(1)


if __name__ == "__main__":
    main()
