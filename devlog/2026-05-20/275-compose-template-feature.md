# 파일 기반 Compose 템플릿 관리와 서비스 생성 템플릿 적용 흐름 추가

- **날짜**: 2026-05-20
- **ID**: 275
- **유형**: 기능 추가
- **요청 원문**: `Compose 템플릿 기능을 만들어줘. 템플릿을 먼저 만들어놓고 각 템플릿마다 추가 입력받아야 할 변수 표준을 정의한 후, 서비스 생성에서는 그 템플릿을 선택한 후 클릭 몇 번만으로 원하는 서비스를 띄울 수 있게. 예: WIZ framework 컨테이너 템플릿은 서비스 이름만 입력하면 개발 환경이 구성되는 느낌.`

## 변경 사항

1. DB 테이블 없이 WIZ data directory의 `templates/{namespace}/`를 사용하는 파일 기반 Compose 템플릿 모델을 추가했다.
2. 템플릿 표준 파일을 `docker-compose.yaml`, `values.default.yaml`, `values.schema.json`, `README.md`, `template.json`으로 고정했다.
3. 비밀번호/토큰류 변수는 비워두거나 `change_me`이면 서비스 초안 적용 시 자동 생성하도록 했다.
4. 기본 seed로 `WIZ Framework 개발환경`, `Wiki.js 문서 사이트`를 추가했다.
5. `/templates` 관리 화면을 복구해 템플릿 메타데이터, Compose, 기본값, schema, README, 렌더 미리보기를 편집할 수 있게 했다.
6. `/services/create` 1단계에 Compose 템플릿 선택과 변수 입력, 템플릿 적용 버튼을 추가했다.
7. 템플릿으로 만든 서비스의 source/draft metadata가 `compose_template`으로 남도록 연결했다.
8. 사이드바와 번역에 Compose 템플릿 메뉴를 추가했다.
9. 기존 템플릿 제거 TODO 문서는 과거 기록으로 표시하고 신규 표준 문서로 연결했다.

## 변경 파일

- `docs/compose-template-standard.md`
- `docs/template-removal-todo.md`
- `src/app/component.nav.sidebar/view.ts`
- `src/app/page.templates/api.py`
- `src/app/page.templates/app.json`
- `src/app/page.templates/view.pug`
- `src/app/page.templates/view.ts`
- `src/app/page.services.create/api.py`
- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `src/app/page.services/view.ts`
- `src/assets/lang/en.json`
- `src/assets/lang/ko.json`
- `src/model/struct.py`
- `src/model/struct/templates.py`
- `src/model/struct/templates_seed.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-20/275-compose-template-feature.md`

## 검증

- `python -m py_compile src/model/struct/templates.py src/model/struct/templates_seed.py src/app/page.templates/api.py src/app/page.services.create/api.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)` 성공
- `curl -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' http://127.0.0.1:3001/templates` HTTP 200 확인

## 남은 리스크

- 로그인 세션 비밀번호가 제공되지 않아 `/wiz/api/page.templates/*` API의 인증 후 live flow는 직접 호출하지 못했다.
- `WIZ Framework 개발환경` seed는 일반 WIZ workspace bootstrap을 목표로 한 기본값이며, 운영 이미지가 별도로 확정되면 템플릿 변수의 기본 이미지를 조정해야 한다.
