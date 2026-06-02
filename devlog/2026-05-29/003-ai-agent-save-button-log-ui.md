# AI Agent 설정 저장 버튼과 진행 로그 UI 정리

- 날짜: 2026-05-29
- 리뷰 ID: zqedfbguxpwwfmqiouspvybeelnfvedm
- 요청: Codex 저장, Agent 저장 버튼은 오른쪽에 붙이고, Codex 업그레이드 진행 상태 로그는 완료 시 닫을 수 있게 하며, Claude Code/헤르메스 탭 UI를 Codex 기준으로 통일.

## 변경 요약

- Codex 하단 작업 영역에서 브라우저 로그인/상태 확인은 왼쪽, Codex 저장은 오른쪽에 배치했다.
- Claude Code/헤르메스 하단 작업 영역에서도 설치 스크립트 실행/상태 확인은 왼쪽, Agent 저장은 오른쪽에 배치했다.
- Codex 업그레이드 진행 로그에 완료/실패/취소 후 닫기 버튼을 추가했다.
- Claude Code/헤르메스 탭을 Codex와 같은 모델 입력 폭, 문단형 로그인 상태/버전 표시, 진행 로그, 좌우 분리 버튼 구조로 정리했다.
- Agent 설치/업데이트 진행 로그에도 완료 후 닫기 버튼을 추가하고 정적 계약 테스트를 갱신했다.

## 변경 파일

- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `tests/api/test_system_settings_dynamic_menu.py`
- `devlog.md`
- `devlog/2026-05-29/003-ai-agent-save-button-log-ui.md`

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/model/struct/ai_assistant.py src/app/page.system/api.py`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest`: 성공
- `git diff --check -- src/app/page.system/view.pug src/app/page.system/view.ts tests/api/test_system_settings_dynamic_menu.py`: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' http://127.0.0.1:3001/system`: HTTP 200 확인
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' -X POST http://127.0.0.1:3001/wiz/api/page.system/load`: HTTP 200 wrapper와 인증 필요 응답 확인

## 남은 리스크

- 인증 세션이 없는 환경이라 실제 로그인 상태에서의 버튼 클릭과 진행 로그 닫기 상호작용은 브라우저로 직접 검증하지 못했다.
