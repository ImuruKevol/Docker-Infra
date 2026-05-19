# 262. 시스템 설정에 공식 Codex CLI npm 업데이트 기능 추가

## 사용자 요청

시스템 설정에서 공식 Codex CLI를 npm 명령어로 최신 버전을 확인한 후 버전 업그레이드를 할 수 있는 기능을 추가해줘.

## 변경 요약

- 시스템 설정의 Codex 로그인 실행 섹션에 공식 Codex CLI 업데이트 패널을 추가했다.
- `npm view @openai/codex version --json`으로 최신 버전을 확인하고, 현재 `codex --version` 결과와 비교해 업데이트 가능 여부를 표시하도록 했다.
- `npm install -g @openai/codex@latest` 업그레이드를 operation log 기반 백그라운드 작업으로 실행하고 진행 로그를 화면에서 폴링 표시하도록 했다.
- npm/Codex 실행 파일 탐지, semver 추출, 실패 응답, 업그레이드 전후 상태 payload를 `struct/codex_runtime.py`에 추가했다.

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `src/app/page.system/api.py`
- `src/app/page.system/view.ts`
- `src/app/page.system/view.pug`
- `devlog.md`
- `devlog/2026-05-19/262-codex-cli-npm-update.md`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/app/page.system/api.py`: 통과
- `npm view @openai/codex version --json && codex --version`: 최신 npm `0.131.0`, 현재 CLI `0.130.0` 확인
- 더미 WIZ 컨텍스트에서 `codex_runtime.cli_update_status({})` 호출: `@openai/codex 0.130.0 0.131.0 True` 확인
- `wiz_project_build(projectName=main, clean=false)`: 통과
- `https://infra-dev.nanoha.kr/system`, `https://infra-dev.nanoha.kr/dashboard`에 `season-wiz-project=main; season-wiz-devmode=true` 쿠키를 붙여 HTTP 200 확인
- `https://infra-dev.nanoha.kr/wiz/api/page.system/ai_codex_cli_update_check`는 동일 쿠키로 라우트 도달 후 인증 필요 401을 반환하는 것까지 확인

## 남은 리스크

- 실제 관리자 로그인 세션에서 버튼 클릭과 백그라운드 npm install 완료까지의 브라우저 플로우는 수행하지 않았다.
- 실제 업그레이드 명령은 시스템 전역 npm 패키지를 변경하므로 검증 중에는 실행하지 않았다.
