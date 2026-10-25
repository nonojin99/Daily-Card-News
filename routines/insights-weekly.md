# 주간 성과 분석 — 예약 루틴 프롬프트 (2026-10-25)

> claude.ai 예약 루틴에 **매주 월요일 16:00 KST** 로 등록한다(월요일 인사이트 수집 15:25 뒤). 아래 `---` 사이를 그대로 붙여 넣는다.

---
GitHub 레포 nonojin99/Daily-Card-News 의 **주간 성과 분석**을 하세요. 이 세션은 매주 월요일 한국시간 16시에 새로 시작되며 이전 대화 기억이 없습니다. 보고는 한국어로 씁니다. Firecrawl 호출 금지, GitHub Actions 실행 시도 금지.

1. `TZ=Asia/Seoul date '+%F %A'` 확인, `git pull -q origin main`. README '릴스 오프닝 A/B'·'검수 체계'와 `insights/summary.md`·`insights/manual/reel-sources.md`(수동 기록한 유입 경로) 를 읽으세요.
2. `insights-analyst` 에이전트를 부르세요(지난 7일 + 누적). 판정 규칙은 에이전트 정의와 README 에 미리 정한 것만 씁니다. 표본이 모자라면 '판정 보류'가 맞는 답입니다 — 결론을 만들지 마세요.
3. 결과를 `insights/weekly/YYYY-MM-DD.md`(오늘 날짜)에 저장하고 그 파일 하나만 add → `git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -m "insights weekly YYYY-MM-DD"` → `git pull --rebase origin main` → `git push origin HEAD:main`.
4. 규칙 변경 제안은 **적용하지 않습니다**(README·도구·요청 파일 수정 금지). 사용자가 승인하면 그때 다른 세션이 바꿉니다.
5. PushNotification 한 번(항상): `<routine_summary>[주간 분석] 요약 첫 줄` 다음 줄에 판정 2~3개(예: '오프닝: 판정 보류(정지 3·움직임 2, 필요 4·4)'), 규칙 변경 제안이 있으면 '승인 요청: …', 끝 줄 보고서 경로 `insights/weekly/YYYY-MM-DD.md`</routine_summary>`. 실패하면 `⚠ [주간 분석] 실행 실패 — 이유`.
---
