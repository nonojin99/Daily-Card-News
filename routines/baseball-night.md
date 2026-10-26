# ⚾ 야구 나이트 — 예약 루틴 프롬프트 (초안, 2026-10-21)

> claude.ai 예약 루틴에 **매일 23:30 KST** 로 등록한다. 스포츠 인스타 계정과 시크릿이 준비된 뒤 켠다(README '스포츠 계정').
> 아래 `---` 사이를 그대로 붙여 넣는다.

---
GitHub 레포 nonojin99/Daily-Card-News 의 오늘자 **야구 나이트** 브리프를 만들어 발행하세요. 이 세션은 매일 한국시간 밤 11시 30분에 새로 시작되며 이전 대화 기억이 없습니다. 브리프와 보고는 한국어로 씁니다.

## 준비
1. `TZ=Asia/Seoul date '+%Y-%m-%d %A'` — 오늘(KST) 날짜. 이 브리프는 **오늘 끝난 경기**를 다룬다(KBO 오늘 밤, MLB 오늘 한국 낮).
2. `CLAUDE.md`·`README.md` 를 읽는다. 특히 README '스포츠 계정'(시리즈·시즌·비시즌 규칙), '카드 넘겨보기'(여러 경기 스코어 `cn-scores`), '카드 검토 하네스', '오디오'.
3. 최근 3일 `*_baseball-brief.html` 의 tracker(순위 경쟁·시리즈 상황·다룬 경기)를 읽는다. 어제 브리프의 `<style>` 을 그대로 복사(액센트 `#1f5f8b`/`#e8f0f5`, `audio-player` div 는 복사 금지). 첫 회면 최근 `*_sports-brief.html` 의 `<style>`.
4. **오늘 KBO·MLB 경기가 모두 없으면** 먼저 시즌 중(3월~포스트시즌 종료)인지 본다.
   - **시즌 중 경기 없는 날**(시리즈 사이 휴식일, 월요일 등) = **프리뷰**(2026-10-22 사용자 결정): 확정된 다음 시리즈·대진(포스트시즌 대진, 선발 예고, 감독 발언, 상대 전적), 직전 시리즈 결산·MVP, 순위·일정, MLB 포스트시즌 대진으로 4~6장. KBO 결과 카드(`cn-scores`)는 직전 시리즈 스코어로 대신한다.
     어제 브리프와 같은 내용이면 새 변화(선발 발표·엔트리·부상 등)가 있을 때만 다시 다룬다. 다룰 새 소식이 정말 없을 때만 "오늘 발행 없음".
   - **비시즌**이면 README 비시즌 규칙 — 스토브리그 발행일(화·금)이 아니면 아무것도 만들지 않고 "오늘 발행 없음"으로 끝낸다.

## 오늘 만들 파일 — `YYYY-MM-DD_baseball-brief.html`
- 카드 4~6장. 첫 카드 = 그날 가장 큰 야구 소식.
  - **KBO 결과 카드 1장**: 오늘 전 경기 스코어를 `<p class="cn-scores">팀|점수|점수|팀 / …</p>`(최대 6경기)로, 본문에 경기별 결승타·승리투수 한 줄씩.
  - 순위·매직넘버·시리즈 상황 카드(`cn-bars`·`cn-num`), 그날 가장 큰 경기 1~2장(`cn-score`).
  - **MLB**: 한국 선수 출전 경기·포스트시즌·큰 기록만 1~2장. 15경기 전부 쓰지 않는다.
