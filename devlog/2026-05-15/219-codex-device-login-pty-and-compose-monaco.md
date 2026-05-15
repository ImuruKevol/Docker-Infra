# 219. Codex 브라우저 로그인 PTY 처리와 Compose Monaco 편집 개선

- 날짜: 2026-05-15
- 리뷰 ID: pofkvorwkbnazooamriktpwumgpcdinu
- 프로젝트: main

## 원 요청

```text
브라우저 로그인을 누르니 잠깐 뭐가 떴다가 바로 사라지고 있어. one-time code는 뜨지도 않고, 발급 대기 라고만 뜬 것 같아.

고급 사용자용 Compose 직접 작성 시 textarea 말고 monaco editor로 편집할 수 있도록 해줘. 그리고 직접 작성 후 Compose 적용을 눌렀을 때 에러가 나면 message값만 표시하고 있는데 자세한 reason도 표시를 해줘야 해. 이미 reason 키값은 message값고 같이 들어오는데 표시만 안되고 있어.
```

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `src/app/page.system/view.ts`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/app/page.services/view.ts`
- `tests/api/test_services_preflight.py`
- `tests/api/test_system_settings_dynamic_menu.py`
- `devlog.md`
- `devlog/2026-05-15/219-codex-device-login-pty-and-compose-monaco.md`

## 작업 내용

- `codex login --device-auth` 실행을 pipe 기반 캡처에서 PTY 기반 캡처로 바꿔 Codex CLI가 터미널에 쓰는 device-code 출력을 웹 API에서 안정적으로 읽도록 했다.
- 시스템 설정 화면의 Codex 브라우저 로그인 상태 동기화에서 진행 중 세션이 일시적으로 빈 응답을 받아도 즉시 패널을 지우지 않도록 했다.
- 서비스 생성 화면의 고급 Compose 직접 작성 영역을 `textarea`에서 `nu-monaco-editor`로 교체하고 YAML 편집 옵션을 추가했다.
- Compose 검증/적용 오류 포맷에 최상위 `reason`과 상세 항목의 `reason`을 함께 표시하도록 했다.

## 확인 결과

- `python -m py_compile src/model/struct/codex_runtime.py src/app/page.system/api.py` 통과
- `python -m unittest tests.api.test_services_preflight tests.api.test_system_settings_dynamic_menu` 통과, 15개 실행 및 2개 스킵
- `git diff --check` 통과
- `wiz_project_build(projectName="main", clean=false)` 통과

## 남은 리스크

- 실제 Codex 계정 device 로그인 완료 여부는 one-time code를 발급받아 사용자가 브라우저에서 인증해야 최종 확인할 수 있다.
