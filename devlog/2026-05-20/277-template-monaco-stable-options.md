# 277. Compose 템플릿 Monaco editor 재렌더링 방지

## 요청

> monaco editor쪽에 문제가 있어. 모나코 에디터가 계속해서 렌더링이 다시 되고 있는 것 같아. 클릭하면 포커스가 바로 풀리고, 스크롤 후 클릭하면 스크롤이 맨 위로 가면서 포커스가 풀리고 있어.

## 변경 파일

- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-20/277-template-monaco-stable-options.md`

## 변경 내용

- Compose 템플릿 화면의 Monaco editor options를 템플릿 렌더마다 새 객체로 만들지 않도록 탭별 고정 객체로 변경했다.
- 탭 전환을 `setActiveTab()`으로 통일해 active tab과 editor option 참조를 함께 갱신하도록 정리했다.
- Pug 템플릿의 `[options]` 바인딩을 메서드 호출 대신 안정적인 `activeEditorOptions` 프로퍼티 참조로 변경했다.
- 정적 계약 테스트가 안정적인 editor options 바인딩을 확인하도록 갱신했다.

## 확인

- `python -m py_compile src/model/struct/templates.py src/model/struct/templates_seed.py src/app/page.templates/api.py src/app/page.services.create/api.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`
- `systemctl restart wiz.docker-infra.service`
- Playwright 브라우저 검증:
  - `http://127.0.0.1:3001/templates`, `https://infra-dev.nanoha.kr/templates` 진입 및 로그인
  - Monaco editor 클릭 후 focus 유지 확인
  - 입력 반영 확인
  - 스크롤 이후 editor 클릭 시 화면 위치와 focus 유지 확인
  - console error/page error 없음 확인

## 남은 리스크

- 실제 사용자가 테마를 화면 진입 후 즉시 전환하는 흐름은 별도 이벤트가 없어 이번 검증 범위에 포함하지 않았다.
