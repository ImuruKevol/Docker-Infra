# 279. 템플릿 관리 AI 초안 생성 흐름 추가

## 요청

> 템플릿 관리 화면에도 서비스 생성/수정/점검과 같은 느낌의 AI 기능을 추가해줘.

## 변경 파일

- `src/app/page.templates/api.py`
- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `src/model/struct/ai_assistant.py`
- `docs/compose-template-standard.md`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-20/279-template-management-ai-draft.md`

## 변경 내용

- 템플릿 관리 화면에 AI 템플릿 초안 카드, 요청 입력, 모델 선택, 진행 요약, warning 표시를 추가했다.
- AI 초안 결과를 저장하지 않고 현재 편집 중인 README, Compose, 기본값, Schema, 태그에 적용해 사용자가 검토 후 저장하도록 구성했다.
- `page.templates` API에 AI 모델 목록 조회와 템플릿 AI 스트림 endpoint를 추가했다.
- `ai_assistant`에 Compose 템플릿 전용 contract, system prompt, output 정규화, README/placeholder/schema/Compose 검증을 추가했다.
- 템플릿 AI 표준을 문서와 정적 계약 테스트에 반영했다.

## 확인

- `python -m py_compile src/model/struct/ai_assistant.py src/model/struct/templates.py src/model/struct/templates_seed.py src/app/page.templates/api.py src/app/page.services.create/api.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`
- `systemctl restart wiz.docker-infra.service`
- Playwright 브라우저 검증:
  - 로컬 `/templates`에서 AI 템플릿 카드, 요청 입력, 모델 선택, 기존 README editor 렌더 확인
  - 실제 도메인 `/templates`에서 AI 템플릿 UI 노출 확인
  - console error/page error 없음 확인

## 남은 리스크

- 실제 AI 호출은 비용과 실행 시간이 큰 작업이라 UI/route/정규화 계약까지만 검증했고, 실모델 생성 결과의 품질은 운영 모델 설정에서 별도 확인이 필요하다.
