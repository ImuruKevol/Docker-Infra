# Compose/Nginx 탭 서비스 예외 응답 보강

- **ID**: 001
- **날짜**: 2026-05-27
- **유형**: 버그 수정

## 작업 요약

서비스 상세 Compose/Nginx 탭의 Compose 저장, nginx 저장, 다시 적용 API에서 WIZ 모델 재로딩으로 예외 클래스 객체가 달라져도 `status_code`, `message`, `error_code` 형태의 서비스 예외를 구조화 응답으로 반환하도록 보강했습니다.
`otp` 서비스의 Compose 검증 실패가 HTTP 500으로 터지던 문제를 재현했고, 수정 후 검증 실패 상세가 정상 payload로 내려오는 것을 확인했습니다.

## 원문 요청사항

```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: oroskgfeujlwvrqtgxkxsmxfjahyzzqp
- 제목: Compose/Nginx 탭 오류
- 요청 링크: https://infra-dev.nanoha.kr/services
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra

## 리뷰어 요청 내용

서비스 관리 - Compose/Nginx 탭에서 검사후 저장 / 다시 적용 기능이 전부 에러가 뜨고 있어.
"otp" 서비스가 해당 상태니까 확인해줘.
```

## 변경 파일 목록

- `src/app/page.services/api.py`
  - 서비스 예외 형태를 클래스 동일성이 아니라 속성 기반으로 감지하는 fallback 응답 변환을 추가.
  - `deploy_service`, `save_nginx_config`, `save_compose_content`에서 재로딩된 모델 예외도 500이 아닌 구조화 payload로 반환하도록 보강.
- `tests/api/test_services_preflight.py`
  - 재로딩된 Compose validation 예외 shape가 details/warning/can_continue를 유지해 응답되는지 검증하는 회귀 테스트 추가.
- `devlog.md`, `devlog/2026-05-27/001-compose-nginx-service-error-response.md`
  - 작업 이력 기록.

## 검증 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_services_api_handles_reloaded_service_error_shapes` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_p7_nginx_and_domain_certificate_contract_is_wired` 성공.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `wiz service restart docker-infra`로 실행 번들 반영.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키와 검증 세션으로 로컬 API 확인:
  - `save_compose_content`는 HTTP 200 wrapper, payload code `400`, `COMPOSE_VALIDATION_FAILED`, details 1건 반환.
  - `save_nginx_config`의 없는 domain_id 요청은 HTTP 200 wrapper, payload code `404`, `SERVICE_DOMAIN_NOT_FOUND` 반환.
  - `deploy_service`의 service_id 누락 요청은 HTTP 200 wrapper, payload code `400`, `SERVICE_ID_REQUIRED` 반환.

## 남은 리스크

- `otp` 서비스의 현재 Compose 원문은 app 서비스 healthcheck 누락으로 검증 자체는 실패합니다. 이번 수정은 해당 검증 실패가 HTTP 500이 아니라 사용자에게 설명 가능한 payload로 전달되도록 한 것입니다.
- 실제 nginx 설정 파일 저장과 Docker stack 재배포는 운영 상태 변경을 수반하므로 검증에서는 오류 경로만 확인했습니다.
