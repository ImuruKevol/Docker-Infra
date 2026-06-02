# AI Agent 버튼 즉시 표시와 로딩 상태 패널 추가

- **ID**: 003
- **날짜**: 2026-06-01
- **유형**: 개선

## 작업 요약
AI Agent 상태 API 응답이 끝나기 전에도 우측 하단 Agent 버튼이 즉시 보이도록 표시 조건을 변경했다.
상태 확인 중이거나 Agent를 사용할 수 없는 경우에는 패널 내부에 현재 상태 메시지를 표시하고, 채팅 전송과 히스토리 조작은 준비 완료 후에만 가능하도록 제한했다.

## 원문 요청사항
```text
화면 우측 하단의 Agent 버튼 아이콘이 필요한 정보들을 모두 불러온 후에야 화면에 보이는데, 버튼은 바로 보이게 하고, 로드가 덜되었으면 채팅창이나 거기에 로드 중같은걸 표시하도록 해줘.
```

## 변경 파일 목록
- `src/angular/app/app.component.ts`: Agent 버튼 표시 조건을 상태 로딩과 분리하고, 준비/로딩/비활성 상태 helper 및 전송 가드 추가.
- `src/angular/app/app.component.pug`: 로딩/비활성 상태 패널, 토글 버튼 로딩 아이콘, 준비 전 히스토리 버튼 비활성 처리 추가.
- `src/angular/app/app.component.scss`: 상태 패널과 토글 로딩/비활성 스타일 및 다크모드 스타일 추가.
- `tests/api/test_ai_agent_history.py`: Agent 버튼 즉시 표시와 로딩 상태 UI 정적 계약 테스트 추가.
- `devlog.md`, `devlog/2026-06-01/003-ai-agent-loading-toggle.md`: 작업 이력 기록.

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history` 성공.
- `git diff --check` 대상 파일 검사 성공.
- `wiz_project_build(clean=false)` 성공.
