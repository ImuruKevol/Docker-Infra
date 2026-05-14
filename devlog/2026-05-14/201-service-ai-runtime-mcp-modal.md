# 201. 서비스 AI MCP scope와 백그라운드 모달 개선

- 날짜: 2026-05-14
- 요청: "AI를 이용해 서비스 점검 및 수정 시 MCP 도구가 노출되어있지 않다는 로그가 중간중간 보여 에러처럼 느껴진다. 필요한 MCP 도구를 추가하고 각 세션의 MCP 도구 허용 범위를 재설정해달라. AI 백그라운드 검사/수정 모달도 컴팩트하고 예쁘게 정리해달라."

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `tools/docker_infra_mcp.py`
- `src/model/struct/ai_assistant.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `docs/service-ai-codex-agent-design.md`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-14/201-service-ai-runtime-mcp-modal.md`

## 작업 내용

- Docker Infra MCP에 `browser_probe` 도구를 추가해 허용된 서비스 URL의 HTTP 상태, 최종 URL, title, 본문 텍스트 일부를 브라우저형 요청으로 점검할 수 있게 했다.
- 서비스 초안, preflight 보정, 배포 후 검증, 런타임 점검, 런타임 수정 scope별 MCP 도구 목록을 중앙화하고 `container_action`, `ssh_command` 허용 여부를 세션 입력에 맞춰 필터링했다.
- AI 프롬프트와 MCP guidance에 노출되지 않은 도구를 운영자용 이슈/경고로 보고하지 말고 허용된 도구와 수집된 컨텍스트로 대체하라는 정책을 추가했다.
- 서비스 처리 로그와 AI 스트림에서 "MCP 도구가 노출되지 않음/사용 불가" 계열 노이즈를 사용자에게 오류처럼 표시하지 않도록 정규화했다.
- AI 백그라운드 검사/수정 모달을 더 작은 폭, 짧은 입력, 모델 선택, 서버 진단 토글, 자동 조치 토글, 점검 범위 칩, 축약 진행 요약 중심으로 재구성했다.
- 정적 계약 테스트와 설계 문서에 신규 MCP 도구와 scope 정책을 반영했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_assistant.py tools/docker_infra_mcp.py` 성공.
- MCP smoke test에서 `browser_probe`가 enabled tool로 노출되는 것을 확인.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight` 성공.
- `wiz_project_build(clean=false, projectName="main")` 성공.
- `git diff --check` 성공.

## 남은 리스크

- `browser_probe`는 실제 JS 실행 브라우저가 아니라 브라우저형 HTTP 요청 기반 점검이다. 로그인 이후 상호작용이나 SPA 렌더 완료 검증은 별도 브라우저 자동화 도구가 필요할 수 있다.
- 실제 운영 서비스에 대해 AI 검사/수정 end-to-end 실행은 이번 검증에서 수행하지 않았다.
