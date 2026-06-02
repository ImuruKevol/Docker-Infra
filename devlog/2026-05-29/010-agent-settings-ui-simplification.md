# Claude 자동 업데이트 UI와 Hermes API Key 설정 단순화

- 날짜: 2026-05-29
- 리뷰 ID: cxaqmytxjrdnjjdcuazqouethjqeipfv
- 요청: Claude Code는 자동 업데이트이므로 최신 확인 버튼을 제거하고, 헤르메스는 환경변수명이 아닌 API Key 입력만 웹에서 저장하게 하며, 헤르메스 수동 업그레이드 안내 문구와 Working Directory 입력을 제거해 달라는 요청.

## 변경 요약

- Claude Code 탭에서는 `최신 확인` 버튼을 숨기고 자동 업데이트 안내만 남겼다.
- 헤르메스 설정에서 `API Key Env` 입력과 환경변수명 노출을 제거하고 `API Key` 입력/저장 상태만 보이도록 단순화했다.
- 헤르메스 수동 업그레이드 안내 문구를 제거했다.
- 헤르메스 Working Directory는 Docker Infra workspace root로 고정하고 화면 입력에서 제거했다.
- installer WIZ bundle archive와 checksum을 최신 변경 기준으로 재생성했다.

## 변경 파일

- `src/app/page.system/view.ts`
- `src/app/page.system/view.pug`
- `src/model/struct/ai_settings.py`
- `src/model/struct/codex_runtime.py`
- `tests/api/test_system_settings_dynamic_menu.py`
- `installer/payload/checksums.sha256`
- `installer/payload/wiz-bundle.tar.zst`
- `devlog.md`
- `devlog/2026-05-29/010-agent-settings-ui-simplification.md`

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/app/page.system/api.py`: 성공
- `python -m unittest tests/api/test_services_preflight.py tests/api/test_system_settings_dynamic_menu.py tests/api/test_installer_contract.py`: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `/opt/conda/bin/wiz bundle --project=main`: 성공
- `/root/docker-infra/update-wiz-bundle.sh`: 성공, payload checksum 검증 포함
- `cd installer/payload && sha256sum -c checksums.sha256`: 성공
- `curl -I` with `season-wiz-project=main; season-wiz-devmode=true` against `http://127.0.0.1:3001/dashboard`: HTTP 200
- `POST /wiz/api/page.system/load` with the same cookies: route reachable, application response 401 because no authenticated session cookie was present

## 남은 리스크

- 인증된 브라우저 세션에서 실제 화면 렌더링까지 확인하지는 않았다.
- 헤르메스 CLI가 미설치인 환경에서는 저장된 API Key와 provider 조합의 실제 실행 검증은 설치 후 필요하다.
