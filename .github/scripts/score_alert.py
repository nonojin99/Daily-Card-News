#!/usr/bin/env python3
"""경기 결과 알림 — 스토리(2026-10-23~). 경기가 끝나면 AI·토큰 없이 공식 기록만으로 결과 카드를 만들어 @hannun.sports **스토리**에 올린다.
피드(그리드)는 야구 나이트·축구 모닝 같은 시리즈만 두고, 실시간 결과는 24시간 뒤 사라지는 스토리로(사용자 결정 2026-10-24).

  python3 score_alert.py --check   새로 끝난 경기가 있으면 GITHUB_OUTPUT 에 has_new=1 (브라우저 설치를 아끼려고 먼저 확인만)
  python3 score_alert.py           종목마다 카드 1장(최대 5경기 묶음, tools/score_card.js) → 커밋·push → 공개 주소 확인 → 스토리 게시 → 기록

데이터
- ⚾ KBO: koreabaseball.com 스코어보드 JSON(GetKboGameList). GAME_STATE_SC "3" + 정상경기 = 종료. 오늘(KST), 새벽 3시 전이면 어제도.
- 🎮 LoL: lolesports.com 일정 API(getSchedule — 사이트가 쓰는 공개 키). 롤드컵·MSI·퍼스트 스탠드·LCK, state "completed" 이고 시작 18시간 안.
- 올린 경기는 sports/alerts/posted.json 에 남겨 중복 게시를 막는다. 해설은 밤 야구 나이트·e스포츠 루틴 몫.
- 끄기: 저장소 변수 SCORE_ALERT=off · 카드만 만들고 게시 안 함: dry
"""
import datetime, json, os, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
POSTED = os.path.join(ROOT, "sports/alerts/posted.json")
API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
PAGES = "https://nonojin99.github.io/Daily-Card-News/"
MODE = os.environ.get("SCORE_ALERT", "on").strip().lower() or "on"
STAGE = {"준PO": "준플레이오프", "PO": "플레이오프", "KS": "한국시리즈", "WC": "와일드카드 결정전"}
LOL_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"   # lolesports.com 이 브라우저에서 쓰는 공개 키(비밀 아님)
LOL_LEAGUES = {"98767975604431411": "롤드컵", "98767991325878492": "MSI", "113464388705111224": "퍼스트 스탠드", "98767991310872058": "LCK"}
LCK_KO = {"GEN": "젠지", "HLE": "한화생명", "DK": "디플러스 기아", "KT": "KT", "T1": "T1", "NS": "농심", "BFX": "BNK 피어엑스",
          "DRX": "DRX", "BRO": "OK저축은행 브리온", "DNF": "DN 프릭스", "KDF": "광동"}
SPORT = {"kbo": {"kicker": "⚾ 경기 종료", "accent": "#1f5f8b", "src": "기록: KBO 공식 기록 · 해설은 오늘 밤 ⚾ 야구 나이트", "foot": "야구 결과"},
         "lol": {"kicker": "🎮 경기 종료", "accent": "#4a4fa0", "src": "기록: LoL Esports 공식 일정 · 해설은 🎮 e스포츠 브리프", "foot": "e스포츠 결과"}}


