#!/usr/bin/env python3
"""인스타 게시물 성과 수집 (Instagram API with Instagram Login, 2026-10-23~).

릴스·캐러셀마다 조회·도달·좋아요·댓글·공유·저장, 릴스는 평균 시청 시간·총 시청 시간까지 가져와
insights/latest.json · insights/history/YYYY-MM-DD.json · insights/summary.md 로 남긴다.
목적: 릴스 개편(첫 장면·배속·자막 등)을 감이 아니라 숫자로 비교하기.

- 본계정(IG_ACCESS_TOKEN·IG_USER_ID)과, 있으면 스포츠 계정(IG_SPORTS_*)을 차례로 본다.
- 권한(instagram_business_manage_insights)이 없거나 지표 이름이 바뀌어도 멈추지 않고 오류를 기록에 남긴다
  — 첫 실행은 '가능한지 확인'이 목적이라 오류 내용이 곧 결과다. 토큰은 출력·기록하지 않는다.
"""
import datetime, json, os, urllib.error, urllib.parse, urllib.request

API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
LIMIT = int(os.environ.get("INSIGHTS_LIMIT", "30"))
COMMON = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions"]
REEL_EXTRA = ["ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]


def call(token, path, **params):
    params["access_token"] = token
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode(errors="replace")).get("error", {})
        except Exception:
            err = {}
        return None, {"http": e.code, "code": err.get("code"), "subcode": err.get("error_subcode"), "message": (err.get("message") or "")[:300]}
    except Exception as e:  # 네트워크 등
        return None, {"message": str(e)[:300]}


def insights(token, mid, metrics):
    """한 번에 묻고, 실패하면 지표를 하나씩 물어 어떤 지표가 안 되는지 남긴다."""
    j, err = call(token, f"{mid}/insights", metric=",".join(metrics))
    if j:
        return {d["name"]: (d.get("values") or [{}])[0].get("value", d.get("total_value", {}).get("value")) for d in j.get("data", [])}, {}
    out, bad = {}, {}
    for m in metrics:
        j, e = call(token, f"{mid}/insights", metric=m)
        if j and j.get("data"):
            d = j["data"][0]
            out[m] = (d.get("values") or [{}])[0].get("value", d.get("total_value", {}).get("value"))
        else:
            bad[m] = e
    if not out:
        bad["_all"] = err
    return out, bad


def account(label, token, uid):
    rec = {"account": label, "checked_at": datetime.datetime.utcnow().isoformat() + "Z", "media": [], "errors": []}
    me, err = call(token, "me", fields="user_id,username,account_type,media_count,followers_count,follows_count")
    if err:
        rec["errors"].append({"step": "me", **err}); return rec
    rec["username"] = me.get("username"); rec["account_type"] = me.get("account_type")
    rec["followers"] = me.get("followers_count"); rec["posts"] = me.get("media_count")
    lst, err = call(token, f"{uid}/media", fields="id,caption,media_type,media_product_type,timestamp,permalink", limit=LIMIT)
    if err:
        rec["errors"].append({"step": "media", **err}); return rec
    for m in lst.get("data", []):
        reel = m.get("media_product_type") == "REELS"
        vals, bad = insights(token, m["id"], COMMON + (REEL_EXTRA if reel else []))
        rec["media"].append({"id": m["id"], "type": m.get("media_product_type") or m.get("media_type"), "timestamp": m.get("timestamp"),
                             "permalink": m.get("permalink"), "first_line": (m.get("caption") or "").split("\n")[0][:80],
                             **({"variant": "short" if "⚡ 핵심" in (m.get("caption") or "") else "narrated"} if reel else {}),
                             "metrics": vals, **({"metric_errors": bad} if bad else {})})
    return rec


def fmt(v, ms=False):
    if v is None: return "–"
    return f"{v / 1000:.1f}초" if ms else f"{v:,}"


def main():
    accs = []
    for label, tk, uid in (("main", "IG_ACCESS_TOKEN", "IG_USER_ID"), ("sports", "IG_SPORTS_ACCESS_TOKEN", "IG_SPORTS_USER_ID")):
        t, u = os.environ.get(tk, "").strip(), os.environ.get(uid, "").strip()
        if t and u:
            accs.append(account(label, t, u))
        else:
            accs.append({"account": label, "errors": [{"step": "secrets", "message": f"{tk}/{uid} 없음"}], "media": []})
    kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    os.makedirs("insights/history", exist_ok=True)
    data = {"collected_kst": kst.strftime("%Y-%m-%d %H:%M"), "api": API, "accounts": accs}
    json.dump(data, open("insights/latest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(data, open(f"insights/history/{kst:%Y-%m-%d}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = [f"# 인스타 성과 — {data['collected_kst']} KST 수집", "", "자동 생성(`.github/scripts/ig_insights.py`). 평균 시청 = 릴스 1회 재생당 평균 시청 시간.", ""]
    for a in accs:
        L.append(f"## {a['account']} @{a.get('username', '?')} — 팔로워 {fmt(a.get('followers'))} · 게시물 {fmt(a.get('posts'))}")
        for e in a["errors"]:
            L.append(f"- ⚠ {e.get('step')}: {e.get('code', '')} {e.get('message', '')}")
        reels = [m for m in a["media"] if m["type"] == "REELS"]
        if reels:
            L += ["", "| 게시(UTC) | 형식 | 릴스 첫 줄 | 조회 | 도달 | 평균 시청 | 총 시청 | 공유 | 저장 |", "|---|---|---|---|---|---|---|---|---|"]
            for m in reels:
                x = m["metrics"]
                L.append(f"| {m['timestamp'][:16]} | {'⚡짧은판' if m.get('variant') == 'short' else '🎧낭독'} | {m['first_line'].replace('|', '/')} | {fmt(x.get('views'))} | {fmt(x.get('reach'))} | "
                         f"{fmt(x.get('ig_reels_avg_watch_time'), True)} | {fmt(x.get('ig_reels_video_view_total_time'), True)} | {fmt(x.get('shares'))} | {fmt(x.get('saved'))} |")
        feed = [m for m in a["media"] if m["type"] != "REELS"]
        if feed:
            L += ["", "| 게시(UTC) | 게시물 첫 줄 | 조회 | 도달 | 좋아요 | 공유 | 저장 |", "|---|---|---|---|---|---|---|"]
            for m in feed:
                x = m["metrics"]
                L.append(f"| {m['timestamp'][:16]} | {m['first_line'].replace('|', '/')} | {fmt(x.get('views'))} | {fmt(x.get('reach'))} | "
                         f"{fmt(x.get('likes'))} | {fmt(x.get('shares'))} | {fmt(x.get('saved'))} |")
        errs = {k for m in a["media"] for k in m.get("metric_errors", {})}
        if errs:
            L.append(f"\n- ⚠ 받지 못한 지표: {', '.join(sorted(errs))} (자세한 오류는 latest.json)")
        L.append("")
    open("insights/summary.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
