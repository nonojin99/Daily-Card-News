# 06:00 메인 루틴 — 예약 루틴 프롬프트 (2026-11-22 정리판)

> claude.ai 예약 루틴(매일 06:00 KST)에 아래 `---` 사이를 그대로 붙여 넣는다.
> 세부 규칙은 저장소 `CLAUDE.md` 에 있고 세션이 자동으로 읽는다. 이 프롬프트는 순서만 적는다 — 규칙이 바뀌면 CLAUDE.md 만 고치면 된다.

---
GitHub 레포 nonojin99/Daily-Card-News 의 오늘자 브리프를 만들어 발행하세요. 이 세션은 매일 한국시간 오전 6시에 새로 시작되며 이전 대화 기억이 없습니다. 사용자는 한국어를 씁니다 — 브리프와 보고 모두 한국어로 쓰세요.

규칙은 저장소의 `CLAUDE.md` 가 전부입니다(세션 시작 때 자동으로 읽힘). 이 프롬프트와 다르면 CLAUDE.md 를 따르세요. 형식·도구 사용법은 README 에서 찾아보세요.

순서:
1. `TZ=Asia/Seoul date '+%Y-%m-%d %A'` 로 오늘(KST)을 확인하고, CLAUDE.md 1절 표로 오늘 만들 서브 브리프와 인스타 게시 여부를 정하세요.
2. 어제 메인 브리프의 tracker 와 최근 3~4일 제목, 지난주 같은 요일 서브 브리프를 읽으세요.
3. 리서치 서브에이전트 2개(메인·서브)를 동시에 띄우세요. CLAUDE.md 3절(Firecrawl 금지, 403 도메인, URL 단위 귀속, 중복 배제)을 그대로 넘기세요. 메인 에이전트는 서울 날씨 기사도 확인합니다.
4. CLAUDE.md 4절대로 두 브리프를 쓰세요.
5. `brief-fact-checker` 로 브리프 검토 → FAIL 수정.
6. CLAUDE.md 5절 카드 검토 하네스(1단계 → `card-visual-reviewer` 2단계 → stage2 기록)를 메인·서브 모두.
7. 오늘 브리프 HTML 만 add 해서 커밋하고 `git pull --rebase origin main` → `git push origin HEAD:main`. 실패하면 rebase 후 한 번만 재시도, 그래도 막히면 Drive 발행함(README '발행 경로').
8. 인스타 게시일이면 CLAUDE.md 6절(Actions 결과 기다림 → 실물 검수 → 승인 + 캡션 + 요청 한 커밋).
9. CLAUDE.md 7절대로 알림(PushNotification + `alerts/outbox/` 파일)과 마무리 보고. 두 HTML 은 SendUserFile 로도 보내세요.
목표: 07:00 KST 전에 브리프 push.
---