def kst():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def get_json(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def kbo(posted):
    now, out = kst(), []
    for d in [now.date()] + ([now.date() - datetime.timedelta(days=1)] if now.hour < 3 else []):
        try:
            games = get_json("https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList",
                             urllib.parse.urlencode({"leId": "1", "srId": "0,1,3,4,5,6,7,8,9", "date": d.strftime("%Y%m%d")}).encode(),
                             {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest",
                              "Referer": "https://www.koreabaseball.com/Schedule/ScoreBoard.aspx"}).get("game") or []
        except Exception as e:  # noqa: BLE001 — 사이트가 막히거나 바뀌면 이번 회차는 건너뛴다
            print(f"::warning::KBO scoreboard {d}: {e}"); continue
        for g in games:
            gid = "kbo:" + g["G_ID"]
            if str(g.get("GAME_STATE_SC")) != "3" or str(g.get("CANCEL_SC_ID")) != "0" or gid in posted or g["G_ID"] in posted:
                continue
            m = re.match(r"(준PO|PO|KS|WC)(\d+)", g.get("GAME_SC_NM") or "")
            sa, sh = str(g["T_SCORE_CN"]), str(g["B_SCORE_CN"])
            pit = " · ".join(x for x in (f"승 {g['W_PIT_P_NM'].strip()}" if (g.get("W_PIT_P_NM") or "").strip() else "",
                                         f"패 {g['L_PIT_P_NM'].strip()}" if (g.get("L_PIT_P_NM") or "").strip() else "",
                                         f"세 {g['SV_PIT_P_NM'].strip()}" if (g.get("SV_PIT_P_NM") or "").strip() else "") if x)
            stage = f"{STAGE[m[1]]} {m[2]}차전" if m else ""
            note = " · ".join(x for x in (stage or (f"{g.get('GAME_INN_NO')}회 무승부" if sa == sh else ""), g.get("S_NM", ""), pit) if x)
            out.append({"id": gid, "date": datetime.datetime.strptime(g["G_DT"], "%Y%m%d").date(), "away": g["AWAY_NM"].strip(),
                        "home": g["HOME_NM"].strip(), "as": sa, "hs": sh, "note": note, "stage": stage})
    return out


def lol(posted):
    now, out = datetime.datetime.utcnow(), []
    for lid, lname in LOL_LEAGUES.items():
        try:
            ev = get_json(f"https://esports-api.lolesports.com/persisted/gw/getSchedule?hl=ko-KR&leagueId={lid}",
                          headers={"x-api-key": LOL_KEY})["data"]["schedule"]["events"]
        except Exception as e:  # noqa: BLE001
            print(f"::warning::lolesports {lname}: {e}"); continue
        for e in ev:
            m = e.get("match") or {}
            if e.get("state") != "completed" or not m.get("id") or ("lol:" + m["id"]) in posted:
                continue
            st = datetime.datetime.strptime(e["startTime"][:19], "%Y-%m-%dT%H:%M:%S")
            if not (now - datetime.timedelta(hours=18) <= st <= now):
                continue
            t = m.get("teams") or []
            if len(t) != 2 or not all(x.get("result") for x in t):
                continue
            nm = lambda x: LCK_KO.get(x.get("code"), x.get("code") or x.get("name"))
            bo = (m.get("strategy") or {}).get("count")
            out.append({"id": "lol:" + m["id"], "date": (st + datetime.timedelta(hours=9)).date(), "away": nm(t[0]), "home": nm(t[1]),
                        "as": str(t[0]["result"].get("gameWins", 0)), "hs": str(t[1]["result"].get("gameWins", 0)),
                        "note": " · ".join(x for x in (f"{lname} {e.get('blockName') or ''}".strip(), f"Bo{bo}" if bo else "") if x),
                        "stage": f"{lname} {e.get('blockName') or ''}".strip()})
    out.sort(key=lambda x: x["id"])
    return out


def load_posted():
    return json.load(open(POSTED, encoding="utf-8")) if os.path.exists(POSTED) else {"posted": {}}


def finished_new():
    posted = load_posted()["posted"]
    return {"kbo": kbo(posted), "lol": lol(posted)}


def git(*a):
    subprocess.run(["git", *a], cwd=ROOT, check=True)


def push(msg, paths):
    git("add", *paths)
    if subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=ROOT).returncode == 0:
        return
    git("commit", "-q", "-m", msg)
    for _ in range(3):
        if subprocess.run(["git", "push", "-q"], cwd=ROOT).returncode == 0:
            return
        git("pull", "-q", "--rebase", "--autostash", "origin", "main")
    sys.exit("::error::push failed")


def ig(method, path, token, **params):
    params["access_token"] = token
    body = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{path}" + ("?" + body.decode() if method == "GET" else ""), data=None if method == "GET" else body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} → HTTP {e.code}: {e.read().decode(errors='replace')[:400]}")


