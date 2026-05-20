# 278. 템플릿 관리 상세 로딩 캐시와 README 중심 입력 흐름 적용

## 요청

> 이미지 관리 쪽에서 서버 전환시 화면 초기화 후 로드 및 캐싱 처리에 대한 부분을 참고해서 템플릿 관리 화면도 똑같이 적용해줘.
> 대표 이미지 부분은 삭제해줘. 그리고 분류는 태그 형식으로 변경해서 입력 후 엔터, 입력 후 엔터 식으로 UI/UX를 수정해줘.
> 그리고 기본적으로 README를 제일 첫번째 탭으로 이동해줘. 이에 따라 README가 있는데 굳이 설명에 대한 부분은 필요가 없으므로 설명은 삭제해줘. 대신 README는 필수적으로 서비스 생성 화면에 노출되도록 해줘.

## 변경 파일

- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/model/struct/templates.py`
- `src/model/struct/templates_seed.py`
- `docs/compose-template-standard.md`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-20/278-template-management-readme-tags-cache.md`

## 변경 내용

- 템플릿 상세 선택 시 기존 화면을 초기화하고 상세 로딩 상태를 먼저 표시한 뒤 데이터를 반영하도록 변경했다.
- 이미지 관리의 로컬 상세 캐시 방식처럼 템플릿 상세 캐시와 request id guard를 추가해 빠른 전환 시 오래된 응답이 화면을 덮어쓰지 않게 했다.
- 대표 이미지와 템플릿 설명 입력을 제거하고, 분류는 Enter로 추가하는 tag chip 입력 UI로 변경했다.
- README 탭을 첫 번째 기본 탭으로 이동하고, README가 비어 있으면 저장이 막히도록 검증을 추가했다.
- 서비스 생성 화면에서 선택한 템플릿 README를 변수 입력 영역 상단에 항상 노출하도록 추가했다.
- 템플릿 metadata 표준을 `tags` 배열 중심으로 정리하고, 기존 `category`/`primary_image`는 읽기 호환만 유지했다.

## 확인

- `python -m py_compile src/model/struct/templates.py src/model/struct/templates_seed.py src/app/page.templates/api.py src/app/page.services.create/api.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`
- `systemctl restart wiz.docker-infra.service`
- Playwright 브라우저 검증:
  - 로컬 `/templates`에서 README 기본 탭, 대표 이미지/설명 제거, 태그 Enter 입력 확인
  - 로컬 `/services/create?template_id=wiz_framework_dev`에서 README 노출 확인
  - 실제 도메인 `/templates`에서 동일 UI 상태 확인
  - console error/page error 없음 확인

## 남은 리스크

- 기존에 저장된 템플릿 파일의 `template.json`에 `category`/`primary_image`가 남아 있어도 화면/API 응답에서는 `tags` 기준으로 정규화하지만, 실제 파일은 다음 저장 시 정리된다.
