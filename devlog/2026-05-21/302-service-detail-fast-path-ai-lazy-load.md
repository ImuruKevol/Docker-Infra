# 302. 서비스 상세 fast path와 AI 옵션 지연 로딩 적용

## 요청

- 리뷰 ID: `ilynrvzpxhohddzosaprvxqjvnwvrnti`
- 제목: 서비스 관리 화면 API 최적화
- 원 요청: `detail_service`가 여전히 약 3.65초 걸리고, `ai_model_options`를 초기 화면에서 바로 호출하지 않아도 되므로 각 API가 가능하면 1초 미만이 되도록 추가 최적화하고 브라우저 테스트로 확인해 달라는 요청.

## 변경 파일

- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/model/struct/services_detail_fast.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-21/302-service-detail-fast-path-ai-lazy-load.md`

## 변경 내용

- `detail_service(lightweight=true)`가 대형 `services` 매니저를 로드하지 않도록 `services_detail_fast` 전용 모델을 추가했다.
- fast path 상세 응답은 서비스/도메인/파일 루트/저장된 런타임 상태만 반환하고, 작업 로그·백업·인증서 분석은 초기 상세 렌더에서 제외했다.
- `detail_service_extras`도 fast 모델의 DB 기반 요약을 사용하도록 바꿔 백업 상태와 인증서 대상 정보를 빠르게 반환하게 했다.
- 서비스 화면 `ngOnInit`에서 `ai_model_options` 즉시 호출을 제거하고, AI 기능을 실제 열거나 실행할 때만 모델 옵션을 조회하도록 유지했다.
- `ai_model_options` API가 무거운 `ai_assistant` 대신 `ai_settings.model_options()`를 직접 호출하도록 변경했다.
- release/migration 모달처럼 백업 상태가 필요한 사용자 액션 시점에만 부가 정보를 지연 조회하도록 조정했다.
- 정적 계약 테스트에 fast 모델 사용, AI 옵션 지연 로딩, 가벼운 AI 옵션 API 경로를 추가했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.services/api.py src/model/struct/services_detail_fast.py src/model/struct/services_runtime.py src/model/struct/service_nginx_certificates.py` 통과.
- `git diff --check` 통과.
- `wiz_project_build(projectName="main", clean=false)` 통과.
- 인증된 Playwright 브라우저 테스트에서 `/services` 초기 호출은 `load` 311ms, `detail_service` 69ms, 1초 이상 API 0건으로 확인했다.
- 같은 세션에서 직접 호출한 `detail_service` 60ms, `detail_service_extras` 72ms, `ai_model_options` 90ms를 확인했다.

## 남은 리스크

- fast path는 인증서 파일의 실제 openssl 분석과 작업 로그를 초기 상세 응답에서 제외하므로, 해당 정보는 관련 탭/액션에서 지연 로딩된다.
