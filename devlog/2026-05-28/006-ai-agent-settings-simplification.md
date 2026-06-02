# AI Agent 설정 화면 단순화

- 날짜: 2026-05-28
- 리뷰 ID: zqedfbguxpwwfmqiouspvybeelnfvedm
- 요청: 기존에 잘 돌아가던 Codex 설정 화면에서 CODEX_HOME, 활성 CLI, 실행 파일 등 불필요한 항목을 제거하고 현재 모델, Reasoning, 로그인 여부, 버전만 보이도록 단순화. 업데이트는 버전 카드에 통합. 브라우저 로그인 로직 안정화. Claude Code와 헤르메스도 실행 파일, Agent HOME, 명령 템플릿을 Docker Infra 기본값으로 고정하고 숨기기.

## 변경 요약

- 시스템 설정 AI Agent 화면에서 Codex는 모델, Reasoning, 로그인, 버전 카드 중심으로 재구성하고 버전 카드에 최신 확인/업그레이드 버튼을 통합했다.
- Claude Code와 헤르메스는 모델 입력만 노출하고 실행 파일, Agent HOME, 명령 템플릿 UI와 클라이언트 payload 전송을 제거했다.
- `ai_settings` 정규화에서 숨긴 설정값을 저장/공개하지 않도록 정리했다.
- `codex_runtime`에서 Claude Code/헤르메스 HOME과 명령 템플릿을 Docker Infra 기본값으로 고정하고, 실행 파일은 env/PATH/기본 후보 경로로만 탐색하도록 조정했다.
- Codex 브라우저 로그인은 시작 대기 시간을 늘리고 device code/URL/로그인 성공 출력 파싱을 보강했다.
- README와 배포 문서의 AI Agent 설정 설명을 단순화된 화면 정책에 맞췄다.

## 변경 파일

- `README.md`
- `docs/docker-infra-deployment.md`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/model/struct/ai_settings.py`
- `src/model/struct/codex_runtime.py`
- `tests/api/test_system_settings_dynamic_menu.py`
- `devlog.md`
- `devlog/2026-05-28/006-ai-agent-settings-simplification.md`

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/model/struct/ai_assistant.py src/app/page.system/api.py`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest`: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' http://127.0.0.1:3001/system`: HTTP 200 확인
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' -X POST http://127.0.0.1:3001/wiz/api/page.system/load`: HTTP 200 wrapper와 인증 필요 응답 확인

## 남은 리스크

- 실제 Codex 브라우저 로그인 완료 플로우와 Claude Code/헤르메스 실 CLI 호출은 인증 세션 및 운영 CLI 로그인 상태가 필요해 수행하지 않았다.
