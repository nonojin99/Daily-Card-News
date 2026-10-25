#!/usr/bin/env python3
"""경기 결과 알림 — 스토리(2026-10-23~). 경기가 끝나면 AI·토큰 없이 공식 기록만으로 결과 카드를 만들어 @hannun.sports **스토리**에 올린다.
피드(그리드)는 야구 나이트·축구 모닝 같은 시리즈만 두고, 실시간 결과는 24시간 뒤 사라지는 스토리로(사용자 결정 2026-10-24).

  python3 score_alert.py --check   새로 끝난 경기가 있으면 GITHUB_OUTPUT 에 has_new=1 (브라우저 설치를 아끼려고 먼저 확인만)
  python3 score_alert.py --watch 355   355분 동안 5분마다 확인·게시(2026-10-24~ — GitHub 15분 예약 실행이 자주 건너뛰어져, 경기 시간대에 한 번 띄워 길게 지켜본다)
  python3 score_alert.py           종목마다 카드 1장(최대 5경기 묶음, tools/score_card.js) → 커밋·push → 공개 주소 확인 → 스토리 게시 → 기록

데이터(어떤 종목을 볼지는 sports/alerts/sources.json, 한국어 팀 이름은 sports/alerts/names_ko.json)
- ⚾ KBO: koreabaseball.com 스코어보드 JSON(GetKboGameList). GAME_STATE_SC "3" + 정상경기 = 종료. 오늘(KST), 새벽 3시 전이면 어제도.
- 🎮 LoL: lolesports.com 일정 API(getSchedule — 사이트가 쓰는 공개 키). 롤드컵·MSI·퍼스트 스탠드·LCK, state "completed" 이고 시작 18시간 안.
- ⚾ MLB: MLB 공식 Stats API(statsapi.mlb.com/api/v1/schedule). abstractGameState "Final".
- ⚽🏀🏈 그 밖: ESPN 공개 스코어보드(site.api.espn.com) — EPL·라리가·세리에 A·분데스리가·챔피언스리그·유로파리그, NBA·NFL(기본 꺼짐).
  공식 문서가 없는 공개 주소라 바뀌면 그 종목만 경고를 남기고 건너뛴다.
- 같은 날 결과판은 sources.json 의 every(분) 간격으로만 다시 올리고, 그날 경기가 모두 끝난 최종 판은 꼭 올린다(스토리가 쏟아지지 않게).
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
FRESH_H = 6   # 시작한 지 6시간이 지난 경기는 새로 올리지 않는다(2026-10-24 사용자: '너무 예전 것' — 이어 달리기로 5분마다 보니 짧아도 놓치지 않는다)
SOURCES = json.load(open(os.path.join(ROOT, "sports/alerts/sources.json"), encoding="utf-8"))
NAMES = json.load(open(os.path.join(ROOT, "sports/alerts/names_ko.json"), encoding="utf-8"))
ESPN = {"eng.1": "soccer", "esp.1": "soccer", "ita.1": "soccer", "ger.1": "soccer", "uefa.champions": "soccer", "uefa.europa": "soccer",
        "nba": "basketball", "nfl": "football"}
KICK = {"soccer": ("⚽ 경기 종료", "#2f6b45", "⚽ 축구 모닝"), "basketball": ("🏀 경기 종료", "#9a5b14", "다음 날 브리프"), "football": ("🏈 경기 종료", "#9a5b14", "다음 날 브리프")}
SPORT = {"kbo": {"kicker": "⚾ 경기 종료", "accent": "#1f5f8b", "src": "기록: KBO 공식 기록 · 해설은 오늘 밤 ⚾ 야구 나이트", "foot": "야구 결과"},
         "lol": {"kicker": "🎮 경기 종료", "accent": "#4a4fa0", "src": "기록: LoL Esports 공식 일정 · 해설은 🎮 e스포츠 브리프", "foot": "e스포츠 결과"},
         "ufc": {"kicker": "🥊 경기 종료", "accent": "#8a2b2b", "src": "기록: ESPN 스코어보드 · 큰 대회 해설은 🏆 이벤트 픽", "foot": "UFC 결과"},
         "mlb": {"kicker": "⚾ 경기 종료", "accent": "#1f5f8b", "src": "기록: MLB 공식 Stats API · 해설은 ⚾ 야구 나이트", "foot": "MLB 결과"}}
for k, kind in ESPN.items():
    kk, ac, br = KICK[kind]
    SPORT[k] = {"kicker": kk, "accent": ac, "src": f"기록: ESPN 스코어보드 · 해설은 {br}", "foot": f"{SOURCES.get(k, {}).get('label', k)} 결과"}
ko = lambda name: NAMES.get(name, name)


LIVE_STYLE = {"kicker": "⚾ 중간 스코어", "src": "진행 중인 경기 · 공식 기록 기준 · 최종 결과는 경기 종료 후 다시 올려요", "foot": "포스트시즌 중간 스코어"}

PRE_STYLE = {"kicker": "⚾ 경기 전 · 선발", "src": "선발은 MLB 공식 Stats API·KBO 공식 기록의 예고 기준 · 경기 직전 바뀔 수 있어요", "foot": "포스트시즌 선발 안내"}


def kst():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def get_json(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def kbo(posted):
    """새로 끝난 경기가 있는 날마다 그날 전 경기 결과판 하나: {"sport","date","title","rows","new"}"""
    now, boards = kst(), []
    for d in [now.date()] + ([now.date() - datetime.timedelta(days=1)] if now.hour < 3 else []):
        try:
            games = get_json("https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList",
                             urllib.parse.urlencode({"leId": "1", "srId": "0,1,3,4,5,6,7,8,9", "date": d.strftime("%Y%m%d")}).encode(),
                             {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest",
                              "Referer": "https://www.koreabaseball.com/Schedule/ScoreBoard.aspx"}).get("game") or []
        except Exception as e:  # noqa: BLE001 — 사이트가 막히거나 바뀌면 이번 회차는 건너뛴다
            print(f"::warning::KBO scoreboard {d}: {e}"); continue
        rows, new, stage = [], [], ""
        for g in games:
            gid = "kbo:" + g["G_ID"]
            m = re.match(r"(준PO|PO|KS|WC)(\d+)", g.get("GAME_SC_NM") or "")
            stage = f"{STAGE[m[1]]} {m[2]}차전" if m else stage
            done = str(g.get("GAME_STATE_SC")) == "3" and str(g.get("CANCEL_SC_ID")) == "0"
            cancel = str(g.get("CANCEL_SC_ID")) not in ("0", "None")
            sa, sh = (str(g["T_SCORE_CN"]), str(g["B_SCORE_CN"])) if done else ("-", "-")
            pit = " · ".join(f"{k} {(g.get(f) or '').strip()}" for k, f in (("승", "W_PIT_P_NM"), ("패", "L_PIT_P_NM"), ("세", "SV_PIT_P_NM")) if (g.get(f) or "").strip())
            state = (f"{g.get('GAME_INN_NO')}회 무승부" if done and sa == sh else pit) if done else (g.get("CANCEL_SC_NM") or "취소") if cancel else \
                    ("진행 중" if str(g.get("GAME_STATE_SC")) == "2" else f"{g.get('G_TM', '')} 시작")
            rows.append({"gid": gid, "away": g["AWAY_NM"].strip(), "home": g["HOME_NM"].strip(), "as": sa, "hs": sh, "pending": not done,
                         "note": " · ".join(x for x in (g.get("S_NM", ""), state) if x)})
            if done and gid not in posted and g["G_ID"] not in posted:
                new.append(gid)
        if new:
            fin = sum(not r["pending"] for r in rows)
            title = (f"{stage}" if len(rows) == 1 and stage else f"오늘 KBO {len(rows)}경기") + (f" — {fin}/{len(rows)} 종료" if fin < len(rows) else " 결과")
            boards.append({"sport": "kbo", "date": d, "title": title, "rows": rows, "new": new})
    return boards


def lol(posted):
    """리그마다, 새로 끝난 경기가 있는 날(KST)의 그날 전 경기 결과판. 남은 경기는 '- : -'와 시작 시각(KST)."""
    now, boards = datetime.datetime.utcnow(), []
    for lid, lname in LOL_LEAGUES.items():
        try:
            ev = get_json(f"https://esports-api.lolesports.com/persisted/gw/getSchedule?hl=ko-KR&leagueId={lid}",
                          headers={"x-api-key": LOL_KEY})["data"]["schedule"]["events"]
        except Exception as e:  # noqa: BLE001
            print(f"::warning::lolesports {lname}: {e}"); continue
        ks = lambda e: datetime.datetime.strptime(e["startTime"][:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=9)
        days = set()
        for e in ev:
            m = e.get("match") or {}
            st = ks(e) - datetime.timedelta(hours=9)
            if e.get("state") == "completed" and m.get("id") and ("lol:" + m["id"]) not in posted and now - datetime.timedelta(hours=FRESH_H) <= st <= now:
                days.add(ks(e).date())
        for d in sorted(days):
            todays = [e for e in ev if ks(e).date() == d and (e.get("match") or {}).get("teams")]
            block = todays[0].get("blockName") or ""
            same = sorted({ks(e).date() for e in ev if (e.get("blockName") or "") == block and ks(e).year == d.year})
            nth = same.index(d) + 1 if d in same else 0
            nm = lambda x: LCK_KO.get(x.get("code"), x.get("code") or x.get("name") or "TBD")
            rows, new = [], []
            for e in sorted(todays, key=lambda e: e["startTime"]):
                m, t = e["match"], e["match"]["teams"]
                done = e.get("state") == "completed" and all(x.get("result") for x in t)
                bo = (m.get("strategy") or {}).get("count")
                state = "" if done else ("진행 중" if e.get("state") == "inProgress" else f"{ks(e):%H:%M} 시작")
                rows.append({"gid": "lol:" + m["id"], "away": nm(t[0]), "home": nm(t[1]), "pending": not done,
                             "as": str(t[0]["result"].get("gameWins", 0)) if done else "-", "hs": str(t[1]["result"].get("gameWins", 0)) if done else "-",
                             "note": " · ".join(x for x in (f"Bo{bo}" if bo else "", state) if x)})
                if done and ("lol:" + m["id"]) not in posted:
                    new.append("lol:" + m["id"])
            fin = sum(not r["pending"] for r in rows)
            title = f"{lname} {block}{f' {nth}일차' if nth else ''} — " + (f"{fin}/{len(rows)} 종료" if fin < len(rows) else "결과")
            boards.append({"sport": "lol", "date": d, "title": title, "rows": rows, "new": new})
    return boards


def board_title(label, rows, single_note=""):
    """'EPL — 3/7 종료' · 다 끝나면 'EPL 결과'. 한 경기면 '밀워키, 월드시리즈 1차전 승리'."""
    fin = sum(not r["pending"] for r in rows)
    if len(rows) == 1 and fin == 1:
        x = rows[0]
        if x["as"] == x["hs"]:
            return f"{label} · {x['away']}·{x['home']} 무승부"
        w = x["away"] if float(x["as"]) > float(x["hs"]) else x["home"]
        return f"{w}, {single_note} 승리" if single_note else f"{label} · {w} 승리"
    return f"{label} — {fin}/{len(rows)} 종료" if fin < len(rows) else f"{label} 결과"


def mlb(posted):
    """MLB 공식 Stats API — KST 날짜별 그날 전 경기 결과판."""
    now, boards = kst(), []
    try:
        d0, d1 = (now - datetime.timedelta(days=1)).date(), now.date()
        dates = get_json(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={d0}&endDate={d1}")["dates"]
    except Exception as e:  # noqa: BLE001
        print(f"::warning::MLB schedule: {e}"); return []
    games = [g for dt in dates for g in dt["games"]]
    ks = lambda g: datetime.datetime.strptime(g["gameDate"][:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=9)
    # 묶음 날짜 = KST 시각에서 12시간 뺀 날(정오~다음 날 정오가 한 '밤') — 미국·유럽 경기가 현지 경기일 기준으로 한 판에 모인다
    gd = lambda g: (ks(g) - datetime.timedelta(hours=12)).date()
    for d in sorted({gd(g) for g in games}):
        todays = sorted([g for g in games if gd(g) == d], key=lambda g: g["gameDate"])
        rows, new, series = [], [], ""
        for g in todays:
            st = g["status"]["abstractGameState"]
            done = st == "Final" and g["status"].get("detailedState") not in ("Postponed", "Cancelled")
            a, h = g["teams"]["away"], g["teams"]["home"]
            ser = g.get("seriesDescription") or ""
            if g.get("gameType") not in ("R", "S", "E") and ser:
                ko_ser = {"World Series": "월드시리즈", "League Championship Series": "챔피언십시리즈", "Division Series": "디비전시리즈",
                          "Wild Card": "와일드카드"}.get(ser, ser)
                series = f"{ko_ser} {g.get('seriesGameNumber', '')}차전".strip()
            state = "" if done else ("진행 중" if st == "Live" else g["status"].get("detailedState") if g["status"].get("detailedState") in ("Postponed", "Cancelled", "Suspended") else f"{ks(g):%H:%M} 시작")
            rows.append({"gid": f"mlb:{g['gamePk']}", "away": ko(a["team"]["name"]), "home": ko(h["team"]["name"]), "pending": not done,
                         "as": str(a.get("score", "-")) if done else "-", "hs": str(h.get("score", "-")) if done else "-",
                         "note": " · ".join(x for x in (series if g.get("gameType") not in ("R", "S", "E") else "", g.get("venue", {}).get("name", ""), state) if x)})
            if done and f"mlb:{g['gamePk']}" not in posted and ks(g) >= now - datetime.timedelta(hours=FRESH_H):
                new.append(f"mlb:{g['gamePk']}")
        if new:
            k0 = min(ks(g) for g in todays)
            boards.append({"sport": "mlb", "date": d, "title": board_title("MLB", rows, series), "rows": rows, "new": new, "kst_date": k0.date(), "dawn": k0.hour < 6})
    return boards


def espn(key, posted):
    """ESPN 공개 스코어보드 — 리그 하나, KST 날짜별 그날 전 경기 결과판."""
    kind, label, now, boards = ESPN[key], SOURCES[key]["label"], kst(), []
    evs = []
    for d in {(now - datetime.timedelta(days=1)).date(), now.date()}:
        try:
            evs += get_json(f"https://site.api.espn.com/apis/site/v2/sports/{kind}/{key}/scoreboard?dates={d:%Y%m%d}").get("events", [])
        except Exception as e:  # noqa: BLE001
            print(f"::warning::ESPN {key} {d}: {e}")
    evs = list({e["id"]: e for e in evs}.values())
    ks = lambda e: datetime.datetime.strptime(e["date"][:16], "%Y-%m-%dT%H:%M") + datetime.timedelta(hours=9)
    gd = lambda e: (ks(e) - datetime.timedelta(hours=12)).date()   # 정오~다음 날 정오 = 한 밤(현지 경기일)
    for d in sorted({gd(e) for e in evs}):
        rows, new = [], []
        for e in sorted([e for e in evs if gd(e) == d], key=lambda e: e["date"]):
            t = e["competitions"][0]["competitors"]
            a = next((x for x in t if x.get("homeAway") == "away"), t[0]); h = next((x for x in t if x.get("homeAway") == "home"), t[-1])
            st = e["status"]["type"]
            done = bool(st.get("completed"))
            name = st.get("name", "")
            state = "" if done else ("연기" if "POSTPONED" in name else "취소" if "CANCELED" in name else "진행 중" if st.get("state") == "in" else f"{ks(e):%H:%M} 시작")
            rows.append({"gid": f"{key}:{e['id']}", "away": ko(a["team"].get("shortDisplayName") or a["team"].get("displayName")), "home": ko(h["team"].get("shortDisplayName") or h["team"].get("displayName")),
                         "pending": not done, "as": str(a.get("score", "-")) if done else "-", "hs": str(h.get("score", "-")) if done else "-", "note": state})
            if done and f"{key}:{e['id']}" not in posted and ks(e) >= now - datetime.timedelta(hours=FRESH_H):
                new.append(f"{key}:{e['id']}")
        if new:
            k0 = min(ks(e) for e in evs if gd(e) == d)   # 판의 첫 경기 KST — 카드에는 묶음 날짜가 아니라 이 날짜(오전이면 '새벽')
            boards.append({"sport": key, "date": d, "title": board_title(label, rows), "rows": rows, "new": new, "kst_date": k0.date(), "dawn": k0.hour < 12})
    return boards


WEIGHT = {"Strawweight": "스트로급", "Flyweight": "플라이급", "Bantamweight": "밴텀급", "Featherweight": "페더급", "Lightweight": "라이트급",
          "Welterweight": "웰터급", "Middleweight": "미들급", "Light Heavyweight": "라이트헤비급", "Heavyweight": "헤비급", "Catchweight": "계약 체중"}


def ufc(posted):
    """UFC(ESPN mma/ufc) — 대회 하나 = 결과판 하나, 메인 카드 쪽 마지막 8경기(스토리 한 장에 들어가는 만큼). 결과는 '승'·'패', 끝난 라운드·시간 또는 판정.
    끝낸 방법(KO·서브미션)은 데이터에 없어 쓰지 않는다."""
    now, boards, evs = kst(), [], []
    for d in {(now - datetime.timedelta(days=1)).date(), now.date()}:
        try:
            evs += get_json(f"https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates={d:%Y%m%d}").get("events", [])
        except Exception as e:  # noqa: BLE001
            print(f"::warning::ESPN ufc {d}: {e}")
    for e in {e["id"]: e for e in evs}.values():
        bouts = e.get("competitions") or []
        rows, new = [], []
        for c in bouts[-8:]:
            t = sorted(c.get("competitors") or [], key=lambda x: x.get("order", 0))
            if len(t) != 2:
                continue
            st = (c.get("status") or {}).get("type", {})
            done = bool(st.get("completed"))
            wc = ((c.get("type") or {}).get("abbreviation") or "")
            wk = ("여성 " if wc.startswith("W ") else "") + WEIGHT.get(wc[2:] if wc.startswith("W ") else wc, wc)
            w = 0 if t[0].get("winner") else 1 if t[1].get("winner") else None
            per, clk = (c.get("status") or {}).get("period"), (c.get("status") or {}).get("displayClock")
            how = ("판정" if any(x.get("linescores") for x in t) else f"{per}R {clk}") if done and per else ""
            ks_ = datetime.datetime.strptime((c.get("date") or e["date"])[:16], "%Y-%m-%dT%H:%M") + datetime.timedelta(hours=9)
            state = how if done else ("진행 중" if st.get("state") == "in" else f"{ks_:%H:%M} 예정")
            rows.append({"gid": f"ufc:{c['id']}", "away": ko(t[0]["athlete"]["displayName"]), "home": ko(t[1]["athlete"]["displayName"]), "pending": not done,
                         "as": ("승" if w == 0 else "패" if w == 1 else "무") if done else "-", "hs": ("승" if w == 1 else "패" if w == 0 else "무") if done else "-",
                         "win": ("a" if w == 0 else "h" if w == 1 else "") if done else "", "note": " · ".join(x for x in (wk, state) if x)})
            if done and f"ufc:{c['id']}" not in posted and ks_ >= now - datetime.timedelta(hours=FRESH_H):
                new.append(f"ufc:{c['id']}")
        if new:
            fin = sum(not r["pending"] for r in rows)
            name = e.get("shortName") or e.get("name", "UFC")
            d0 = (datetime.datetime.strptime(e["date"][:16], "%Y-%m-%dT%H:%M") + datetime.timedelta(hours=9)).date()
            nm = e.get("name", "UFC")   # 'UFC 333: Volkanovski vs. Evloev' — 메인 이벤트 성(姓)은 names_ko 에 있으면 한국어로
            main = " vs ".join(ko(x.strip().rstrip(".")) for x in nm.split(":", 1)[1].split("vs.")) if ":" in nm and "vs." in nm else ""
            boards.append({"sport": "ufc", "date": d0, "title": f"{nm.split(':')[0]}{': ' + main if main else ''} — " + (f"{fin}/{len(rows)} 종료" if fin < len(rows) else "결과"),
                           "rows": rows, "new": new})
    return boards


LIVE_STEPS = ((7, "6회"), (4, "3회"))   # (이 회 이상이면 그 단계). 가장 높은 단계 하나만 올린다 — 경기당 중간 스토리 최대 2장(3회 마침·6회 마침)


def live_big(posted):
    """포스트시즌급 야구(KBO 와일드카드·준PO·PO·KS, MLB 와일드카드·디비전·챔피언십·월드시리즈)만, 경기가 길어서 3회·6회를 마칠 때 중간 스코어 한 장.
    정규시즌 경기는 다루지 않는다(사용자 결정 2026-10-24). 올린 단계는 posted 에 live:<경기>:<회> 로 남겨 중복을 막는다."""
    boards, now = [], kst()

    def step(inn):
        for need, label in LIVE_STEPS:
            if inn >= need:
                return need, label
        return 0, ""

    def add(sport, gid, inn, row, title, gdate, kdate):
        need, label = step(inn)
        if not need or any(k.startswith(f"live:{gid}:") and int(k.rsplit(":", 1)[1]) >= need for k in posted):
            return
        row = {**row, "pending": True, "live": True}
        boards.append({"sport": sport, "live": True, "date": gdate, "kst_date": kdate, "title": title, "rows": [row], "new": [f"live:{gid}:{need}"], "final": False})

    if SOURCES.get("kbo", {}).get("on"):
        d = now.date()
        try:
            games = get_json("https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList",
                             urllib.parse.urlencode({"leId": "1", "srId": "0,1,3,4,5,6,7,8,9", "date": d.strftime("%Y%m%d")}).encode(),
                             {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest",
                              "Referer": "https://www.koreabaseball.com/Schedule/ScoreBoard.aspx"}).get("game") or []
        except Exception as e:  # noqa: BLE001
            print(f"::warning::KBO live {d}: {e}"); games = []
        for g in games:
            m = re.match(r"(준PO|PO|KS|WC)(\d+)", g.get("GAME_SC_NM") or "")
            if not m or str(g.get("GAME_STATE_SC")) != "2":
                continue
            try:
                inn = int(g.get("GAME_INN_NO") or 0)
            except ValueError:
                continue
            tb = (g.get("GAME_TB_SC_NM") or "").strip()
            stage = f"{STAGE[m[1]]} {m[2]}차전"
            add("kbo", "kbo:" + g["G_ID"], inn, {"away": g["AWAY_NM"].strip(), "home": g["HOME_NM"].strip(), "as": str(g["T_SCORE_CN"]), "hs": str(g["B_SCORE_CN"]),
                                                 "note": f"{inn}회{tb} 진행 중" + (f" · {g['S_NM']}" if g.get("S_NM") else "")},
                f"{stage} — 중간 스코어", d, d)
    if SOURCES.get("mlb", {}).get("on"):
        try:
            d0, d1 = (now - datetime.timedelta(days=1)).date(), now.date()
            dates = get_json(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={d0}&endDate={d1}&hydrate=linescore")["dates"]
        except Exception as e:  # noqa: BLE001
            print(f"::warning::MLB live: {e}"); dates = []
        for g in (g for dt in dates for g in dt["games"]):
            if g.get("gameType") not in ("F", "D", "L", "W") or g["status"]["abstractGameState"] != "Live":
                continue
            ls, a, h = g.get("linescore") or {}, g["teams"]["away"], g["teams"]["home"]
            ser = {"World Series": "월드시리즈", "League Championship Series": "챔피언십시리즈", "Division Series": "디비전시리즈",
                   "Wild Card": "와일드카드"}.get(g.get("seriesDescription") or "", g.get("seriesDescription") or "MLB 포스트시즌")
            k0 = datetime.datetime.strptime(g["gameDate"][:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=9)
            add("mlb", f"mlb:{g['gamePk']}", int(ls.get("currentInning") or 0),
                {"away": ko(a["team"]["name"]), "home": ko(h["team"]["name"]), "as": str(a.get("score", 0)), "hs": str(h.get("score", 0)),
                 "note": f"{ls.get('currentInning')}회{'초' if ls.get('isTopInning') else '말'} 진행 중 · {g.get('venue', {}).get('name', '')}".rstrip(" ·")},
                f"{ser} {g.get('seriesGameNumber', '')}차전 — 중간 스코어".replace("  ", " "), (k0 - datetime.timedelta(hours=12)).date(), k0.date())
    return boards


PRE_MIN = 120   # 시작 2시간 전부터(선발이 둘 다 나와 있으면) 한 번만


def mlb_pitch(pid, season):
    """선발 투수 시즌 기록 두 줄: ['정규 16승 5패 · ERA 2.67', '포스트시즌 2승 0패 · ERA 1.29'] (MLB 공식 Stats API). 못 받으면 빈 목록."""
    if not pid:
        return []
    out = []
    for gt, label in (("R", "정규"), ("P", "포스트시즌")):
        try:
            sp = get_json(f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?stats=season&group=pitching&season={season}&gameType={gt}")["stats"][0]["splits"]
        except Exception:  # noqa: BLE001 — 기록이 없거나(첫 등판) 주소가 바뀌면 그 줄만 뺀다
            continue
        if sp:
            s = sp[0]["stat"]
            out.append(f"{label} {s['wins']}승 {s['losses']}패 · ERA {s['era']}")
    return out


def pre_big(posted):
    """포스트시즌급 야구 경기 전 선발 안내(사용자 요청 2026-10-24) — live_big 과 같은 경기만, 시작 PRE_MIN 분 안에 선발 투수가 둘 다 발표돼 있으면 한 장.
    posted 에 pre:<경기> 로 남긴다. 시작했거나 선발이 아직이면 건너뛴다(시작 전 회차에서 다시 본다)."""
    boards, now = [], kst()

    def add(sport, gid, start, row, title, gdate):
        if f"pre:{gid}" in posted or not (now <= start <= now + datetime.timedelta(minutes=PRE_MIN)) or not (row["as"] and row["hs"]):
            return
        boards.append({"sport": sport, "pre": True, "date": gdate, "kst_date": start.date(), "title": title,
                       "rows": [{**row, "pending": True, "pre": True}], "new": [f"pre:{gid}"], "final": False})

    if SOURCES.get("kbo", {}).get("on"):
        d = now.date()
        try:
            games = get_json("https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList",
                             urllib.parse.urlencode({"leId": "1", "srId": "0,1,3,4,5,6,7,8,9", "date": d.strftime("%Y%m%d")}).encode(),
                             {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest",
                              "Referer": "https://www.koreabaseball.com/Schedule/ScoreBoard.aspx"}).get("game") or []
        except Exception as e:  # noqa: BLE001
            print(f"::warning::KBO pre {d}: {e}"); games = []
        for g in games:
            m = re.match(r"(준PO|PO|KS|WC)(\d+)", g.get("GAME_SC_NM") or "")
            tm = re.match(r"(\d{1,2}):(\d{2})", g.get("G_TM") or "")
            if not m or not tm or str(g.get("GAME_STATE_SC")) not in ("1", "None", "") or str(g.get("CANCEL_SC_ID")) not in ("0", "None"):
                continue
            start = datetime.datetime.combine(d, datetime.time(int(tm[1]), int(tm[2])))
            add("kbo", "kbo:" + g["G_ID"], start,
                {"away": g["AWAY_NM"].strip(), "home": g["HOME_NM"].strip(), "as": (g.get("T_PIT_P_NM") or "").strip(), "hs": (g.get("B_PIT_P_NM") or "").strip(),
                 "note": f"{start:%H:%M} 시작" + (f" · {g['S_NM']}" if g.get("S_NM") else "")},
                f"{STAGE[m[1]]} {m[2]}차전 — 오늘의 선발", d)
    if SOURCES.get("mlb", {}).get("on"):
        try:
            d0, d1 = now.date(), (now + datetime.timedelta(days=1)).date()
            dates = get_json(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={d0 - datetime.timedelta(days=1)}&endDate={d1}&hydrate=probablePitcher")["dates"]
        except Exception as e:  # noqa: BLE001
            print(f"::warning::MLB pre: {e}"); dates = []
        for g in (g for dt in dates for g in dt["games"]):
            if g.get("gameType") not in ("F", "D", "L", "W") or g["status"]["abstractGameState"] != "Preview":
                continue
            a, h = g["teams"]["away"], g["teams"]["home"]
            ser = {"World Series": "월드시리즈", "League Championship Series": "챔피언십시리즈", "Division Series": "디비전시리즈",
                   "Wild Card": "와일드카드"}.get(g.get("seriesDescription") or "", g.get("seriesDescription") or "MLB 포스트시즌")
            start = datetime.datetime.strptime(g["gameDate"][:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(hours=9)
            pit = lambda x: ko((x.get("probablePitcher") or {}).get("fullName", ""))
            stat = lambda x: mlb_pitch((x.get("probablePitcher") or {}).get("id"), g.get("season") or now.year)
            add("mlb", f"mlb:{g['gamePk']}", start,
                {"away": ko(a["team"]["name"]), "home": ko(h["team"]["name"]), "as": pit(a), "hs": pit(h), "ast": stat(a), "hst": stat(h),
                 "note": f"한국시간 {start:%H:%M} 시작 · {g.get('venue', {}).get('name', '')}".rstrip(" ·")},
                f"{ser} {g.get('seriesGameNumber', '')}차전 — 오늘의 선발".replace("  ", " "), (start - datetime.timedelta(hours=12)).date())
    return boards


def load_posted():
    return json.load(open(POSTED, encoding="utf-8")) if os.path.exists(POSTED) else {"posted": {}}


def finished_new():
    db = load_posted()
    posted, seen = db["posted"], db.get("boards", {})
    on = lambda k: SOURCES.get(k, {}).get("on")
    boards = (kbo(posted) if on("kbo") else []) + (lol(posted) if on("lol") else []) + (mlb(posted) if on("mlb") else []) + (ufc(posted) if on("ufc") else [])
    for k in ESPN:
        if on(k):
            boards += espn(k, posted)
    out = (live_big(posted) + pre_big(posted)) if on("live") else []   # 경기 전 선발·경기 중 중간 스코어(포스트시즌급 야구만) — 간격 규칙과 무관
    for b in boards:   # 같은 날 판은 every 분 간격으로만, 최종 판(모두 종료)은 꼭
        key, fin = f"{b['sport']}:{b['date']}", all(not r["pending"] for r in b["rows"])
        last = seen.get(key, {}).get("last", 0)
        if not fin and time.time() - last < 60 * SOURCES.get(b["sport"], {}).get("every", 0):
            print(f"{b['sport']} {b['date']}: 간격 안이라 다음 회차에 ({len(b['new'])}경기 대기)"); continue
        b["final"] = fin
        out.append(b)
    return out


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


def publish_reel(rel, caption):
    """스포츠 데이터 릴스 게시(2026-10-26~) — 스토리와 같은 계정·확인 절차, 영상은 처리 시간이 길어 최대 10분 기다린다."""
    token, uid = os.environ.get("IG_SPORTS_ACCESS_TOKEN", "").strip(), os.environ.get("IG_SPORTS_USER_ID", "").strip()
    expect = os.environ.get("EXPECT_SPORTS_USERNAME", "hannun.sports").strip().lstrip("@")
    if not token or not uid:
        raise RuntimeError("IG_SPORTS_ACCESS_TOKEN / IG_SPORTS_USER_ID 없음")
    me = ig("GET", "me", token, fields="user_id,username")
    if str(me.get("user_id")) != uid or (expect and me.get("username") != expect):
        raise RuntimeError(f"토큰 계정이 @{expect} 가 아님 — 중단")
    recent = ig("GET", f"{uid}/media", token, fields="caption,permalink", limit="15").get("data", [])
    if any((r.get("caption") or "").strip() == caption.strip() for r in recent):
        return "already"
    url, t0 = PAGES + rel, time.time()
    while True:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
                if r.status == 200:
                    break
        except Exception:  # noqa: BLE001
            pass
        if time.time() - t0 > 900:
            raise RuntimeError(f"공개 주소에 영상이 안 뜸: {url}")
        time.sleep(20)
    cid = ig("POST", f"{uid}/media", token, media_type="REELS", video_url=url, caption=caption.strip(), share_to_feed="true", is_ai_generated="false")["id"]
    for _ in range(60):
        st = ig("GET", cid, token, fields="status_code").get("status_code")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {st}")
        time.sleep(10)
    return ig("POST", f"{uid}/media_publish", token, creation_id=cid)["id"]


def reels_tick():
    """데이터 릴스: 결과판 묶음 시각이면 만들고, 대기열에서 올릴 차례인 것 하나를 올린다. 실패해도 스토리 감시는 계속."""
    import sports_reels as SR
    try:
        made = SR.maybe_bundle(load_posted()["posted"], MODE == "dry")
        if made:
            push("결과판 묶음 릴스 [skip ci]", made)
        it = SR.next_item()
        if not it or MODE == "dry":
            return
        cap = open(os.path.join(ROOT, it["caption"]), encoding="utf-8").read()
        print(f"데이터 릴스 게시: {it['mp4']} (점수 {it['score']})")
        try:
            pid = publish_reel(it["mp4"], cap)
            SR.mark(it["id"], "published", pid)
        except Exception as e:  # noqa: BLE001
            print(f"::error::sports reel publish failed: {e}")
            SR.mark(it["id"], "failed", e)
        push(f"데이터 릴스 {it['id']} [skip ci]", [os.path.relpath(SR.QUEUE, ROOT)])
    except Exception as e:  # noqa: BLE001
        print(f"::warning::sports reels tick failed: {e}")


def slots_tick():
    """시간대 게시(07:30·12:10·18:40·21:07, 2026-10-26~ 사용자 요청): 예약 실행이 몇 시간씩 늦어 이 루프에서 올린다. 실패해도 스토리 감시는 계속."""
    if MODE == "dry":
        return
    try:
        import publish_slots as PS
        changed = PS.tick()
        if changed:
            push("시간대 게시 처리 [skip ci]", changed)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::slot publish tick failed: {e}")


def main():
    if MODE == "off":
        print("score alert: off"); return
    if "--watch" in sys.argv:
        end = time.time() + 60 * float(sys.argv[sys.argv.index("--watch") + 1])
        bad = 0
        while True:
            try:
                bad += run_once()
            except SystemExit as e:   # push 실패 등 — 다음 회차에 다시
                print(f"::warning::{e}"); bad += 1
            except Exception as e:  # noqa: BLE001
                print(f"::warning::score alert round failed: {e}"); bad += 1
            if time.time() + 300 > end:
                break
            time.sleep(300)
            subprocess.run(["git", "pull", "-q", "--rebase", "--autostash", "origin", "main"], cwd=ROOT)
        if bad:
            sys.exit(1)
        return
    if run_once():
        sys.exit(1)


def run_once():
    """한 번 확인하고 새로 끝난 경기가 있으면 결과판을 게시. 실패한 종목 수를 돌려준다."""
    boards = finished_new()
    if "--check" in sys.argv:
        print("score alert: " + (", ".join(f"{b['sport']} {b['date']} 새 종료 {len(b['new'])}" for b in boards) or "nothing new"))
        with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
            f.write(f"has_new={1 if boards else 0}\n")
        return 0
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    if not boards:
        print(f"{kst():%H:%M} score alert: nothing new"); reels_tick(); slots_tick(); return 0
    failed = []
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from check_sports_data import validate   # 스포츠 데이터 검사(2026-10-25~) — 옮겨 적은 값이 이상하면 그 판은 올리지 않는다
    for bd in boards:
        sport, gdate = bd["sport"], bd["date"]
        bad, warn = validate(bd)
        for w in warn: print(f"::notice::{sport} {gdate}: {w}")
        if bad:
            print(f"::warning::{sport} {gdate} 결과판 게시 보류 — 데이터 검사 FAIL: " + " / ".join(bad))
            continue
        rel = f"sports/alerts/{gdate:%Y-%m}/{gdate}_{sport.replace('.', '-')}_{kst():%H%M}.jpg"
        os.makedirs(os.path.dirname(os.path.join(ROOT, rel)), exist_ok=True)
        spec = os.path.join(ROOT, "sports/alerts/.games.json")
        json.dump({**SPORT[sport], **(LIVE_STYLE if bd.get("live") else PRE_STYLE if bd.get("pre") else {}), "story": True, "date": str(bd.get("kst_date") or gdate), "dawn": bool(bd.get("dawn")), "title": bd["title"], "games": bd["rows"][:10]},
                  open(spec, "w", encoding="utf-8"), ensure_ascii=False)
        subprocess.run(["node", os.path.join(ROOT, "tools/score_card.js"), spec, os.path.join(ROOT, rel)], check=True)
        os.replace(spec, os.path.join(ROOT, rel[:-4] + ".json"))   # 원자료를 jpg 옆에 남긴다(감사·데이터 릴스 재료)
        db = load_posted()
        for gid in bd["new"]:
            db["posted"][gid] = {"image": rel, "status": "dry" if MODE == "dry" else "pending", "at_kst": kst().strftime("%Y-%m-%d %H:%M")}
        json.dump(db, open(POSTED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        push(f"결과 알림 카드 {sport} {gdate} (새 종료 {len(bd['new'])}) [skip ci]", [rel, rel[:-4] + ".json", POSTED])
        print(f"{sport}: {bd['title']} → {rel}")
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
        for gid in bd["new"]:
            db["posted"][gid].update(status=status, result=pid)
        if status == "published" and not (bd.get("live") or bd.get("pre")):
            db.setdefault("boards", {})[f"{sport}:{gdate}"] = {"last": time.time(), "final": bd.get("final", False)}
        json.dump(db, open(POSTED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        push(f"결과 알림 {sport} {status} [skip ci]", [POSTED])
        if status in ("published",) or MODE == "dry":   # 데이터 릴스(2026-10-26~): 점수 기준을 넘은 경기는 한 경기 릴스로
            try:
                import sports_reels as SR
                made = SR.on_board(bd, rel, {k: v for k, v in SPORT[sport].items()}, SOURCES.get(sport, {}).get("label", sport.upper()), board_title, MODE == "dry")
                if made:
                    push(f"데이터 릴스 재료 {sport} {gdate} [skip ci]", made)
            except Exception as e:  # noqa: BLE001
                print(f"::warning::sports reel make failed: {e}")
    reels_tick()
    slots_tick()
    return len(failed)


if __name__ == "__main__":
    main()
