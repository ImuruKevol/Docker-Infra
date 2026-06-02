# Codex 설정 문단형 UI와 업그레이드 셸 수정

- 날짜: 2026-05-29
- 리뷰 ID: zqedfbguxpwwfmqiouspvybeelnfvedm
- 요청: Codex 설정에서 모델/Reasoning 폭을 fit-content 느낌으로 줄이고, 현재 모델/Reasoning 카드를 삭제하며, 로그인 상태/버전은 카드가 아닌 문단 형태로 변경. Codex 업그레이드 시 `sh: 1: set: Illegal option -o pipefail` 오류 수정.

## 변경 요약

- Codex 모델 입력과 Reasoning select를 full-width grid에서 고정 폭 flex 배치로 변경했다.
- 현재 모델/Reasoning 정보 카드를 제거하고 로그인 상태와 버전을 문단형 상태 영역으로 정리했다.
- Codex/Agent 설치 스크립트가 bash 전용 `pipefail`을 사용하므로 백그라운드 설치 실행 셸을 `sh -lc`에서 `bash -lc`로 변경했다.
- 시스템 설정 정적 계약 테스트에 Codex 카드 제거와 bash 실행 경로 검증을 추가했다.

## 변경 파일

- `src/app/page.system/view.pug`
- `src/model/struct/codex_runtime.py`
- `tests/api/test_system_settings_dynamic_menu.py`
- `devlog.md`
- `devlog/2026-05-29/001-codex-settings-ui-upgrade-shell.md`

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/model/struct/ai_assistant.py src/app/page.system/api.py`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest`: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' http://127.0.0.1:3001/system`: HTTP 200 확인
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' -X POST http://127.0.0.1:3001/wiz/api/page.system/load`: HTTP 200 wrapper와 인증 필요 응답 확인
- `git diff --check` 대상 파일 확인: 성공

## 남은 리스크

- 실제 npm global 업그레이드는 시스템 패키지 변경을 수반하므로 실행하지 않았다. 실행 명령은 `bash -lc`로 변경되어 보고된 `sh pipefail` 오류 경로는 제거됐다.
