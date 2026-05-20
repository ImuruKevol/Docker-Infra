# 280. 템플릿 AI MCP/표준/허용 범위 명시

## 요청

> 템플릿 관리 화면의 AI에서는 서비스 관리 쪽의 AI와 조금 다른 느낌으로 정리가 되어야 할 것 같은데, 제대로 반영이 된지는 모르겠어. MCP, 템플릿의 표준 규격, AI에 대한 허용 범위 등을 상세하게 확인하고 정의해야해.

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `src/model/struct/ai_assistant.py`
- `src/app/page.templates/api.py`
- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `docs/compose-template-standard.md`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-20/280-template-ai-policy-scope.md`

## 변경 내용

- Codex MCP scope에 `compose_template`을 추가하고 허용 도구를 `infra_context`, `docker_search`, `docker_image_check`로 제한했다.
- 템플릿 AI contract에 `template_ai_policy`를 추가해 MCP 허용/차단 도구군, 템플릿 필수 파일, placeholder/schema 규칙, 저장/배포/런타임 조치 차단 범위를 구조화했다.
- 템플릿 AI system prompt와 repair context에 템플릿 전용 scope를 반영해 서비스 생성/수정/점검 AI와 분리했다.
- 템플릿 관리 API에 `ai_contract` endpoint를 추가하고, 화면에 AI 허용 범위와 템플릿 표준 요약을 노출했다.
- Compose 템플릿 표준 문서와 정적 계약 테스트에 MCP contract와 AI permission scope를 반영했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/model/struct/templates.py src/model/struct/templates_seed.py src/app/page.templates/api.py src/app/page.services.create/api.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`
- `systemctl restart wiz.docker-infra.service`
- `GET http://127.0.0.1:3001/api/system/health`
- Playwright 브라우저 검증:
  - 로컬 `/templates`에서 AI 허용 범위, 템플릿 표준, 허용 MCP 도구, 런타임 조치 차단, 사용자 검토 후 저장 문구 확인
  - 실제 도메인 `/templates`에서 동일 항목 확인
  - page error 없음 확인

## 남은 리스크

- 실제 AI 생성 호출은 실행 비용과 시간이 큰 작업이라 이번 검증에서는 수행하지 않았다. 실모델이 새 policy를 얼마나 잘 따르는지는 운영 모델별 추가 샘플링이 필요하다.