def title_of(sport, games):
    if len(games) > 1:
        return f"{games[0]['stage'] or ('KBO' if sport == 'kbo' else 'LoL')} {len(games)}경기 결과" if sport == "lol" else f"오늘 KBO {len(games)}경기 결과"
    x = games[0]
    if x["as"] == x["hs"]:
        return f"{x['away']}·{x['home']} 무승부"
    w = x["away"] if int(x["as"]) > int(x["hs"]) else x["home"]
    return f"{w}, {x['stage']} 승리" if x["stage"] else f"{w} 승리"


def publish_story(rel):
    token, uid = os.environ.get("IG_SPORTS_ACCESS_TOKEN", "").strip(), os.environ.get("IG_SPORTS_USER_ID", "").strip()
    expect = os.environ.get("EXPECT_SPORTS_USERNAME", "hannun.sports").strip().lstrip("@")
    if not token or not uid:
        raise RuntimeError("IG_SPORTS_ACCESS_TOKEN / IG_SPORTS_USER_ID 없음")
    me = ig("GET", "me", token, fields="user_id,username")
    if str(me.get("user_id")) != uid or (expect and me.get("username") != expect):
        raise RuntimeError(f"토큰 계정이 @{expect} 가 아님 — 중단")
    url, t0 = PAGES + rel, time.time()
    while True:   # Pages 배포(보통 1~2분)를 기다린다
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
                if r.status == 200:
                    break
        except Exception:  # noqa: BLE001
            pass
        if time.time() - t0 > 900:
            raise RuntimeError(f"공개 주소에 이미지가 안 뜸: {url}")
        time.sleep(20)
    cid = ig("POST", f"{uid}/media", token, media_type="STORIES", image_url=url)["id"]
    for _ in range(30):
        st = ig("GET", cid, token, fields="status_code").get("status_code")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {st}")
        time.sleep(5)
    pid = ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]
    return pid


def main():
    if MODE == "off":
        print("score alert: off"); return
    new = finished_new()
    n = sum(len(v) for v in new.values())
    if "--check" in sys.argv:
        print(f"score alert: " + ", ".join(f"{k} {len(v)}" for k, v in new.items()))
        with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
            f.write(f"has_new={1 if n else 0}\n")
        return
    if not n:
        print("score alert: nothing new"); return
    failed = []
    for sport, games in new.items():
        if not games:
            continue
        games = games[:5]
        gdate = max(g["date"] for g in games)
        rel = f"sports/alerts/{gdate:%Y-%m}/{gdate}_{sport}_{kst():%H%M}.jpg"
        os.makedirs(os.path.dirname(os.path.join(ROOT, rel)), exist_ok=True)
        spec = os.path.join(ROOT, "sports/alerts/.games.json")
        json.dump({**SPORT[sport], "story": True, "date": str(gdate), "title": title_of(sport, games),
                   "games": [{k: g[k] for k in ("away", "home", "as", "hs", "note")} for g in games]}, open(spec, "w", encoding="utf-8"), ensure_ascii=False)
        subprocess.run(["node", os.path.join(ROOT, "tools/score_card.js"), spec, os.path.join(ROOT, rel)], check=True)
        os.remove(spec)
        db = load_posted()
        for g in games:
            db["posted"][g["id"]] = {"image": rel, "status": "dry" if MODE == "dry" else "pending", "at_kst": kst().strftime("%Y-%m-%d %H:%M"),
                                     "score": f"{g['away']} {g['as']}:{g['hs']} {g['home']}"}
        json.dump(db, open(POSTED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        push(f"결과 알림 카드 {sport} {gdate} ({len(games)}경기) [skip ci]", [rel, POSTED])
        print(f"{sport}: {title_of(sport, games)} → {rel}")
        if MODE == "dry":
            continue
        try:
            pid, status = publish_story(rel), "published"
            print(f"story published: {pid}")
        except Exception as e:  # noqa: BLE001
            print(f"::error::{sport} story publish failed: {e}")
            pid, status = str(e)[:300], "failed"
            failed.append(sport)
        db = load_posted()
        for g in games:
            db["posted"][g["id"]].update(status=status, result=pid)
        json.dump(db, open(POSTED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        push(f"결과 알림 {sport} {status} [skip ci]", [POSTED])
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
