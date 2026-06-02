# AI Agent 버전 확인 저장과 공통 업그레이드 버튼 추가

- 날짜: 2026-05-29
- 리뷰 ID: zqedfbguxpwwfmqiouspvybeelnfvedm
- 요청: Codex 저장 버튼을 Agent 저장으로 바꾸고, 버전 최신 확인 정보가 새로고침 후에도 유지되게 저장하며, Claude Code/헤르메스에도 최신 확인/업그레이드 버튼 추가.

## 변경 요약

- Codex 저장 버튼 라벨을 다른 Agent 탭과 동일하게 `Agent 저장`으로 변경했다.
- `ai.agent_updates` 설정 저장 키를 추가해 Agent별 최신 버전 확인 결과와 마지막 확인 시간을 보존하도록 했다.
- Codex 최신 확인/업그레이드 상태를 저장소에 반영하고, load payload에서 저장된 업데이트 정보를 다시 내려주도록 연결했다.
- Claude Code/헤르메스에도 최신 확인/업그레이드 버튼과 최신 버전/마지막 확인 표시를 추가했다.
- CodexRuntime에 Agent 공통 npm 패키지 최신 버전 확인 흐름을 추가하고 Claude Code/헤르메스 설치 완료 후 업데이트 상태를 갱신하도록 보강했다.
- 시스템 설정 정적 계약 테스트를 신규 API/저장 키/UI 문구에 맞춰 갱신했다.

## 변경 파일

- `src/app/page.system/api.py`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/model/struct/ai_settings.py`
- `src/model/struct/codex_runtime.py`
- `tests/api/test_system_settings_dynamic_menu.py`
- `devlog.md`
- `devlog/2026-05-29/004-ai-agent-update-cache-common-buttons.md`

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/model/struct/ai_assistant.py src/app/page.system/api.py`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest`: 성공
- `git diff --check -- src/app/page.system/view.pug src/app/page.system/view.ts src/app/page.system/api.py src/model/struct/ai_settings.py src/model/struct/codex_runtime.py tests/api/test_system_settings_dynamic_menu.py`: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' http://127.0.0.1:3001/system`: HTTP 200 확인
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' -X POST http://127.0.0.1:3001/wiz/api/page.system/load`: HTTP 200 wrapper와 인증 필요 응답 확인

## 남은 리스크

- 인증 세션이 없는 환경이라 실제 최신 확인/업그레이드 버튼 클릭과 저장된 `ai.agent_updates`의 화면 복원은 브라우저에서 직접 검증하지 못했다.
- Hermes 최신 확인은 기본 npm 패키지 `hermes-agent` 또는 환경변수 `DOCKER_INFRA_HERMES_AGENT_NPM_PACKAGE`가 실제 배포 환경에서 유효해야 정상 동작한다.
