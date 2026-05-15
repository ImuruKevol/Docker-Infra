# 서비스 AI 사용 가능 조건과 Codex 브라우저 로그인

- **ID**: 218
- **날짜**: 2026-05-15
- **유형**: 기능 추가

## 작업 요약
시스템 설정에서 사용 중인 AI 모델이 없을 때 서비스 생성/수정/런타임 점검의 AI 진입점을 숨기고, 서비스 생성 화면은 Compose 직접 작성 모드를 자동으로 열도록 조정했다.
시스템 설정의 Codex 탭에서 `codex login --device-auth`를 웹으로 시작하고 one-time code, 로그인 URL, 진행 상태를 확인할 수 있는 API와 UI를 추가했다.

## 원문 요청사항
```text
작업 시작해줘.

서비스 생성 시, AI 점검 시 AI를 사용하도록 되어있는데, 이것들이 시스템 설정에서 AI들이 하나도 사용 설정이 되어있지 않으면 보이지 않거나 해야해. 특히 서비스 초안 만들기 시에는 AI 활성화가 하나도 활성화가 안되어있으면 고급 사용자용 모드를 자연스럽게 보여주도록 구성이 되어야 해.

그리고 현재 codex는 무조건 터미널에 들어가서 "codex login --device-auth"를 한 다음 수동으로 로그인을 해야해. 근데 이 과정을 터미널이 아니라 시스템 설정 웹 화면에서 할 수 있도록 지원하고 싶어. "codex login --device-auth" 명령어를 치면 아래와 같이 뜨고, 사용자가 터미널에 뜨는 one-time code를 브라우저를 통해 로그인 후 입력할 때까지 기다리도록 되어있어. 근데 이걸 웹 화면으로 하고싶어.
root@season:~/installer/payload# codex login --device-auth

Welcome to Codex [v0.130.0]
OpenAI's command-line coding agent

Follow these steps to sign in with ChatGPT using device code authorization:

1. Open this link in your browser and sign in to your account
   https://auth.openai.com/codex/device

2. Enter this one-time code (expires in 15 minutes)
   OOOO-OOOOO
Device codes are a common phishing target. Never share this code.
```

## 변경 파일 목록
- `src/model/struct/ai_assistant.py`
  - AI 모델 옵션에서 비활성 Codex를 기본 노출하지 않도록 변경.
  - 사용 가능한 AI 모델이 없을 때 빈 옵션과 안내 메시지를 반환.
  - 비활성 Codex 모델 선택 요청을 `AI_PROVIDER_NOT_CONFIGURED`로 차단.
- `src/app/page.services.create/view.ts`
  - AI 모델 사용 가능 여부 상태를 추가.
  - AI 모델이 없으면 Compose 직접 작성 패널을 자동으로 열고 단계 설명/검증 문구를 조정.
- `src/app/page.services.create/view.pug`
  - AI 모델이 없을 때 AI 자동 구성 영역을 숨기고 Compose 직접 작성 안내를 표시.
- `src/app/page.services/view.ts`
  - 서비스 수정 AI와 런타임 AI 검사/수정 진입 전 모델 사용 가능 여부를 확인.
  - AI 모델이 없으면 AI 수정 섹션과 런타임 AI 모달 진입을 차단.
- `src/app/page.services/view.pug`
  - AI 모델이 없으면 `AI 검사/수정`과 `AI 수정안` 버튼을 숨김.
- `src/model/struct/codex_runtime.py`
  - `codex login --device-auth` 백그라운드 실행, one-time code/URL 파싱, 상태 폴링, 취소 기능을 추가.
- `src/app/page.system/api.py`
  - Codex device login 시작/상태/취소 API를 추가.
- `src/app/page.system/view.ts`
  - Codex device login 시작, 상태 폴링, 취소, 코드 복사 동작을 추가.
- `src/app/page.system/view.pug`
  - Codex 설정 탭에 브라우저 로그인 버튼, 로그인 URL, one-time code, 상태 갱신 UI를 추가.
- `tests/api/test_services_preflight.py`
  - AI 비활성 시 UI 숨김/Compose 직접 작성 진입 계약을 보강.
- `tests/api/test_system_settings_dynamic_menu.py`
  - Codex device login API/UI/런타임 계약을 보강.

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/app/page.system/api.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight tests.api.test_system_settings_dynamic_menu`
- `wiz_project_build(projectName="main", clean=false)`
