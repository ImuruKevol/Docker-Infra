# 145. 서비스 AI 검사에 화면 표시 실패 로그 신호 병합

- 날짜: 2026-05-12
- 리뷰 ID: zjcknbgqlnbbrsgddfrzcrdgivrbcbyq

## 원 요청

여전히 문제가 있어. 로그 탭에서 처리 로그에 상태는 문제 있음이라 뜨는데 검사를 돌리면 문제가 없다고 뜨고 있어. 확실하게 분석하고 수정해줘

## 변경 파일

- `src/app/page.services/view.ts`
  - 로그 탭에 표시되는 실패/취소 처리 로그를 `runtimeIssueOperations()`로 별도 수집한다.
  - AI 런타임 검사/수정 요청에 `force`와 `client_runtime_issues`를 함께 보내 현재 화면에 보이는 실패 로그, runtime summary, 문제 컨테이너 신호가 백엔드 검사에 반영되도록 했다.
- `src/model/struct/ai_assistant.py`
  - `repair_runtime` 진단에 클라이언트가 전달한 실패 로그와 런타임 신호를 병합한다.
  - DB 재조회 결과와 화면 표시 로그가 어긋나도 `operation_failed`, `client_service_status`, `client_stack_task_errors`, `client_runtime_issue` 신호를 만들 수 있게 했다.
- `tests/api/test_services_preflight.py`
  - 화면 실패 로그 신호 전달 및 백엔드 병합 계약을 정적 테스트에 추가했다.
- `devlog.md`
- `devlog/2026-05-12/145-service-ai-visible-failed-operation-signal.md`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tools/docker_infra_mcp.py src/app/page.services/api.py tests/api/test_services_preflight.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 11개 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 운영 AI 모델 호출 및 실제 장애 서비스 복구는 토큰/대상 장애 서비스가 없어 수행하지 않았다.
