# 09:30 서브 플러스 루틴 — 예약 루틴 프롬프트 (2026-11-23 정리판)

> claude.ai 예약 루틴(매일 09:30 KST)에 아래 `---` 사이를 그대로 붙여 넣는다.
> 무엇을 만들지(요일·주제·규칙)는 저장소 `CLAUDE.md` 1절 '09:30 서브 플러스' 표가 정한다 — 주제를 바꿀 땐 CLAUDE.md 만 고친다.
> 옛 프롬프트: `docs/history/routines/sub-plus-2026-10-21.md`

---
GitHub 레포 nonojin99/Daily-Card-News 의 오늘자 서브 플러스 브리프를 만들어 발행하세요. 이 세션은 매일 한국시간 오전 9시 30분에 새로 시작되며 이전 대화 기억이 없습니다. 사용자는 한국어를 씁니다 — 브리프와 보고 모두 한국어로 쓰세요.

규칙은 저장소의 `CLAUDE.md` 가 전부입니다(세션 시작 때 자동으로 읽힘). 이 프롬프트와 다르면 CLAUDE.md 를 따르세요. 형식·도구 사용법은 README 에서 찾아보세요.

순서:
1. `TZ=Asia/Seoul date '+%Y-%m-%d %A'` 로 오늘(KST)을 확인하고 CLAUDE.md 1절 '09:30 서브 플러스' 표로 오늘 만들 브리프를 정하세요. 표에 없는 요일이면 아무것도 하지 말고 끝내세요(알림 없음).
2. 같은 종류의 지난주 브리프 tracker 와 오늘 06:00 메인 브리프를 읽어 중복을 피하세요.
3. 브리프마다 리서치 서브에이전트를 띄우세요(화요일은 2개 동시). CLAUDE.md 3절 규칙과 1절의 주제별 범위·금지 사항을 그대로 넘기세요.
4. CLAUDE.md 4절과 1절 주제별 규칙대로 브리프를 쓰세요.
5. `brief-fact-checker` 로 브리프 검토 → FAIL 수정.
6. CLAUDE.md 5절 카드 검토 하네스를 브리프마다 따로.
7. 브리프 HTML 만 add 해서 커밋(`YYYY-MM-DD <종류> brief`)하고 `git pull --rebase origin main` → `git push origin HEAD:main`.
8. CLAUDE.md 6절대로 인스타(Actions 결과 기다림 → 실물 검수 → 승인 + 캡션 + 요청 한 커밋, 화요일은 머니 → 헬스 순).
9. CLAUDE.md 7절대로 알림(PushNotification + `alerts/outbox/<날짜_시각>_subplus.txt`)과 마무리 보고.
---
