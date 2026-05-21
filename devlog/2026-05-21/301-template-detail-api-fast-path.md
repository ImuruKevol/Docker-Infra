# 301. 템플릿 상세 화면 API 초기화 경량화와 브라우저 속도 검증

## 요청

- 리뷰 ID: `eefhwxkdqqsteqaknxclghsqncjollnd`
- 템플릿 상세 화면의 `load`, `detail`, `ai_contract`, `ai_model_options` API가 느리므로 개선하고, 실제 브라우저 테스트로 각 API가 1초 미만인지 확인 요청.
- 관리자 패스워드는 제공되었지만 devlog에는 보안상 기록하지 않음.

## 변경 파일

- `src/app/page.templates/api.py`
- `src/model/struct/templates.py`
- `src/model/struct/ai_settings.py`
- `src/model/struct/template_ai.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-21/301-template-detail-api-fast-path.md`

## 변경 내용

- 템플릿 목록/상세 API에서 쓰지 않는 `services_wizard`, `compose_validator` 모델을 import 시점에 초기화하지 않고 preview/service draft 경로에서만 lazy-load하도록 변경했다.
- `ai_contract`는 새 경량 `template_ai` 모델에서 정적 템플릿 AI 계약을 반환하도록 분리했다.
- `ai_model_options`는 무거운 `ai_assistant` 대신 `ai_settings.model_options()`로 처리하고, `ai_settings`의 node/script 모델도 실제 리소스 조회 시점에만 로드하도록 늦췄다.
- 정적 테스트에 빠른 경로가 무거운 템플릿/AI 모델을 즉시 로드하지 않는 구조 검증을 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/templates.py src/model/struct/ai_settings.py src/model/struct/template_ai.py src/app/page.templates/api.py tests/api/test_services_preflight.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight` 통과.
- `wiz_project_build(projectName=main, clean=false)` 성공.
- devmode 쿠키(`season-wiz-project=main`, `season-wiz-devmode=true`)와 실제 브라우저 로그인 세션으로 `https://infra-dev.nanoha.kr/templates` 네트워크 타이밍 확인:
  - `load`: 350ms
  - `detail`: 135ms
  - `ai_contract`: 117ms
  - `ai_model_options`: 181ms

## 남은 리스크

- 측정값은 2026-05-21 dev 서버에서 한 차례 초기 화면 로딩 기준이다. 서버 부하나 네트워크 상태가 크게 변하면 절대 시간은 달라질 수 있다.
