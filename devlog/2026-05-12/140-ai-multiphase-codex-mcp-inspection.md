# 140. AI 서비스 생성/수정 2단계 보정 플로우와 Docker Infra MCP 상태 조회 도구 보강

- 날짜: 2026-05-12
- 리뷰 ID: hufvrianlhobxsyvrorjmbvwffdkjioy

## 원 요청

AI를 활용한 서비스 생성 및 수정 시 AI 호출 자체는 여러 번 해야할 것 같아. 첫 번째 호출 때 어떤 이미지를 사용할 것인지, 컨테이너별로 어떤 포트들이 사용되는지 등에 대한 초안을 작성하고, 그 정보를 바탕으로 현재 Docker Infra에 띄운다면 어떤 서버에 띄울 것인지, 해당 서버의 포트 사용 정보, docker image와 버전이 실제 존재하는지 등 확인을 해야해. 그 다음에 다시 AI에 요청해서 검증 및 보정을 해야할 것 같아. 가능하면 codex용 MCP를 만들어서 AI가 Docker Infra의 상태나 값들을 읽어서 활용할 수 있도록 해야해.

## 변경 파일

- `src/model/struct/ai_assistant.py`
  - 서비스 생성/수정 AI를 1차 초안 호출, Docker Infra 상태 검사, 2차 보정 호출 순서로 재구성했다.
  - 1차 초안 결과를 정규화한 뒤 `services_preflight`와 `services_placement`로 배치 후보, 공개 포트 조정/사용 여부, 이미지 검증, Compose 검증 결과를 수집해 2차 AI 컨텍스트에 전달한다.
  - 스트리밍 API도 동일한 단계 메시지와 최종 보정 결과를 반환하도록 맞췄다.
- `src/model/struct/codex_runtime.py`
  - Codex MCP 컨텍스트에 등록 서버, 배치 추천, Docker Infra 런타임 값을 포함했다.
  - Codex 실행 시 `infra_context`, `docker_image_check`, `server_port_check` MCP 도구를 노출한다.
- `tools/docker_infra_mcp.py`
  - `infra_context`, `docker_image_check`, `server_port_check` 도구를 추가했다.
  - 기존 서버 조회, 서버 정보 수집, SSH 실행, Docker image search 도구와 함께 Codex 모델이 Docker Infra 상태를 조회할 수 있게 했다.
- `tests/api/test_services_preflight.py`
  - 다단계 AI 플로우와 MCP 도구 노출이 정적 계약에 포함되도록 테스트를 보강했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tools/docker_infra_mcp.py tests/api/test_services_preflight.py`: 통과
- `python -m unittest tests.api.test_services_preflight`: 11개 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- Docker Infra MCP stdio 초기화 및 `tools/list`: `infra_context`, `docker_image_check`, `server_port_check` 포함 확인
- 수정된 Codex debug 바이너리 `/root/docker-infra/codex/codex-rs/target/debug/codex --version`: `codex-cli 0.0.0`
- 로컬 fake Responses API와 MCP 설정을 붙인 `codex exec` smoke 테스트: 종료 코드 0, 최종 응답 `{"ok": true, "source": "fake-responses-smoke"}` 확인

## 남은 리스크

- 실제 OpenAI/Gemini/Ollama 토큰 또는 운영 모델 호출은 현재 환경에서 수행하지 않았다.
- 원격 서버 포트/이미지 확인은 등록 노드 SSH 자격 증명과 네트워크 상태에 따라 warning으로 떨어질 수 있다.
- 2차 AI 보정 품질은 모델이 검사 결과를 얼마나 정확히 반영하는지에 의존하므로, 최종 저장 전 기존 preflight 검증은 계속 필요하다.