- 사진·AI 그림 금지. 인사이트 태그 `⚾ 알고 보면 달라지는 것`.
- 낭독 원고 700~1,300자. **카드 하나 = 문단 하나**: 첫 문단은 "M월 D일 X요일, 야구 나이트입니다." 한 줄만, 둘째 문단(카드 1)의 첫 문장이 훅(그날 가장 센 사실을 숫자·질문으로, 날짜·인사·"소개합니다"로 시작 금지) → 카드 순서대로 한 문단씩 → 클로징. (2026-10-23~ 릴스 개편 — 릴스는 첫 문단·끝인사를 빼고 카드 1번부터 1.2배속으로 시작한다. README '오디오'·'릴스')
- **⚾ 결과 알림(2026-10-23~)**: 경기가 끝나면 Actions(`Score alert`)가 AI 없이 KBO 공식 기록으로 점수 카드 1장을 먼저 올린다(`sports/alerts/`). 이 루틴은 해설·결승타·순위·다음 일정 등 **알림에 없는 이야기**를 맡는다 — 점수만 되풀이하는 카드는 만들지 않는다. 캡션 첫 줄은 '오늘 KBO 결과'처럼 검색어와 숫자부터.
- 파일 끝 `<!-- tracker: … -->`: 순위·시리즈 현재 상태 / 오늘 다룬 경기 / 제외 이유.
- **📈 데이터 릴스 점수(2026-10-26~)**: Actions 가 끝난 경기마다 규칙 점수를 매겨 `sports/reels/queue.json` 의 `scored` 에 남긴다(기준 50 이상은 한 경기 데이터 릴스가 자동으로 나간다 — 해설 없음).
  준비 단계에서 이 파일을 읽고 **점수 높은 경기를 해설 우선순위로** 쓴다(카드 1번 후보). 데이터 릴스가 이미 나간 경기는 해설 카드에서 '왜 중요한가'를 더 깊게.
  한국 선수 소속 팀이 기사로 확인되면 `sports/reels/rules.json` 의 `korean_teams`(names_ko.json 의 한국어 이름)를 고쳐 같은 커밋에 넣는다 — 확인 안 된 팀은 넣지 않는다.

## 리서치
- 서브에이전트 2개를 동시에 띄워 WebSearch 로 발견 → WebFetch 로 기사 본문 검증(**Firecrawl 호출 금지**).
- 잘 되는 도메인: sports.khan.co.kr · spotvnews.co.kr · news1.kr · newsis.com · ytn.co.kr · en.sedaily.com · hankooki.com · apnews.com · cbsnews.com · aljazeera.com
- WebFetch 403(시도 금지): yna.co.kr · mk.co.kr · donga.com · chosun.com · hani.co.kr · news.kbs.co.kr · imnews.imbc.com · naver.com · olympics.com
- 스코어·순위·기록은 기사 본문에서 확인, 두 매체가 어긋나면 빼거나 "매체별 표기 불일치". 시각은 한국시간(원문이 현지시간이면 변환 근거).
- 각 사실이 어느 URL 본문에 있는지 URL 단위로 기록, 같은 URL 3개 이상 카드 재사용 금지, 위키·블로그·언론사 홈 링크 금지.
- 서브에이전트 A = KBO(경기 결과·순위·기록), B = MLB(한국 선수·포스트시즌) + **오늘 저녁 끝난 롤 e스포츠 큰 경기**(아래 별도 브리프용). KBO 결과는 경기 종료 직후 기사(스포츠경향·스포티비뉴스·뉴스1·뉴시스)를 쓴다.

## 🎮 e스포츠는 따로 (야구 브리프에 섞지 않는다)
- 오늘 저녁 롤 **큰 경기**(LCK 플레이오프·결승, MSI, 월즈, 한국 팀 국제전)가 끝났으면 **별도 파일 `YYYY-MM-DD_esports-brief.html`**(카드 2~4장, 액센트 `#4a4fa0`/`#ecedf6`, 인사이트 태그 `🎮 알고 보면 달라지는 것`)을 만든다. 일반 정규 시즌 경기는 다루지 않는다.
- **큰 대회 기간인데 오늘 경기가 없으면 프리뷰**(2026-10-22 사용자 결정): 대진·조 추첨이 새로 확정됐거나 다음 경기가 3일 안이면 대진·관전 포인트·일정으로 2~3장. 어제 e스포츠 브리프와 같은 내용이면 만들지 않는다. **조사는 경기가 없어도 매일 한다**(서브에이전트 B).
- 낭독 원고 400~800자("M월 D일 X요일, e스포츠 브리프입니다."), tracker 주석, 카드 검토 하네스·push 관문은 야구 브리프와 똑같이 따로 거친다.
- 인스타는 별도 캐러셀: 캡션 `captions/YYYY-MM-DD_esports.txt`(첫 줄 `[🎮 e스포츠] …`), 요청 항목 `"media":"cards/YYYY-MM/YYYY-MM-DD_esports-brief"`, `"account":"sports"`.

