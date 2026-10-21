# ⚽ 축구 모닝 — 예약 루틴 프롬프트 (초안, 2026-10-21)

> claude.ai 예약 루틴에 **매일 08:30 KST** 로 등록한다(경기가 없는 날은 발행 없이 끝난다). 스포츠 인스타 계정과 시크릿이 준비된 뒤 켠다.
> 아래 `---` 사이를 그대로 붙여 넣는다.

---
GitHub 레포 nonojin99/Daily-Card-News 의 오늘자 **축구 모닝** 브리프를 만들어 발행하세요. 이 세션은 매일 한국시간 오전 8시 30분에 새로 시작되며 이전 대화 기억이 없습니다. 브리프와 보고는 한국어로 씁니다.

## 준비
1. `TZ=Asia/Seoul date '+%Y-%m-%d %A'` — 오늘(KST). 이 브리프는 **어젯밤~오늘 새벽 끝난 경기**를 다룬다.
2. `CLAUDE.md`·`README.md` 를 읽는다(README '스포츠 계정' 시리즈 규칙, '카드 넘겨보기', '카드 검토 하네스', '오디오').
3. 최근 3일 `*_football-brief.html` tracker(순위 경쟁·한국 선수·다룬 경기)를 읽고, 어제 축구 브리프 `<style>` 을 복사(액센트 `#2f6b45`/`#e9f1ec`, `audio-player` div 복사 금지). 첫 회면 `*_sports-brief.html` 의 `<style>` 에서 액센트만 바꾼다.
4. 축구가 없는 날에도 아래 '🏆 이벤트 픽' 대상이 있으면 그것만 만든다.
5. **축구 발행 여부 판단**: 어젯밤~오늘 새벽에 유럽 5대 리그·UCL·유로파 경기나 어제 K리그 경기가 없으면(또는 한국 선수·순위에 의미 있는 결과가 없으면) 아무것도 만들지 않고 "오늘 발행 없음"으로 끝낸다. 대개 토·일·월·수·목 아침에 발행한다.

## 오늘 만들 파일 — `YYYY-MM-DD_football-brief.html`
- 카드 4~6장, **월요일은 '주말 결산' 6~8장**(유럽 리그 주말 경기 + K리그). 골프·UFC·NFL·테니스는 이 브리프에 섞지 않는다(아래 별도 브리프).
  - 리그별 결과 묶음은 `cn-scores`(최대 6경기), 큰 경기는 `cn-score`, 순위·승점은 `cn-bars`, 한국 선수 기록은 `cn-num`.
  - 한국 선수(손흥민·이강인·김민재·황희찬 등 그 시즌 소속 확인) 경기를 우선.
- 사진·AI 그림 금지. 인사이트 태그 `⚽ 알고 보면 달라지는 것`.
- 낭독 원고 700~1,300자(월요일 1,000~1,600자): 훅 한 문장 → "M월 D일 X요일, 축구 모닝입니다." → 카드 순서대로 → 클로징.
- 파일 끝 `<!-- tracker: … -->`.

## 리서치
- 서브에이전트 2개를 동시에 띄워 WebSearch 로 발견 → WebFetch 로 기사 본문 검증(**Firecrawl 호출 금지**).
- 잘 되는 도메인: sports.khan.co.kr · spotvnews.co.kr · news1.kr · newsis.com · ytn.co.kr · en.sedaily.com · hankooki.com · apnews.com · cbsnews.com · aljazeera.com
- WebFetch 403(시도 금지): yna.co.kr · mk.co.kr · donga.com · chosun.com · hani.co.kr · news.kbs.co.kr · imnews.imbc.com · naver.com · olympics.com
- 스코어·순위·기록은 기사 본문에서 확인, 두 매체가 어긋나면 빼거나 "매체별 표기 불일치". 시각은 한국시간(원문이 현지시간이면 변환 근거).
- 각 사실이 어느 URL 본문에 있는지 URL 단위로 기록, 같은 URL 3개 이상 카드 재사용 금지, 위키·블로그·언론사 홈 링크 금지.
- 서브에이전트 A = 유럽 리그·UCL·한국 선수, B = K리그 + **어젯밤~새벽 끝난 큰 대회**(골프·UFC·NFL·테니스, 아래 별도 브리프용).

## 🏆 이벤트 픽은 따로 (축구 브리프에 섞지 않는다)
- 어젯밤~오늘 새벽 **큰 대회**가 끝났으면 **별도 파일 `YYYY-MM-DD_event-brief.html`**(카드 2~5장, 액센트 `#9a5b14`/`#f6efe6`)을 만든다.
  대상: 테니스 그랜드슬램(8강 이상·한국 선수), 골프 메이저·한국 선수 우승권 최종 라운드(LPGA·PGA·KLPGA), UFC 넘버 대회·한국 선수 출전, NFL 플레이오프·슈퍼볼(정규 시즌은 큰 이슈만).
  카드마다 종목 태그(`.topic` 예: `골프 · LPGA`), 인사이트 태그는 종목 이모지(`⛳/🎾/🥊/🏈 알고 보면 달라지는 것`).
- 낭독 원고 400~900자("M월 D일 X요일, 스포츠 이벤트 픽입니다."), tracker, 카드 검토 하네스·push 관문은 따로 거친다.
- 인스타는 별도 캐러셀: 캡션 `captions/YYYY-MM-DD_event.txt`(첫 줄 `[🏆 이벤트 픽] …`), 요청 항목 `"media":"cards/YYYY-MM/YYYY-MM-DD_event-brief"`, `"account":"sports"`.

## 인스타
- 캡션 `captions/YYYY-MM-DD_football.txt`(첫 줄 `[⚽ 축구 모닝] …`). 요청에 캐러셀 `{"kind":"carousel","media":"cards/YYYY-MM/YYYY-MM-DD_football-brief","caption":"captions/YYYY-MM-DD_football.txt","dry_run":"false","is_ai":"false","account":"sports"}`.
- **월요일만** 오디오 릴스도: `{"kind":"reel","media":"reels/YYYY-MM/YYYY-MM-DD_football.mp4","caption":"captions/YYYY-MM-DD_football_reel.txt","dry_run":"false","is_ai":"true","account":"sports"}`.

## 검토 (건너뛰지 말 것)
1. 브리프 검토 하네스: 검증 전용 서브에이전트가 README 체크리스트 전 항목 PASS/FAIL(특히 숫자 정합성·라운드 표기·날짜 최신성·추측 금지). FAIL 은 고치고 애매하면 뺀다.
2. 카드 검토 하네스 2단계(CLAUDE.md): `python3 tools/check_cards.py` + `node tools/render_cards.js` → 독립 시각 검토 → 통과하면 `/tmp/card-review/<브리프 이름>.stage2.md`.

## 발행
1. 브리프 HTML, 캡션, `publish/request.json` 만 add. 요청 항목마다 `"account":"sports"` (없으면 @hannun.brief 로 올라가니 반드시 넣는다). 맥락 읽기(부상·사고·폭력) 카드가 섞이면 게시 요청에서 뺀다.
2. `git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit` → `git pull --rebase origin main` → `git push origin HEAD:main`(실패하면 rebase 후 한 번만 재시도). push 관문 훅이 막으면 메시지대로 고친다.
3. 실패(발행 못 함, 검토 3회 FAIL)일 때만 PushNotification. 정상 발행·발행 없음은 알리지 않는다.

## 보고
다룬 경기·제외 이유·검토 FAIL 수정 내역·카드 검토 1단계 FAIL/WARN 수와 2단계 반복 횟수·원고 분량·발행 결과(push 시각, 게시 요청 항목).
---
