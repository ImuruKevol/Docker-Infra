# 238. Codex 런타임 프롬프트 컨텍스트 축약과 MCP 요약 경로 추가

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> context window 초과 문제이면 context가 초과되지 않도록 자동 요약을 시키던지 프롬프트에 내용을 전부 담지 말고 mcp 호출을 하도록 하는 방향으로 수정을 하던지 해야지 왜 아무 동작도 안해? 기능 최적화 및 로직 최적화를 진행해줘.

## 변경 요약

- Codex 호출 전에 원본 요청 context를 그대로 프롬프트에 넣지 않고, 70,000자 예산 내 compact summary로 변환하도록 했다.
- 런타임 상태, 진단 로그, 최근 operation output, container/task 오류는 핵심 필드만 남기고 긴 stdout/stderr와 반복 로그를 잘라 context window 초과 가능성을 낮췄다.
- 민감 키(api key, token, password, secret 등)는 프롬프트 요약에서 redaction 또는 omission 처리되도록 했다.
- MCP `infra_context` 응답에 `ai_request_summary`와 `request_context_keys`를 추가해, AI가 프롬프트 외부의 Docker Infra 요약 정보를 도구 호출로 확인할 수 있게 했다.
- Codex JSON event 파싱에서 `item.completed` 형태의 최종 메시지도 읽을 수 있게 보강했다.

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `tools/docker_infra_mcp.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-18/238-codex-context-budget-mcp-summary.md`

## 확인한 내용

- 대형 runtime diagnostics/recent operations/base_content를 넣은 직접 검사에서 prompt context가 `PROMPT_CONTEXT_CHAR_BUDGET` 이하로 축약되고 민감값이 포함되지 않음을 확인했다.
- MCP newline JSON stdio 수동 호출로 `infra_context`가 `ai_request_summary`와 `request_context_keys`를 반환하는 것을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py tools/docker_infra_mcp.py src/model/struct/ai_assistant.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight tests.api.test_domain_management_ui`: 18개 테스트 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `git diff --check`: 통과

## 남은 리스크

- 이미 실행 중이던 AI 검사/수정 operation은 이전 프롬프트 구성으로 시작됐으면 이번 축약 로직이 적용되지 않는다.
- 외부 Codex CLI 자체가 모델/인증/네트워크 문제로 실패하는 경우에는 context 축약과 별개로 실패할 수 있다.
