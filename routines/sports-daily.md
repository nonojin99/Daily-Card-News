# 매일 스포츠 브리프 — 예약 루틴 프롬프트 (초안, 2026-10-21)

> claude.ai 예약 루틴에 **매일 08:30 KST** 로 등록할 프롬프트다. 스포츠 인스타 계정이 열리고 시크릿이 등록된 뒤에 켠다(README '스포츠 계정').
> 아래 `---` 사이를 그대로 붙여 넣는다.

---
GitHub 레포 nonojin99/Daily-Card-News 의 오늘자 **스포츠 브리프**를 만들어 발행하세요. 이 세션은 매일 한국시간 오전 8시 30분에 새로 시작되며 이전 대화 기억이 없습니다. 브리프와 보고는 한국어로 씁니다.

## 0. 준비
1. `TZ=Asia/Seoul date '+%Y-%m-%d %A'` 로 오늘 날짜·요일을 확인하세요(이하 KST).
2. 저장소의 `CLAUDE.md` 와 `README.md` 를 읽으세요. 특히 README '스포츠 계정'(종목 편성표·월요일 주말 결산·카드 그림 규칙), '카드 넘겨보기', '카드 검토 하네스', '오디오', '인스타그램 운영 → API 게시'. README 가 최종 기준입니다.
3. 최근 3일 `*_sports-brief.html` 을 읽고 맨 아래 tracker 주석(추적 중인 시리즈·순위 경쟁, 다룬 경기)을 확인하세요. 같은 경기 결과를 다시 쓰지 마세요(새 전개만).
4. 어제 스포츠 브리프의 `<style>` 을 그대로 복사해 쓰세요(액센트 `#1f5f8b`/`#e8f0f5`). 어제 파일의 `audio-player` div 는 복사하지 않습니다.

## 1. 오늘 만들 파일 (1개)
- `YYYY-MM-DD_sports-brief.html` — 카드 4~6장(월요일 주말 결산은 6~8장). 그날 가장 큰 경기부터. 첫 카드가 그날 가장 센 소식.
- 종목은 README 편성표의 시즌·기준을 따릅니다. 시즌 중인 종목이 한 주에 한 번은 나오게, 최근 3일 tracker 를 보고 빠진 종목을 챙기세요.
- 카드마다 `.cn` 블록(`cn-t`·`cn-s`·그림 재료). 그림은 스코어보드 `cn-score`·순위/승점 막대 `cn-bars`·기록 큰 숫자 `cn-num`·대진/단계 `cn-steps`. **사진·AI 그림 금지.**
- 낭독 원고 `<details class="audio-script">` 700~1,300자(월요일은 1,000~1,600자): 훅 한 문장(첫 카드 핵심 + 숫자) → "M월 D일 X요일, 스포츠 브리프입니다." → 카드 순서대로 → 클로징.
- 인사이트 박스 태그는 `⚾/⚽/🎾/⛳/🥊/🏈/🎮 알고 보면 달라지는 것`. 부상·사고·폭력 사건은 `Context · 맥락 읽기`.
- 파일 맨 아래 `<!-- tracker: YYYY-MM-DD ... -->`: ①시리즈·순위 경쟁 현재 상태 ②오늘 다룬 경기 ③제외한 항목과 이유.

## 2. 리서치 — WebSearch 로 발견 → WebFetch 로 본문 검증 (Firecrawl 호출 금지)
- 서브에이전트 2개를 동시에: A = 국내(KBO·K리그·국내 골프·LCK), B = 해외(MLB·유럽 축구·UCL·테니스·해외 골프·UFC·NFL·롤 국제대회).
- 잘 되는 도메인: sports.khan.co.kr · spotvnews.co.kr · news1.kr · newsis.com · ytn.co.kr · sedaily.com(en.sedaily.com) · hankooki.com · apnews.com · cbsnews.com · aljazeera.com
- WebFetch 403(시도 금지): yna.co.kr · mk.co.kr · donga.com · chosun.com · hani.co.kr · news.kbs.co.kr · imnews.imbc.com · naver.com · olympics.com
- 스코어·순위·기록은 기사 본문에서 확인하고, 두 매체가 어긋나면 그 수치는 빼거나 "매체별 표기 불일치". 경기 시각은 한국시간으로 적고 원문이 현지시간이면 변환 근거를 적으세요.
- 각 사실이 어느 URL 본문에 있는지 URL 단위로 기록, 같은 URL 3개 이상 카드 재사용 금지, 위키·블로그·언론사 홈 링크 금지.

## 3. 검토
1. 브리프 검토 하네스: 검증 전용 서브에이전트가 README 체크리스트 전 항목을 PASS/FAIL(특히 1 숫자 정합성·2 라운드 표기·3 날짜 최신성·7 추측 금지). FAIL 은 고치고, 애매하면 항목을 뺍니다.
2. 카드 검토 하네스 2단계(CLAUDE.md): `python3 tools/check_cards.py` + `node tools/render_cards.js` → 독립 시각 검토 → 통과하면 `/tmp/card-review/<브리프 이름>.stage2.md` 기록.

## 4. 발행
1. 브리프 HTML 과, 인스타 게시용 캡션 `captions/YYYY-MM-DD_sports.txt`(월요일은 `captions/YYYY-MM-DD_sports_reel.txt` 도), `publish/request.json` 만 add 합니다.
   요청 파일: `{"requests":[{"kind":"carousel","media":"cards/YYYY-MM/YYYY-MM-DD_sports-brief","caption":"captions/YYYY-MM-DD_sports.txt","dry_run":"false","is_ai":"false","account":"sports"}], "note":"…"}`
   월요일엔 릴스 항목도(`"kind":"reel","media":"reels/YYYY-MM/YYYY-MM-DD_sports.mp4"`, `"is_ai":"true"`, `"account":"sports"`). 맥락 읽기 카드가 섞이면 게시 요청에서 뺍니다.
2. `git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "YYYY-MM-DD sports brief"` → `git pull --rebase origin main` → `git push origin HEAD:main`(실패하면 rebase 후 한 번만 재시도). push 관문 훅이 막으면 메시지대로 고칩니다.
3. 막히면 PushNotification 으로 알리고 HTML 을 SendUserFile 로 전달합니다.

## 5. 보고
다룬 경기·제외 이유·검토 FAIL 수정 내역·카드 검토 1단계 FAIL/WARN 수와 2단계 반복 횟수·원고 분량·발행 결과(push 시각, 게시 요청 항목). 실패가 있을 때만 알림을 보냅니다.
---
