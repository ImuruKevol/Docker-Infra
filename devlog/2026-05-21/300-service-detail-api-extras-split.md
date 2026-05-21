# 300. 서비스 상세 느린 부가 정보 API 분리

## 요청

- 리뷰 ID: `ilynrvzpxhohddzosaprvxqjvnwvrnti`
- 제목: 서비스 관리 화면 API 최적화
- 원 요청: 서비스 관리 화면에서 서비스 목록은 바로 뜨지만 서비스 상세 표시가 느리므로, 오래 걸리는 부분을 찾아 별도 API 분리 등으로 최적화해 달라는 요청.

## 변경 파일

- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/model/struct/services_runtime.py`
- `src/model/struct/service_nginx_certificates.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-21/300-service-detail-api-extras-split.md`

## 변경 내용

- 서비스 선택 직후 호출되는 `detail_service`의 `lightweight` 응답에서 백업 시스템 상태 조회를 제외했다.
- 인증서 상태와 백업 시스템 상태를 `detail_service_extras` API로 분리하고, 첫 상세 렌더 이후 프론트에서 조용히 병합하도록 변경했다.
- 실행 상태 새로고침과 처리 완료 후 overview 재조회도 경량 상세 응답을 사용하도록 조정했다.
- 무료 SSL 인증서 대상이 없을 때도 `certbot.renewal.status` 외부 명령을 먼저 실행하던 흐름을 수정해, 표시할 인증서 row가 있을 때만 갱신 상태를 확인하도록 했다.
- 상세 API 분리 계약을 정적 테스트에 추가했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_detail_splits_slow_extras_from_initial_overview` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.services/api.py src/model/struct/services_runtime.py src/model/struct/service_nginx_certificates.py` 통과.
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `https://infra-dev.nanoha.kr/services`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣고 Playwright 접근을 시도했으나 인증 세션이 없어 `/access`로 리다이렉트되어 실제 서비스 상세 API 호출까지는 확인하지 못했다.

## 남은 리스크

- 인증된 운영 세션에서 실제 서비스 상세 선택 시 `detail_service` 후 `detail_service_extras`가 분리 호출되는지 네트워크 타이밍 확인이 필요하다.
