# AI 기능 Agent 기반 재정리

- 날짜: 2026-05-28
- 리뷰 ID: cxaqmytxjrdnjjdcuazqouethjqeipfv
- 요청: 일단 작업지시서의 내용에 따라 AI를 사용하는 부분들을 agent 기반으로 싹 정리해줘.

## 변경 요약

- OpenAI/Gemini/Ollama 직접 API 실행 경로와 모델/토큰 설정 UI/API를 제거하고 Codex, Claude Code, 헤르메스 에이전트 3개 Agent 설정으로 재구성했다.
- Agent 실행은 Codex CLI 또는 일반 Agent CLI에 Docker Infra MCP 설정과 컨텍스트를 주입하는 방식으로 통일했다.
- 시스템 설정 AI 화면, API, ai_settings/ai_assistant/codex_runtime, local command catalog/scripts, installer env, 문서, 테스트를 Agent 기준으로 정리했다.

## 변경 파일

- README.md
- docs/docker-infra-deployment.md
- docs/service-ai-codex-agent-design.md
- docs/template-removal-todo.md
- installer/docker-infra.env.example
- installer/install.sh
- src/app/page.system/api.py
- src/app/page.system/view.pug
- src/app/page.system/view.ts
- src/model/struct/ai_assistant.py
- src/model/struct/ai_settings.py
- src/model/struct/codex_runtime.py
- src/model/struct/local_command_catalog.py
- src/model/struct/local_command_scripts.py
- tests/api/test_backup_registry_nodes.py
- tests/api/test_installer_contract.py
- tests/api/test_services_preflight.py
- tests/api/test_system_settings_dynamic_menu.py

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/model/struct/ai_assistant.py src/model/struct/local_command_catalog.py src/model/struct/local_command_scripts.py src/app/page.system/api.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_installer_contract.InstallerContractTest tests.api.test_backup_registry_nodes.BackupRegistryNodeStaticContractTest`
- `bash -n installer/install.sh`
- WIZ build `main` 성공
- 기존 direct API/Ollama 관련 문자열 정적 검색에서 관련 잔존 경로 없음 확인

## 남은 리스크

- Claude Code와 헤르메스 실제 CLI 설치/로그인 환경에서 실호출 검증은 별도로 필요하다.
- 브라우저에서 시스템 설정 화면을 직접 조작하는 live 검증은 수행하지 않았다.
