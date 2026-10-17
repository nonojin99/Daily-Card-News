#!/usr/bin/env python3
"""인스타그램 게시 (Instagram API with Instagram Login).

워크플로 'Publish to Instagram' 에서 수동 실행한다(사람이 보고 누르는 1탭 승인).
  KIND=reel     MEDIA=reels/2026-10/2026-10-17_weekend.mp4
  KIND=carousel MEDIA=cards/2026-10/2026-10-17_weekend        (폴더 안 01.jpg … 최대 10장)
  CAPTION=<캡션 파일 경로>   DRY_RUN=true 면 컨테이너만 만들고 게시하지 않는다.

안전장치: 토큰의 계정이 IG_USER_ID·EXPECT_USERNAME 과 다르면 중단. 게시 한도를 먼저 확인.
컨테이너는 24시간 뒤 만료되므로 실행할 때 만든다. AI 음성·그림이 있으면 is_ai_generated=true(릴스·단일 게시물).
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request

TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip()
UID = os.environ.get("IG_USER_ID", "").strip()
EXPECT = os.environ.get("EXPECT_USERNAME", "hannun.brief").strip()
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


def main():
    if not TOKEN or not UID:
        sys.exit("::error::IG_ACCESS_TOKEN / IG_USER_ID secrets are missing")
    me = call("GET", "me", fields="user_id,username")
    print(f"token account: @{me.get('username')} ({me.get('user_id')})")
    if me.get("username") != EXPECT or str(me.get("user_id")) != UID:
        sys.exit(f"::error::token account does not match IG_USER_ID / @{EXPECT} — stop")
    lim = call("GET", f"{UID}/content_publishing_limit", fields="quota_usage,config")
    print("publishing limit:", json.dumps(lim.get("data", lim), ensure_ascii=False))

    caption = open(CAPTION_FILE, encoding="utf-8").read().strip() if CAPTION_FILE else ""
    print(f"caption: {len(caption)} chars, {caption.count('#')} hashtags")
    if len(caption) > 2200 or caption.count("#") > 5:
        sys.exit("::error::caption too long or more than 5 hashtags")

    if KIND == "reel":
        url = f"{PUBLIC}/{MEDIA}"
        if not head_ok(url):
            sys.exit(f"::error::video not public yet: {url}")
        c = call("POST", f"{UID}/media", media_type="REELS", video_url=url, caption=caption,
                 share_to_feed="true", is_ai_generated="true" if IS_AI else "false")
        cid = c["id"]
    elif KIND == "carousel":
        files = sorted(f for f in os.listdir(MEDIA) if f.lower().endswith(".jpg"))[:10]
        if len(files) < 2:
            sys.exit("::error::carousel needs 2+ JPGs")
        kids = []
        for f in files:
            url = f"{PUBLIC}/{MEDIA}/{f}"
            if not head_ok(url):
                sys.exit(f"::error::image not public yet: {url}")
            kids.append(call("POST", f"{UID}/media", image_url=url, is_carousel_item="true")["id"])
        for k in kids:
            wait_ready(k, 180)
        cid = call("POST", f"{UID}/media", media_type="CAROUSEL", children=",".join(kids), caption=caption)["id"]
    else:
        sys.exit("::error::KIND must be reel or carousel")

    wait_ready(cid)
    if DRY:
        print(f"DRY RUN — container {cid} is ready; not published (it expires in 24h).")
        return
    pub = call("POST", f"{UID}/media_publish", creation_id=cid)
    info = call("GET", pub["id"], fields="permalink,media_type,media_product_type,timestamp")
    print("PUBLISHED:", json.dumps(info, ensure_ascii=False))
    out = os.environ.get("GITHUB_STEP_SUMMARY")
    if out:
        with open(out, "a", encoding="utf-8") as fp:
            fp.write(f"### Published to Instagram\n\n{info.get('permalink')}\n")


if __name__ == "__main__":
    main()
