# Claude/Hermes 설치 후 액션 정책과 웹 설정 보강

- 날짜: 2026-05-29
- 리뷰 ID: cxaqmytxjrdnjjdcuazqouethjqeipfv
- 요청: Claude Code와 헤르메스가 설치 완료되면 설치 스크립트 실행 버튼을 숨기고, 업그레이드 방식 확인 후 수동/자동 정책을 반영하며, Claude Code 브라우저 로그인과 헤르메스 웹 설정 기능을 추가해 달라는 요청.

## 변경 요약

- Claude Code는 설치 완료 후 자동 업데이트 안내만 표시하고 설치 스크립트 실행 버튼을 숨기도록 처리했다.
- 헤르메스 에이전트는 설치 완료 후 설치 스크립트 실행 대신 업그레이드 버튼을 표시하고 `hermes update` 수동 업그레이드 흐름으로 연결했다.
- Claude Code 브라우저 로그인 URL/코드 입력/상태 갱신/취소 API와 UI를 추가했다.
- 헤르메스 provider, 모델, API key env, terminal backend, working directory, timeout을 시스템 설정 화면에서 저장하고 `HERMES_HOME`의 `config.yaml`/`.env`에 반영하도록 추가했다.
- installer WIZ bundle archive와 checksum을 최신 변경 기준으로 재생성했다.

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `src/model/struct/ai_settings.py`
- `src/app/page.system/api.py`
- `src/app/page.system/view.ts`
- `src/app/page.system/view.pug`
- `tests/api/test_system_settings_dynamic_menu.py`
- `installer/payload/checksums.sha256`
- `installer/payload/wiz-bundle.tar.zst`
- `devlog.md`
- `devlog/2026-05-29/009-agent-login-upgrade-hermes-settings.md`

## 확인

- 공식 문서 확인: Claude Code native install은 백그라운드 자동 업데이트, 수동 즉시 업데이트는 `claude update`.
- 공식 문서 확인: Hermes Agent는 `hermes update`, `hermes config set`, `~/.hermes/config.yaml`, `~/.hermes/.env` 설정 구조 사용.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/app/page.system/api.py`: 성공
- `python -m unittest tests/api/test_services_preflight.py tests/api/test_system_settings_dynamic_menu.py tests/api/test_installer_contract.py`: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `timeout 5s claude auth login`: 로그인 URL과 코드 입력 프롬프트 출력 확인
- `/opt/conda/bin/wiz bundle --project=main`: 성공
- `/root/docker-infra/update-wiz-bundle.sh`: 성공, payload checksum 검증 포함
- `cd installer/payload && sha256sum -c checksums.sha256`: 성공
- `curl -I` with `season-wiz-project=main; season-wiz-devmode=true` against `http://127.0.0.1:3001/dashboard`: HTTP 200
- `POST /wiz/api/page.system/load` with the same cookies: route reachable, application response 401 because no authenticated session cookie was present

## 남은 리스크

- Claude Code OAuth 완료까지 실제 브라우저에서 끝까지 진행하는 live 검증은 하지 않았다.
- 헤르메스는 현재 서버에 미설치 상태라 `hermes update`와 실제 provider 연결 실행은 설치 후 추가 확인이 필요하다.
