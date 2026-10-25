#!/usr/bin/env python3
"""인스타그램 게시 (Instagram API with Instagram Login).

워크플로 'Publish to Instagram' 에서 수동 실행한다(사람이 보고 누르는 1탭 승인).
  KIND=reel     MEDIA=reels/2026-10/2026-10-17_weekend.mp4
  KIND=carousel MEDIA=cards/2026-10/2026-10-17_weekend        (폴더 안 01.jpg … 최대 10장)
  CAPTION=<캡션 파일 경로>   DRY_RUN=true 면 컨테이너만 만들고 게시하지 않는다.
  KIND=none(또는 빈칸) 이면 아무것도 하지 않는다 — 게시가 끝난 요청 파일은 none 으로 돌려 둔다.
  요청 파일에 "requests": [{…}, {…}] 가 있으면 차례로 처리한다(게시일의 캐러셀 + 오디오 릴스, 2026-10-18~).
  한 건이 실패해도 다음 건은 시도하고, 하나라도 실패하면 마지막에 실패로 끝난다(메일 알림).

안전장치: 토큰의 계정이 IG_USER_ID·EXPECT_USERNAME 과 다르면 중단. 게시 한도를 먼저 확인.
계정: 요청 항목에 "account":"sports" 가 있으면 IG_SPORTS_ACCESS_TOKEN·IG_SPORTS_USER_ID·EXPECT_SPORTS_USERNAME 으로 올린다(2026-10-21~, README '스포츠 계정').
컨테이너는 24시간 뒤 만료되므로 실행할 때 만든다. AI 음성·그림이 있으면 is_ai_generated=true(릴스·단일 게시물).
"""
import datetime, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

# publish/request.json 의 값을 기본값으로 쓴다 {"kind","media","caption","dry_run","is_ai"}.
# Run workflow 입력칸에 값이 있으면 그쪽이 이긴다 — 빈칸으로 두고 dry_run=false 만 고르면 요청 파일 그대로 게시.
_REQ = os.environ.get("REQUEST", "").strip()
if _REQ and os.path.exists(_REQ):
    for k, v in json.load(open(_REQ, encoding="utf-8")).items():
        env = {"kind": "KIND", "media": "MEDIA", "caption": "CAPTION", "dry_run": "DRY_RUN", "is_ai": "IS_AI"}.get(k)
        if env and not os.environ.get(env, "").strip():
            os.environ[env] = str(v)
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip()
UID = os.environ.get("IG_USER_ID", "").strip()
EXPECT = os.environ.get("EXPECT_USERNAME", "hannun.brief").strip()
ACCOUNTS = {"main": (TOKEN, UID, EXPECT),
            "sports": (os.environ.get("IG_SPORTS_ACCESS_TOKEN", "").strip(), os.environ.get("IG_SPORTS_USER_ID", "").strip(),
                       os.environ.get("EXPECT_SPORTS_USERNAME", "").strip())}
KIND = os.environ.get("KIND", "").strip()
MEDIA = os.environ.get("MEDIA", "").strip().strip("/")
CAPTION_FILE = os.environ.get("CAPTION", "").strip()
DRY = os.environ.get("DRY_RUN", "true").strip().lower() != "false"
IS_AI = os.environ.get("IS_AI", "true").strip().lower() != "false"
PUBLIC = os.environ.get("PUBLIC_BASE", "https://nonojin99.github.io/Daily-Card-News").rstrip("/")
API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")


