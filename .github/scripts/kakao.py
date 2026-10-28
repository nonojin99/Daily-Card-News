"""카카오톡 '나에게 보내기' 공용 모듈(2026-10-29~). kakao_alert.py · publish_ig.py · score_alert.py 가 쓴다.

환경 변수: KAKAO_REST_KEY · KAKAO_CLIENT_SECRET · KAKAO_REFRESH_TOKEN
           KAKAO_SECRETS_PAT(선택 — 있으면 새 refresh token 을 Secret 에 자동 저장) · GITHUB_REPOSITORY
"""
import json, os, subprocess, urllib.error, urllib.parse, urllib.request

APP = "https://nonojin99.github.io/Daily-Card-News/app/"


def _post(url, data, headers=None):
    req = urllib.request.Request(url, urllib.parse.urlencode(data).encode(), headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")


def access_token():
    """(access_token, 경고 문구). 실패하면 RuntimeError."""
    res = _post("https://kauth.kakao.com/oauth/token", {
        "grant_type": "refresh_token",
        "client_id": os.environ["KAKAO_REST_KEY"],
        "client_secret": os.environ.get("KAKAO_CLIENT_SECRET", ""),
        "refresh_token": os.environ["KAKAO_REFRESH_TOKEN"],
    })
    if "access_token" not in res:
        raise RuntimeError(f"카카오 토큰 갱신 실패: {res}")
    warn = ""
    new_rt = res.get("refresh_token")   # 만료 1개월 전부터 새 값이 섞여 온다
    if new_rt:
        pat = os.environ.get("KAKAO_SECRETS_PAT", "")
        ok = bool(pat) and subprocess.run(
            ["gh", "secret", "set", "KAKAO_REFRESH_TOKEN", "--body", new_rt, "--repo", os.environ.get("GITHUB_REPOSITORY", "")],
            env={**os.environ, "GH_TOKEN": pat}, capture_output=True).returncode == 0
        print("새 refresh token " + ("Secret 에 저장함" if ok else "저장 못 함"))
        if not ok:
            warn = "\n⚠ 카카오 토큰 30일 안에 재발급 필요"
    return res["access_token"], warn


def send(at, text, link=APP):
    tpl = {"object_type": "text", "text": text[:200], "link": {"web_url": link, "mobile_web_url": link}}
    res = _post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
                {"template_object": json.dumps(tpl, ensure_ascii=False)},
                {"Authorization": f"Bearer {at}"})
    print("카카오 발송:", res)
    return res.get("result_code") == 0


def notify(text, link=APP):
    """한 건 보내기 — 키가 없거나 실패해도 예외를 내지 않는다(게시 흐름을 막지 않음)."""
    if not os.environ.get("KAKAO_REFRESH_TOKEN"):
        return False
    try:
        at, warn = access_token()
        return send(at, text + warn, link)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::카카오 알림 실패: {e}")
        return False
