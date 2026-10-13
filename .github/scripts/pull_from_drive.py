#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Drive '발행함' 폴더에 올라온 브리프를 레포로 가져온다.

왜 필요한가 (2026-10-13)
  카드뉴스를 쓰는 클라우드 세션은 이 레포에 push 할 수 없다(git proxy 403).
  대신 그 세션은 Google Drive 에 파일을 올릴 수 있으므로, Drive 를 '발행함'으로 두고
  이 스크립트가 정해진 시간마다 새 파일을 레포에 커밋한다.

  대상  폴더(DRIVE_INBOX_ID) 안, 최근 LOOKBACK_DAYS 일 안에 수정된 파일 중
        이름이 YYYY-MM-DD_<type>-brief.html 또는 README.md 인 것
  규칙  같은 이름이 여러 개면 가장 최근 것 하나만 쓴다(수정본은 같은 이름으로 다시 올리면 됨)
  검사  2MB 이하 · UTF-8 · 브리프는 <html 과 </html> 포함 · 레포 내용과 다를 때만 씀
  인증  폴더를 '링크가 있는 모든 사용자 — 뷰어'로 공유하고 API 키(GOOGLE_DRIVE_API_KEY)로 읽는다

실패해도 빌드를 깨지 않는다(exit 0). 바뀐 경로는 PULL_OUT 파일에 적는다.
"""
import datetime, json, os, re, sys, urllib.parse, urllib.request

KEY = os.environ.get("GOOGLE_DRIVE_API_KEY", "").strip()
FOLDER = os.environ.get("DRIVE_INBOX_ID", "").strip()
OUT = os.environ.get("PULL_OUT")
LOOKBACK_DAYS = 3
MAX_BYTES = 2 * 1024 * 1024
API = "https://www.googleapis.com/drive/v3/files"
BRIEF = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z]+-brief\.html$")
ALLOWED_OTHER = {"README.md"}


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def list_files():
    since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%S")
    q = "'%s' in parents and trashed = false and modifiedTime > '%s'" % (FOLDER, since)
    files, token = [], None
    while True:
        params = {"q": q, "key": KEY, "pageSize": "200", "orderBy": "modifiedTime",
                  "fields": "nextPageToken,files(id,name,modifiedTime,size)"}
        if token:
            params["pageToken"] = token
        data = json.loads(get(API + "?" + urllib.parse.urlencode(params)))
        files += data.get("files", [])
        token = data.get("nextPageToken")
        if not token:
            return files


def main():
    if not KEY or not FOLDER:
        print("GOOGLE_DRIVE_API_KEY 또는 DRIVE_INBOX_ID 가 없어 건너뜁니다.")
        return
    latest = {}
    for f in list_files():                      # modifiedTime 오름차순 → 뒤에 온 것이 최신
        name = f.get("name", "")
        if BRIEF.match(name) or name in ALLOWED_OTHER:
            latest[name] = f
    changed = []
    for name, f in sorted(latest.items()):
        try:
            if int(f.get("size") or 0) > MAX_BYTES:
                raise ValueError("too large")
            body = get("%s/%s?alt=media&key=%s" % (API, f["id"], urllib.parse.quote(KEY)))
            text = body.decode("utf-8")
            if BRIEF.match(name) and ("<html" not in text or "</html>" not in text):
                raise ValueError("not a complete html file")
            old = open(name, encoding="utf-8").read() if os.path.exists(name) else None
            if old == text:
                continue
            with open(name, "w", encoding="utf-8") as fp:
                fp.write(text)
            changed.append(name)
            print("pulled:", name, "(Drive %s)" % f.get("modifiedTime"))
        except Exception as e:
            print("::warning::skip %s: %s" % (name, e))
    if OUT and changed:
        with open(OUT, "w", encoding="utf-8") as fp:
            fp.write("\n".join(changed) + "\n")
    if not changed:
        print("새 파일 없음")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("::warning::pull_from_drive failed: %s" % e)
    sys.exit(0)