def call(method, path, **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    req = urllib.request.Request(url + ("?" + data.decode() if method == "GET" else ""),
                                 data=None if method == "GET" else data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.exit(f"::error::{method} {path} → HTTP {e.code}: {body[:600]}")


def wait_ready(cid, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = call("GET", cid, fields="status_code,status")
        code = st.get("status_code")
        print(f"  container {cid}: {code}")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            sys.exit(f"::error::container {code}: {st.get('status')}")
        time.sleep(10)
    sys.exit("::error::container not ready in time")


def head_ok(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def wait_public(url, timeout=2400):
    """브리프와 같은 push 로 요청이 오면 카드 굽기·릴스 만들기·Pages 배포가 끝날 때까지 기다린다(최대 40분)."""
    t0 = time.time()
    while not head_ok(url):
        if time.time() - t0 > timeout:
            return False
        print(f"  waiting for {url}")
        time.sleep(30)
    return True


BLOCK_RECHECK_MIN = int(os.environ.get("BLOCK_RECHECK_MIN", "15"))


def find_published(caption):
    """media_publish 가 막힌 뒤 1분마다 최근 게시물 10개에서 같은 캡션을 찾는다. 조회 자체가 막히면 다음 회차에 다시."""
    for i in range(BLOCK_RECHECK_MIN):
        time.sleep(60)
        try:
            recent = call("GET", f"{UID}/media", fields="caption,permalink,timestamp", limit="10").get("data", [])
        except SystemExit as e:
            print(f"  recheck {i + 1}: media 조회 실패 — {str(e.code)[:200]}")
            continue
        hit = next((r for r in recent if (r.get("caption") or "").strip() == caption), None)
        print(f"  recheck {i + 1}/{BLOCK_RECHECK_MIN}: {'found' if hit else 'not yet'}")
        if hit:
            return hit
    return None


VARIANT = ""   # 릴스 A/B(2026-10-23~): "" = 요청 그대로, "short" = 짧은판(…_short.mp4, 배경음악) 으로 바꿔 올림


def pick_variant(it, media):
    """요청 항목 "ab": "auto" 면 브리프 날짜의 ISO 주 + 코너 순번으로 번갈아 고른다. "short" 는 고정.
    짧은판 MP4 는 make_reel.js --recent 가 낭독판과 함께 만든다(reels/…/<날짜>_<종류>_short.mp4)."""
    ab = str(it.get("ab", "")).strip().lower()
    if KIND != "reel" or ab not in ("auto", "short"):
        return ""
    if ab == "short":
        return "short"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})_([a-z]+)", media)
    if not m:
        return ""
    # 같은 코너는 주마다 번갈아(이번 주 짧은판 ↔ 다음 주 낭독판), 한 주 안에서는 코너끼리 엇갈리게 — 같은 코너끼리 주 단위로 비교
    slot = {"ai": 0, "activity": 1, "science": 2, "sports": 1, "football": 1, "music": 1}.get(m[4], 0)
    week = datetime.date(int(m[1]), int(m[2]), int(m[3])).isocalendar()[1]
    return "short" if (week + slot) % 2 == 0 else ""


def short_caption(caption, media):
    """낭독판 캡션 → 짧은판 캡션: '🎧 …' 줄을 '⚡ 핵심 N장 요약'으로, 낭독 표기 줄을 배경음악 크레디트로."""
    spec = media[:-4] + ".reel.json"
    info = json.load(open(spec, encoding="utf-8")) if os.path.exists(spec) else {}
    n, sec, credit = info.get("cards", 3), round(info.get("seconds", 13)), info.get("credit", "")
    out, has_music = [], False
    for ln in caption.split("\n"):
        if ln.startswith("🎧"):
            ln = f"⚡ 핵심 {n}장, {sec}초 요약"
        elif "🎙" in ln:
            ln = f"🎵 음악: {credit}" + (" · 그림 일부 AI 생성" if "AI 생성" in ln else ""); has_music = True
        out.append(ln)
    if not has_music and credit:
        tags = next((i for i in range(len(out) - 1, -1, -1) if out[i].startswith("#")), len(out))
        out.insert(tags, f"🎵 음악: {credit}")
    return "\n".join(out)


def main():
    global KIND, MEDIA, CAPTION_FILE, DRY, IS_AI, TOKEN, UID, EXPECT, VARIANT
    req = json.load(open(_REQ, encoding="utf-8")) if _REQ and os.path.exists(_REQ) else {}
    items = req.get("requests") if isinstance(req.get("requests"), list) else None
    if not items or MEDIA:   # Run workflow 입력칸(media)을 채웠으면 그 한 건만
        return publish_one()
    failed = []
    for n, it in enumerate(items, 1):
        KIND = str(it.get("kind", "")).strip()
        MEDIA = str(it.get("media", "")).strip().strip("/")
        CAPTION_FILE = str(it.get("caption", "")).strip()
        DRY = str(it.get("dry_run", "true")).strip().lower() != "false"
        IS_AI = str(it.get("is_ai", "true")).strip().lower() != "false"
        acct = str(it.get("account", "main")).strip() or "main"
        if acct not in ACCOUNTS or not all(ACCOUNTS[acct]):
            print(f"::error::request {n}: account '{acct}' 의 토큰·ID·계정 이름이 없음 — 건너뜀")
            failed.append(n)
            continue
        TOKEN, UID, EXPECT = ACCOUNTS[acct]
        VARIANT = pick_variant(it, MEDIA)
        if VARIANT == "short":
            MEDIA = MEDIA[:-4] + "_short.mp4"
        # 검수 관문(2026-10-25~): 항목에 "review" 가 있으면 검수 기록이 있어야 올린다 — 사람·에이전트가 보지 않은 영상이 나가지 않게.
        #   "review":"required" → reels/…/<이름>.review.json(verdict PASS, sha1 = 지금 MP4) / "review":"human" → 그 기록의 by 가 "user"
        #   카드 묶음(캐러셀)은 cards/…/review.json 의 sha1 = cards/…/source.sha1 내용. 없거나 다르면 이번엔 건너뛰고(실패 아님) 다음 실행이 다시 본다.
        need = str(it.get("review", "")).strip().lower()
        if need in ("required", "human") and not DRY:
            ok, why = review_ok(KIND, MEDIA, need)
            if not ok:
                print(f"::warning::request {n} 검수 대기 — {why} (tools/check_reel.py --approve 로 기록 뒤 다시 실행)")
                continue
        print(f"── request {n}/{len(items)}: [{acct}] {KIND} {MEDIA}" + (f" (A/B: {VARIANT or 'narrated'})" if it.get("ab") else "") + (" (dry run)" if DRY else ""))
        try:
            publish_one()
        except SystemExit as e:
            # 같은 날 요청 파일에 이미 올라간 항목이 남아 있으면(예: 아침 캐러셀 + 나중에 덧붙인 축구 캐러셀) 중복 차단은 실패가 아니다 — 2026-10-24 실패 메일 오경보
            if "already published with this caption" in str(e.code):
                print(f"::notice::request {n} skipped — {str(e.code).replace('::error::', '')}")
            elif e.code not in (None, 0):
                print(f"::error::request {n} failed: {e.code}")
                failed.append(n)
    if failed:
        sys.exit(f"::error::failed requests: {failed}")


def review_ok(kind, media, need):
    """검수 기록 확인 — (통과 여부, 이유)."""
    import hashlib
    if kind == "reel":
        rec_p, target = media[:-4] + ".review.json", media
        if not os.path.exists(target):
            return False, f"MP4 없음: {target}"
        h = hashlib.sha1(open(target, "rb").read()).hexdigest()
    else:
        rec_p, src = os.path.join(media, "review.json"), os.path.join(media, "source.sha1")
        if not os.path.exists(src):
            return False, f"카드 지문 없음: {src}"
        h = open(src, encoding="utf-8").read().strip()
    if not os.path.exists(rec_p):
        return False, f"검수 기록 없음: {rec_p}"
    rec = json.load(open(rec_p, encoding="utf-8"))
    if rec.get("verdict") != "PASS":
        return False, f"검수 판정 {rec.get('verdict')}"
    if rec.get("sha1") != h:
        return False, "검수 뒤 파일이 바뀜(다시 구워짐) — 다시 검수 필요"
    if need == "human" and rec.get("by") != "user":
        return False, "수습 기간 항목 — 사용자 승인(by user) 필요"
    return True, ""


def publish_one():
    if KIND in ("", "none"):
        print("request: nothing to publish (kind=none)")
        return
    if not TOKEN or not UID:
        sys.exit("::error::IG_ACCESS_TOKEN / IG_USER_ID secrets are missing")
    me = call("GET", "me", fields="user_id,username")
    print(f"token account: @{me.get('username')} ({me.get('user_id')})")
    if me.get("username") != EXPECT or str(me.get("user_id")) != UID:
        sys.exit(f"::error::token account does not match IG_USER_ID / @{EXPECT} — stop")
    lim = call("GET", f"{UID}/content_publishing_limit", fields="quota_usage,config")
    print("publishing limit:", json.dumps(lim.get("data", lim), ensure_ascii=False))

    caption = open(CAPTION_FILE, encoding="utf-8").read().strip() if CAPTION_FILE else ""
    if VARIANT == "short":
        caption = short_caption(caption, MEDIA)
    print(f"caption: {len(caption)} chars, {caption.count('#')} hashtags")
    if len(caption) > 2200 or caption.count("#") > 5:
        sys.exit("::error::caption too long or more than 5 hashtags")

    if KIND == "reel":
        url = f"{PUBLIC}/{MEDIA}"
        if not wait_public(url):
            sys.exit(f"::error::video not public yet: {url}")
        c = call("POST", f"{UID}/media", media_type="REELS", video_url=url, caption=caption,
                 share_to_feed="true", is_ai_generated="true" if IS_AI else "false")
        cid = c["id"]
    elif KIND == "carousel":
        # 이미지는 배포된 주소에서 01.jpg 부터 차례로 센다(요청 push 시점엔 아직 체크아웃에 없을 수 있다)
        if not wait_public(f"{PUBLIC}/{MEDIA}/01.jpg"):
            sys.exit(f"::error::cards not public yet: {PUBLIC}/{MEDIA}/01.jpg")
        files = []
        while len(files) < 20 and head_ok(f"{PUBLIC}/{MEDIA}/{len(files) + 1:02d}.jpg"):
            files.append(f"{len(files) + 1:02d}.jpg")
        if len(files) < 2:
            sys.exit("::error::carousel needs 2+ JPGs")
        if len(files) > 10:   # API 상한 10장 — 앞 9장 + 마지막 출처 장
            files = files[:9] + files[-1:]
        print("carousel:", ", ".join(files))
        kids = [call("POST", f"{UID}/media", image_url=f"{PUBLIC}/{MEDIA}/{f}", is_carousel_item="true")["id"] for f in files]
        for k in kids:
            wait_ready(k, 180)
        cid = call("POST", f"{UID}/media", media_type="CAROUSEL", children=",".join(kids), caption=caption)["id"]
    else:
        sys.exit("::error::KIND must be reel or carousel")

    wait_ready(cid)
    if caption:   # 같은 요청으로 두 번 누르면 중복 게시 — 최근 게시물에 같은 캡션이 있으면 멈춘다
        recent = call("GET", f"{UID}/media", fields="caption,permalink", limit="10").get("data", [])
        dup = next((r for r in recent if (r.get("caption") or "").strip() == caption), None)
        if dup:
            sys.exit(f"::error::already published with this caption: {dup.get('permalink')}")
    if DRY:
        print(f"DRY RUN — container {cid} is ready; not published (it expires in 24h).")
        return
    try:
        pub = call("POST", f"{UID}/media_publish", creation_id=cid)
    except SystemExit as e:
        # 403 code 4 / subcode 2207051 "action is blocked" 인데 실제로는 몇 분 뒤 게시된 일이 두 번 있었다(2026-10-22 푸드).
        # 최근 게시물에서 같은 캡션을 찾으면 성공으로 치고, 끝내 없으면 '게시 여부 불확실'로 실패한다(README 'API 게시').
        if "2207051" not in str(e.code) or not caption:
            raise
        print(f"::warning::media_publish blocked (2207051) — 실제 게시 여부를 최대 {BLOCK_RECHECK_MIN}분 동안 확인")
        info = find_published(caption)
        if not info:
            sys.exit(f"::error::media_publish 403(2207051) 후 {BLOCK_RECHECK_MIN}분 동안 같은 캡션의 게시물이 안 보임 — "
                     "게시 여부 불확실: 다시 요청하기 전에 계정 그리드를 사람이 확인할 것(중복 게시 위험)")
        print("PUBLISHED (403 뒤 늦게 반영):", json.dumps({k: info.get(k) for k in ("permalink", "timestamp")}, ensure_ascii=False))
        out = os.environ.get("GITHUB_STEP_SUMMARY")
        if out:
            with open(out, "a", encoding="utf-8") as fp:
                fp.write(f"### Published to Instagram (403 2207051 뒤 확인)\n\n{info.get('permalink')}\n")
        return
    info = call("GET", pub["id"], fields="permalink,media_type,media_product_type,timestamp")
    print("PUBLISHED:", json.dumps(info, ensure_ascii=False))
    out = os.environ.get("GITHUB_STEP_SUMMARY")
    if out:
        with open(out, "a", encoding="utf-8") as fp:
            fp.write(f"### Published to Instagram\n\n{info.get('permalink')}\n")


if __name__ == "__main__":
    main()
