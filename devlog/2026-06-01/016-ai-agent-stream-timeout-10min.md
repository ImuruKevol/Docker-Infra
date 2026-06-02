# AI Agent 스트림 응답 대기 시간 10분 확장

- **ID**: 016
- **날짜**: 2026-06-01
- **유형**: 버그 수정

## 작업 요약
AI Agent 스트림 응답이 갱신되지 않을 때 30초 후 실패 처리하던 프론트엔드 제한을 10분으로 확장했다.
전체 스트림 최대 대기 시간도 같은 10분 제한을 사용하도록 맞춰, 총 대기 제한이 먼저 동작하는 문제를 방지했다.

## 원문 요청사항
```text
"AI Agent 응답이 30초 이상 갱신되지 않았습니다." 라고 뜨는데 기본적으로 10분까지는 기다리도록 해줘.
```

## 변경 파일 목록
- `src/angular/app/app.component.ts`
  - AI Agent 스트림 idle timeout과 전체 timeout을 `10 * 60 * 1000`ms로 통일.
  - idle timeout 오류 문구를 `10분 이상 갱신되지 않았습니다`로 변경.
- `tests/api/test_ai_agent_history.py`
  - 10분 timeout 계약과 기존 30초 문구 제거를 검증하는 정적 테스트 추가.
- `devlog.md`
- `devlog/2026-06-01/016-ai-agent-stream-timeout-10min.md`

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_ai_agent_history.py`
- 성공: `git diff --check -- src/angular/app/app.component.ts tests/api/test_ai_agent_history.py`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: DEV 쿠키(`season-wiz-project=main`, `season-wiz-devmode=true`)를 적용한 `https://infra-dev.nanoha.kr/main.js`에서 10분 timeout 반영 확인.

## 남은 리스크
- 실제 브라우저에서 10분 동안 응답이 없는 Agent 요청을 대기시키는 장시간 E2E 검증은 수행하지 않았다.
