# Compose 템플릿 seed 파일 직렬화 오류 수정과 브라우저 검증

- **날짜**: 2026-05-20
- **ID**: 276
- **유형**: 버그 수정
- **요청 원문**: `화면에 data must be str, not dict 에러가 뜨고 있어. 비밀번호는 "-----"니까 가능하면 브라우저 환경에서 직접 테스트해줘.`

## 변경 사항

1. 템플릿 seed의 `values.schema.json` 값이 dict인 상태로 `Path.write_text()`에 전달되어 `data must be str, not dict`가 발생하던 문제를 수정했다.
2. 템플릿 파일 저장 공통 변환 함수 `_file_text()`를 추가해 dict/list는 JSON 문자열로, 그 외 값은 문자열로 저장하게 했다.
3. seed 기본값 생성과 템플릿 저장 경로 모두 같은 변환 함수를 사용하도록 정리했다.
4. 로컬 WIZ 서비스를 재시작해 cached model 상태를 갱신한 뒤 실제 브라우저 흐름을 확인했다.

## 변경 파일

- `src/model/struct/templates.py`
- `devlog.md`
- `devlog/2026-05-20/276-compose-template-seed-serialization-fix.md`

## 검증

- `python -m py_compile src/model/struct/templates.py src/model/struct/templates_seed.py src/app/page.templates/api.py src/app/page.services.create/api.py`
- `wiz_project_build(projectName="main", clean=false)` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest` 성공
- 인증 후 `/wiz/api/page.templates/load` HTTP 200 / `code=200` 확인
- 인증 후 `/wiz/api/page.services.create/load` HTTP 200 / `code=200` 확인
- Playwright Chromium:
  - `/templates` 진입 후 `data must be str` 미노출 확인
  - `/services/create?template_id=wiz_framework_dev`에서 서비스 이름 입력 후 `템플릿 적용` 성공 확인
  - page error와 console error 없음

## 남은 리스크

- 브라우저 검증은 템플릿 초안 적용까지 확인했고, 실제 서비스 저장/배포까지는 실행하지 않았다.
