#!/usr/bin/env python3
"""스포츠 데이터 릴스(2026-10-26~, 사용자 승인) — score_alert.py 의 감시 회차마다 불린다. AI 없음, 숫자는 공식 기록 API 값 그대로.

  점수(규칙): 한국 선수·팀 · 큰 단계(결승·포스트시즌·롤드컵·챔스) · 빅매치 · 많은 골 · UFC 메인 이벤트 — sports/reels/rules.json
  ① 기준 이상 경기 → 한 경기 릴스: 그 경기 큰 스코어 카드(천천히 확대 = 첫 2초 움직임) → 그날 결과판 → 끝. 배경음악 CC BY.
  ② 하루 두 번(07:40·23:40) → 결과판 묶음 릴스: 그사이 스토리로 나간 결과판들을 차례로(경기 2판 이상일 때).
  대기열 sports/reels/queue.json: 같은 계정 릴스 사이 최소 gap_min 분, 하루 최대 daily_max 편, 점수 높은 것부터, max_age_h 시간 지나면 버린다.
  수습 기간(publish/probation.json "sports-data-reel" ≥ 1): 사용자 승인 기록(<mp4>.review.json, by user) 이 있어야 올린다 — 24시간 기다린다.
  해설(왜 중요한가)은 ⚾ 야구 나이트·⚽ 축구 모닝 루틴 몫 — 루틴은 queue.json 의 scored(점수 기록)를 보고 해설할 경기를 고른다.
"""
import datetime, hashlib, json, os, re, subprocess, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RULES = json.load(open(os.path.join(ROOT, "sports/reels/rules.json"), encoding="utf-8"))
QUEUE = os.path.join(ROOT, "sports/reels/queue.json")
BGM = "audio/cc/upbeat-forever_kevin-macleod_0-30.mp3"
CREDIT = "Upbeat Forever — Kevin MacLeod (incompetech.com) · CC BY 3.0"
TAGS = {"kbo": "#KBO #프로야구 #야구", "mlb": "#MLB #메이저리그 #야구", "lol": "#롤 #LoL #롤드컵", "ufc": "#UFC #격투기",
        "eng.1": "#EPL #프리미어리그 #축구", "esp.1": "#라리가 #축구", "ita.1": "#세리에A #축구", "ger.1": "#분데스리가 #축구",
        "uefa.champions": "#챔피언스리그 #UCL #축구", "uefa.europa": "#유로파리그 #축구"}
EMO = {"kbo": "⚾", "mlb": "⚾", "lol": "🎮", "ufc": "🥊"}


def kst():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)


def load():
    q = json.load(open(QUEUE, encoding="utf-8")) if os.path.exists(QUEUE) else {}
    q.setdefault("items", []); q.setdefault("scored", {}); q.setdefault("last_post", 0); q.setdefault("bundles", {})
    return q


