# 운영 감시 — 예약 루틴 프롬프트 (2026-10-25)

> claude.ai 예약 루틴에 **매일 22:40 KST** 로 등록한다(저녁 릴스 21:07 예약 뒤). 아래 `---` 사이를 그대로 붙여 넣는다.
> 문제가 있을 때만 알린다(이상 없으면 조용히 끝 — CLAUDE.md '매일 Slack 요약'의 예외: 이 루틴은 발행을 하지 않는다).

---
GitHub 레포 nonojin99/Daily-Card-News 의 **운영 감시**를 하세요. 이 세션은 매일 한국시간 22시 40분에 새로 시작되며 이전 대화 기억이 없습니다. 보고는 한국어로 씁니다. 파일을 고치거나 push 하지 않습니다(찾기만 — 단 CLAUDE.md '카카오 알림'의 `alerts/outbox/…_ops.txt` 하나는 예외). Firecrawl 호출 금지, GitHub Actions 실행 시도 금지.

1. `TZ=Asia/Seoul date '+%F %H:%M %A'` 로 지금 시각을 확인하고 `git pull -q origin main` 하세요.
2. `python3 tools/ops_check.py` 를 실행해 결과를 저장하세요(검수 대기·MP3/카드/MP4 누락·인사이트 오류).
3. GitHub MCP 도구(`mcp__github__actions_list`, 필요하면 ToolSearch 로 불러오기)로 지난 24시간 워크플로 실행 목록(이름·결론·시각·커밋 제목)을 가져오세요. 실패한 실행은 `mcp__github__get_job_logs` 로 실패 단계 로그 끝부분 20줄만 보세요. 권한 오류로 못 가져오면 그 사실을 적고 저장소 기록만으로 진행합니다.
4. `ops-monitor` 에이전트를 부르고 2·3의 결과를 함께 주세요. 에이전트가 점검 목록 1~6을 판정합니다.
5. 결과:
   - 에이전트가 정확히 `이상 없음` 이면 알림 없이 끝냅니다.
   - 문제가 있으면 PushNotification 한 번: `<routine_summary>⚠ [운영 감시] 문제 N건 — 가장 심각한 것 한 줄` 다음 줄부터 문제마다 한 줄(무엇이·언제·사람이 할 일), 끝 줄 앱 주소 `nonojin99.github.io/Daily-Card-News/app/`</routine_summary>`.
   - `"review":"human"` 승인 대기 항목은 미리보기 주소와 '승인 요청'을 함께 적습니다.
   - 루틴 자체가 못 돈 경우(pull 실패·도구 없음)도 `⚠ [운영 감시] 실행 실패 — 이유` 로 알립니다.
   - PushNotification 을 보낼 때마다 같은 내용을 `alerts/outbox/YYYY-MM-DD_HHMM_ops.txt`(KST, 태그 없이 200자 이내)로 써서 그 파일 하나만 커밋·push 합니다(카카오 알림, 2026-10-29~).
---