## 인스타
- 캡션 `captions/YYYY-MM-DD_baseball.txt`(첫 줄 `[⚾ 야구 나이트] …`), 요청 `{"kind":"carousel","media":"cards/YYYY-MM/YYYY-MM-DD_baseball-brief","caption":"captions/YYYY-MM-DD_baseball.txt","dry_run":"false","is_ai":"false","account":"sports"}`.
- **⚡ 캐러셀판 릴스(2026-10-26~, 사용자 결정 — "야구도 캐러셀 내용을 쇼츠로, 페이지당 1.8초, TTS 없이 배경음")**: **발행하는 날마다** 릴스 1편 — 본문 카드 전부(최대 6장)를 1.8초씩 넘김(첫 장 살짝 확대), 표지·출처 장 없음, 낭독 없음·배경음악, 4장이면 약 6.5초(`tools/make_reel.js` `NIGHT`, push 뒤 Actions 가 `reels/YYYY-MM/YYYY-MM-DD_baseball_short.mp4` 를 만든다). 예전 10초판(`FAST`, 2장)은 축구 모닝(월요일 제외)만.
  그래서 **카드 1 = 그날 가장 센 결과**(`cn-score` 큰 스코어 — 첫 프레임에 결론), 카드 2 = 둘째로 센 것.
  요청은 **다음 날 아침 출근길** `publish/slots/<다음 날>_0730_baseball.json`(결과 알림 이어 달리기가 07:30에 올린다): `{"requests":[{"kind":"reel","media":"reels/YYYY-MM/YYYY-MM-DD_baseball.mp4","caption":"captions/YYYY-MM-DD_baseball_reel.txt","dry_run":"false","is_ai":"false","account":"sports","ab":"short","review":"required"}]}` — `_short.mp4` 로 바뀌어 올라간다.
  검수 관문(CLAUDE.md): 브리프 push → Actions 가 MP4 를 만들면 `python3 tools/check_reel.py reels/…_baseball_short.mp4 --caption captions/…_baseball_reel.txt` + `reel-reviewer` → 통과하면 `--approve --by agent` 기록 + 캡션 + 요청 파일을 한 커밋으로.
  릴스 캡션 첫 줄은 스코어·숫자부터, '🎧'·'AI 음성' 줄 없이 `🎵 음악: Upbeat Forever — Kevin MacLeod (incompetech.com) · CC BY 3.0`. 맥락 읽기(부상·사고·폭력) 카드가 섞이면 릴스도 만들지 않는다.
- **캡션 해시태그는 최대 5개**(넘으면 게시 스크립트가 거부 — 10/21 첫 회가 9개·8개로 실패). e스포츠 캡션도 같다.

## 검토 (건너뛰지 말 것)
1. 브리프 검토 하네스: 검증 전용 서브에이전트가 README 체크리스트 전 항목 PASS/FAIL(특히 숫자 정합성·라운드 표기·날짜 최신성·추측 금지). FAIL 은 고치고 애매하면 뺀다.
2. 카드 검토 하네스 2단계(CLAUDE.md): `python3 tools/check_cards.py` + `node tools/render_cards.js` → 독립 시각 검토 → 통과하면 `/tmp/card-review/<브리프 이름>.stage2.md`.

## 발행
1. 브리프 HTML, 캡션, `publish/request.json` 만 add. 요청 항목마다 `"account":"sports"` (없으면 @hannun.brief 로 올라가니 반드시 넣는다). 맥락 읽기(부상·사고·폭력) 카드가 섞이면 게시 요청에서 뺀다.
2. `git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit` → `git pull --rebase origin main` → `git push origin HEAD:main`(실패하면 rebase 후 한 번만 재시도). push 관문 훅이 막으면 메시지대로 고친다.
3. **끝날 때마다 PushNotification 한 번**(2026-10-24~, 사용자 요청 — Slack 으로 매일 요약): 정상 발행·발행 없음·실패 모두. 형식은 CLAUDE.md '매일 Slack 요약'. 실패면 첫 줄에 ⚠ 와 실패 이유.

## 보고
다룬 경기·제외 이유·검토 FAIL 수정 내역·카드 검토 1단계 FAIL/WARN 수와 2단계 반복 횟수·원고 분량·발행 결과(push 시각, 게시 요청 항목).
---