def save(q):
    cut = (kst() - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
    q["items"] = [i for i in q["items"] if i["made_kst"][:10] >= cut]
    q["scored"] = {k: v for k, v in q["scored"].items() if v.get("at", "")[:10] >= cut}
    json.dump(q, open(QUEUE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def score(sport, row, title):
    P, why = RULES["points"], []
    text = f"{title} {row.get('note', '')}"
    names = {row.get("away", ""), row.get("home", "")}
    s = 0
    if sport == "kbo":
        s += P["kbo"]; why.append("KBO")
    elif names & set(RULES["korean_teams"]) or (sport == "lol" and names & set(RULES["lck_teams"])) \
            or (sport == "ufc" and names & set(RULES["korean_fighters"])):
        s += P["korean"]; why.append("한국")
    if re.search(r"한국시리즈|월드시리즈|결승", text):
        s += P["final_stage"]; why.append("결승급")
    elif re.search(r"플레이오프|챔피언십시리즈|디비전시리즈|와일드카드|준플레이오프|8강|4강|Knockout|Playoffs", text):
        s += P["big_stage"]; why.append("포스트시즌")
    if sport == "lol" and "롤드컵" in title:
        s += P["worlds"]; why.append("롤드컵")
    if sport == "uefa.champions":
        s += P["ucl"]; why.append("챔스")
    big = len(names & set(RULES["big_clubs"]))
    if big == 2:
        s += P["big_both"]; why.append("빅매치")
    elif big == 1:
        s += P["big_one"]; why.append("빅클럽")
    if sport in ("eng.1", "esp.1", "ita.1", "ger.1", "uefa.champions", "uefa.europa") and str(row.get("as", "")).isdigit() and str(row.get("hs", "")).isdigit() \
            and int(row["as"]) + int(row["hs"]) >= 5:
        s += P["many_goals"]; why.append("5골+")
    if row.get("_main"):
        s += P["ufc_main"]; why.append("메인 이벤트")
    return s, why


def ff(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)


def kenburns(img, sec, out, z=0.08):
    """정지 그림 → 천천히 확대되는 영상(첫 2초부터 움직임)."""
    n = int(sec * 30)
    ff("-loop", "1", "-i", img, "-vf", f"scale=2160:-1,zoompan=z='1+{z}*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1080x1920:fps=30,format=yuv420p,setsar=1",
       "-frames:v", str(n), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1", "-preset", "veryfast", "-crf", "20", out)


def stitch(clips, out, sec_total):
    """클립을 0.35초 겹쳐 잇고 배경음악."""
    ins = sum([["-i", c] for c in clips], [])
    durs = [float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", c]).decode()) for c in clips]
    f, cur, off = [], "[0:v]", 0.0
    for k in range(1, len(clips)):
        off += durs[k - 1] - 0.35
        f.append(f"{cur}[{k}:v]xfade=transition=fade:duration=0.35:offset={off:.3f}[x{k}]"); cur = f"[x{k}]"
    total = sum(durs) - 0.35 * (len(clips) - 1)
    A = len(clips)
    f.append(f"[{A}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,afade=t=out:st={total - 1.2:.3f}:d=1.2,volume=0.9[a]")
    ff(*ins, "-stream_loop", "-1", "-i", os.path.join(ROOT, BGM), "-filter_complex", ";".join(f), "-map", cur if len(clips) > 1 else "[0:v]", "-map", "[a]",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1", "-preset", "medium", "-crf", "21", "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.3f}", "-movflags", "+faststart", out)
    return total


def card(spec, out):
    p = out[:-4] + ".spec.json"
    json.dump(spec, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    subprocess.run(["node", os.path.join(ROOT, "tools/score_card.js"), p, out], check=True)
    os.remove(p)


def caption_game(sport, label, row, note_src):
    e = EMO.get(sport, "⚽")
    if sport == "ufc":
        w, l = (row["away"], row["home"]) if row.get("win") == "a" else (row["home"], row["away"])
        head = f"[{e} {label}] {w} 승 — 상대 {l}"
    else:
        head = f"[{e} {label}] {row['away']} {row['as']}:{row['hs']} {row['home']}"
    lines = [head]
    if row.get("note"):
        lines.append(row["note"])
    lines += ["", f"📊 {note_src}", f"🎵 음악: {CREDIT}", "▶ 해설·전체 결과는 프로필 링크의 앱에서", "", TAGS.get(sport, "#스포츠")]
    return "\n".join(lines)


def on_board(bd, rel, sport_meta, label, title_of, dry):
    """스토리 결과판 하나가 나간 뒤: 새로 끝난 경기마다 점수를 매기고, 기준 이상이면 한 경기 릴스를 만들어 대기열에. 만든 파일 목록을 돌려준다."""
    if bd.get("live") or bd.get("pre"):
        return []
    q, made, sport = load(), [], bd["sport"]
    rows = [r for r in bd["rows"] if r.get("gid") in bd["new"] and not r.get("pending")]
    if sport == "ufc" and bd["rows"] and bd["rows"][-1] in rows:
        bd["rows"][-1]["_main"] = True
    for r in rows:
        gid = r["gid"]
        if gid in q["scored"]:
            continue
        s, why = score(sport, r, bd["title"])
        q["scored"][gid] = {"score": s, "why": why, "sport": sport, "title": f"{r['away']} {r['as']}:{r['hs']} {r['home']}", "at": kst().strftime("%Y-%m-%d %H:%M")}
        print(f"  점수 {gid}: {s} ({'·'.join(why) or '-'})")
        if s < RULES["threshold"]:
            continue
        d = kst()
        base = f"reels/sports/{d:%Y-%m}/{d:%Y-%m-%d}_{re.sub(r'[^a-z0-9]+', '-', gid)}"
        os.makedirs(os.path.join(ROOT, os.path.dirname(base)), exist_ok=True)
        tmp = f"/tmp/sreel-{gid.replace(':', '-')}"
        os.makedirs(tmp, exist_ok=True)
        title = bd["title"] if len(bd["rows"]) == 1 else title_of(label, [r])
        card({**sport_meta, "kicker": "🔥 주목 경기", "story": True, "date": str(bd.get("kst_date") or bd["date"]), "dawn": bool(bd.get("dawn")),
              "title": title, "games": [{k: v for k, v in r.items() if not k.startswith("_")}]}, f"{tmp}/one.jpg")
        kenburns(f"{tmp}/one.jpg", 5.5, f"{tmp}/a.mp4")
        clips = [f"{tmp}/a.mp4"]
        if len(bd["rows"]) > 1:
            kenburns(os.path.join(ROOT, rel), 4.0, f"{tmp}/b.mp4", z=0.03); clips.append(f"{tmp}/b.mp4")
        total = stitch(clips, os.path.join(ROOT, base + ".mp4"), 0)
        cap = caption_game(sport, label, r, sport_meta.get("src", "").replace("기록: ", "기록: ").split(" · 해설")[0])
        open(os.path.join(ROOT, base + ".txt"), "w", encoding="utf-8").write(cap + "\n")
        q["items"].append({"id": gid, "kind": "game", "mp4": base + ".mp4", "caption": base + ".txt", "score": s, "why": why, "seconds": round(total, 1),
                           "made_kst": kst().strftime("%Y-%m-%d %H:%M"), "status": "dry" if dry else "queued"})
        made += [base + ".mp4", base + ".txt"]
        print(f"  한 경기 릴스: {base}.mp4 ({total:.1f}초, 점수 {s})")
    save(q)
    return made + [os.path.relpath(QUEUE, ROOT)]


def maybe_bundle(posted, dry):
    """07:40·23:40 — 그사이 스토리로 나간 결과판(종목·날짜마다 마지막 판)을 묶음 릴스로."""
    now, q = kst(), load()
    due = None
    for t in RULES["bundle_at"]:
        hh, mm = map(int, t.split(":"))
        at = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if at <= now < at + datetime.timedelta(hours=2) and f"{now:%Y-%m-%d}_{t}" not in q["bundles"]:
            due = (t, at)
    if not due:
        return []
    t, at = due
    prev = max([x for x in (at - datetime.timedelta(hours=h) for h in range(1, 25))
                if f"{x:%H:%M}" in RULES["bundle_at"]] or [at - datetime.timedelta(hours=16)])
    key = f"{now:%Y-%m-%d}_{t}"
    q["bundles"][key] = {"made_kst": now.strftime("%Y-%m-%d %H:%M")}
    last = {}
    for gid, v in posted.items():
        if gid.startswith(("live:", "pre:")) or v.get("status") not in ("published", "dry"):
            continue
        ts = datetime.datetime.strptime(v["at_kst"], "%Y-%m-%d %H:%M")
        m = re.search(r"/(\d{4}-\d{2}-\d{2})_([a-z0-9-]+)_(\d{4})\.jpg$", v.get("image", ""))
        if m and prev <= ts < at + datetime.timedelta(hours=2):
            k = (m[1], m[2])
            if k not in last or v["image"] > last[k]:
                last[k] = v["image"]
    imgs = sorted(last.values())[:8]
    if len(imgs) < RULES["bundle_min_boards"]:
        q["bundles"][key]["skip"] = f"결과판 {len(imgs)}개"
        save(q); return [os.path.relpath(QUEUE, ROOT)]
    tmp = f"/tmp/sbundle-{key}"; os.makedirs(tmp, exist_ok=True)
    clips = []
    for i, im in enumerate(imgs):
        kenburns(os.path.join(ROOT, im), 3.2 if i else 3.6, f"{tmp}/{i}.mp4", z=0.06 if i == 0 else 0.03); clips.append(f"{tmp}/{i}.mp4")
    base = f"reels/sports/{now:%Y-%m}/{key.replace(':', '')}_bundle"
    os.makedirs(os.path.join(ROOT, os.path.dirname(base)), exist_ok=True)
    total = stitch(clips, os.path.join(ROOT, base + ".mp4"), 0)
    label = "밤사이 결과" if t < "12:00" else "오늘 결과"
    titles, src = [], json.load(open(os.path.join(ROOT, "sports/alerts/sources.json"), encoding="utf-8"))
    for im in imgs:
        js, sp = im[:-4] + ".json", re.search(r"_([a-z0-9-]+)_\d{4}\.jpg$", im)[1]
        t = json.load(open(os.path.join(ROOT, js), encoding="utf-8")).get("title", "") if os.path.exists(os.path.join(ROOT, js)) else ""
        titles.append(t or f"{src.get(sp.replace('-', '.'), {}).get('label', sp)} 결과")
    sports = sorted({re.search(r"_([a-z0-9-]+)_\d{4}\.jpg$", im)[1] for im in imgs})
    cap = "\n".join([f"[🏟 {label}] 결과판 {len(imgs)}장 한 번에", *[f"· {x}" for x in titles if x], "",
                     "📊 기록: 각 리그 공식 기록·ESPN 스코어보드", f"🎵 음악: {CREDIT}", "▶ 해설은 ⚾ 야구 나이트·⚽ 축구 모닝 (프로필 링크의 앱)", "",
                     " ".join((TAGS.get(s.replace("-", "."), "").split() or ["#스포츠"])[0] for s in sports[:4]) + " #경기결과"])   # 해시태그 5개 이하(README 캡션 규칙)
    open(os.path.join(ROOT, base + ".txt"), "w", encoding="utf-8").write(cap + "\n")
    q["items"].append({"id": f"bundle:{key}", "kind": "bundle", "mp4": base + ".mp4", "caption": base + ".txt", "score": RULES["bundle_score"],
                       "seconds": round(total, 1), "made_kst": now.strftime("%Y-%m-%d %H:%M"), "status": "dry" if dry else "queued"})
    save(q)
    print(f"  결과판 묶음 릴스: {base}.mp4 ({total:.1f}초, {len(imgs)}판)")
    return [base + ".mp4", base + ".txt", os.path.relpath(QUEUE, ROOT)]


def probation_left():
    p = os.path.join(ROOT, "publish/probation.json")
    return int(json.load(open(p, encoding="utf-8")).get("sports-data-reel", 0)) if os.path.exists(p) else 0


def approved(mp4, need_user):
    rec = os.path.join(ROOT, mp4[:-4] + ".review.json")
    if not os.path.exists(rec):
        return False
    r = json.load(open(rec, encoding="utf-8"))
    h = hashlib.sha1(open(os.path.join(ROOT, mp4), "rb").read()).hexdigest()
    return r.get("verdict") == "PASS" and r.get("sha1") == h and (r.get("by") == "user" or not need_user)


def next_item():
    """지금 올릴 항목(없으면 None). 간격·하루 최대·나이·수습 승인을 본다. 오래된 항목은 expired 로."""
    q, now = load(), kst()
    today = sum(1 for i in q["items"] if i.get("status") == "published" and i.get("posted_kst", "")[:10] == f"{now:%Y-%m-%d}")
    prob = probation_left() > 0
    changed = False
    for i in q["items"]:
        age = (now - datetime.datetime.strptime(i["made_kst"], "%Y-%m-%d %H:%M")).total_seconds() / 3600
        if i["status"] == "queued" and age > (24 if prob else RULES["max_age_h"]):
            i["status"] = "expired"; changed = True
    if changed:
        save(q)
    if time.time() - q["last_post"] < 60 * RULES["gap_min"] or today >= RULES["daily_max"]:
        return None
    cand = [i for i in q["items"] if i["status"] == "queued" and (not prob or approved(i["mp4"], True))]
    if prob:
        for i in q["items"]:
            if i["status"] == "queued" and i not in cand and not i.get("asked"):
                print(f"::notice::수습 기간 — 사용자 승인 대기: {i['mp4']} (python3 tools/check_reel.py {i['mp4']} --approve --by user)")
    return max(cand, key=lambda i: (i["score"], i["made_kst"])) if cand else None


def mark(item_id, status, result=""):
    q = load()
    for i in q["items"]:
        if i["id"] == item_id:
            i.update(status=status, result=str(result)[:300], posted_kst=kst().strftime("%Y-%m-%d %H:%M"))
    if status == "published":
        q["last_post"] = time.time()
    save(q)
