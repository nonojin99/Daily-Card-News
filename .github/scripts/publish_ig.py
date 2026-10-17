#!/usr/bin/env python3
"""인스타그램 게시 (Instagram API with Instagram Login).

워크플로 'Publish to Instagram' 에서 수동 실행한다(사람이 보고 누르는 1탭 승인).
  KIND=reel     MEDIA=reels/2026-10/2026-10-17_weekend.mp4
  KIND=carousel MEDIA=cards/2026-10/2026-10-17_weekend        (폴더 안 01.jpg … 최대 10장)
  CAPTION=<캡션 파일 경로>   DRY_RUN=true 면 컨테이너만 만들고 게시하지 않는다.
  KIND=none(또는 빈칸) 이면 아무것도 하지 않는다 — 게시가 끝난 요청 파일은 none 으로 돌려 둔다.

안전장치: 토큰의 계정이 IG_USER_ID·EXPECT_USERNAME 과 다르면 중단. 게시 한도를 먼저 확인.
컨테이너는 24시간 뒤 만료되므로 실행할 때 만든다. AI 음성·그림이 있으면 is_ai_generated=true(릴스·단일 게시물).
"""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request

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


def wait_public(url, timeout=1500):
    """브리프와 같은 push 로 요청이 오면 카드 굽기·Pages 배포가 끝날 때까지 기다린다(최대 25분)."""
    t0 = time.time()
    while not head_ok(url):
        if time.time() - t0 > timeout:
            return False
        print(f"  waiting for {url}")
        time.sleep(30)
    return True


def main():
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
    pub = call("POST", f"{UID}/media_publish", creation_id=cid)
    info = call("GET", pub["id"], fields="permalink,media_type,media_product_type,timestamp")
    print("PUBLISHED:", json.dumps(info, ensure_ascii=False))
    out = os.environ.get("GITHUB_STEP_SUMMARY")
    if out:
        with open(out, "a", encoding="utf-8") as fp:
            fp.write(f"### Published to Instagram\n\n{info.get('permalink')}\n")


if __name__ == "__main__":
    main()
