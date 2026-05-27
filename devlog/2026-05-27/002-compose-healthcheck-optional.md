# Compose healthcheck 필수 검증 제거

- **ID**: 002
- **날짜**: 2026-05-27
- **유형**: 버그 수정

## 작업 요약

Compose 검증기에서 서비스별 healthcheck 누락을 오류/경고로 처리하던 `HEALTHCHECK_REQUIRED` 검증을 제거했습니다.
서비스 생성/템플릿/AI 보조 경로의 warning allowlist와 안내 문구에서도 healthcheck 필수 표현을 정리해, healthcheck는 권장 사항이지만 저장/다시 적용의 필수 조건이 아니도록 맞췄습니다.

## 원문 요청사항

```text
- services.app.healthcheck: Compose healthcheck 또는 서비스 health check가 필요합니다.
다시 적용 시 이런 에러가 뜨는데, healthcheck가 필수가 아니도록 수정해줘.
```

## 변경 파일 목록

- `src/model/struct/compose_validator.py`: `HEALTHCHECK_REQUIRED` 검증 제거.
- `src/model/struct/services.py`: Compose import warning code 목록에서 healthcheck 제거.
- `src/model/struct/services_compose.py`: conflict check warning code 목록에서 healthcheck 제거.
- `src/model/struct/services_wizard.py`: manual/import/template draft 검증 warning code 목록에서 healthcheck 제거.
- `src/model/struct/templates.py`: 템플릿 preview 검증 warning code 목록에서 healthcheck 제거.
- `src/model/struct/ai_assistant.py`, `src/model/struct/template_ai.py`: Compose 계약에서 healthcheck 필수 문구를 권장 문구로 변경.
- `src/app/page.templates/view.ts`: 템플릿 검증 안내의 “필수 healthcheck” 문구를 완화.
- `tests/api/test_compose_validator.py`: healthcheck 없는 Compose가 검증 통과하는 회귀 테스트 추가.
- `tests/api/test_services_preflight.py`: 예외 shape 테스트 fixture에서 제거된 healthcheck 오류 코드를 일반 Compose 오류 코드로 변경.
- `devlog.md`, `devlog/2026-05-27/002-compose-healthcheck-optional.md`: 작업 이력 기록.

## 검증 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_compose_validator.ComposeValidateStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_services_api_handles_reloaded_service_error_shapes` 성공.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `wiz service restart docker-infra`로 실행 번들 반영.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키와 검증 세션으로 `otp_d04ea9`의 현재 Compose 원문을 `/api/compose/validate`에 전달했을 때 payload code `200`, `valid: true`, `warnings: []` 확인.

## 남은 리스크

- healthcheck가 선택 사항이 되면서 Docker/Swarm 런타임의 상태 관찰 신뢰도는 서비스별 Compose 품질에 더 의존합니다.
- 실제 Docker stack 재배포는 운영 상태 변경을 수반하므로 이번 검증에서는 Compose validation 경로까지만 확인했습니다.
