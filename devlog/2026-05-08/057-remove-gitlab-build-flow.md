# 057. GitLab 연동과 build→Harbor push 흐름 제거, 이미지 전용 운영 구조로 정리

- 일시: 2026-05-08

## 작업 요약

Docker Infra에서 GitLab 연동 설정, GitLab CE seed 템플릿, `image_builds` 기반 빌드 이력 카탈로그를 제거하고, 서비스가 이미 만들어진 이미지와 Compose만 관리하도록 구조를 정리했다. 기존 설치 DB에는 `007` migration으로 GitLab/build 관련 테이블을 제거했다.

현재 실행 중인 daemon은 Python module cache 때문에 old `integrations` 모델을 계속 잡고 있어서, 서버 재시작 없이 `/system` 화면이 깨지지 않도록 runtime compatibility shim을 최소 범위로 적용했다. 대신 실제 화면과 dashboard에서는 GitLab 항목을 노출하지 않도록 걸러냈다.

## 원문 요청사항

```text
일단 이 Docker Infra에서 깃랩 연동 관련 부분은 전부 제거해줘.
그리고 깃랩에서 가져와서 빌드 후 harbor로 푸시를 한다는 플로우 자체를 제거해줘.
이 Docker Infra 서비스에서는 오로지 이미 만들어져있는 이미지들에 대한 관리만 담당하려고 해.
그리고 나중에는 Harbor도 화면에서는 아예 빼버리고 Docker Infra를 통해 운영 중인 서비스들에 대한 백업 버전 관리용으로만 사용해서 버전 관리용으로만 사용하고 웹 서비스 화면에서는 아예 빼버릴거야.
```

## 변경 파일

### 코드

- `src/model/struct/integrations.py`
- `src/model/struct/integrations_registry.py`
- `src/model/struct/infra_catalog.py`
- `src/model/struct/infra_catalog_registry.py`
- `src/model/struct/images_harbor.py`
- `src/model/struct/templates.py`
- `src/model/struct/templates_seed.py`
- `src/model/struct/templates_store.py`
- `src/model/struct.py`
- `src/app/page.system/api.py`
- `src/app/page.system/view.ts`
- `src/app/page.dashboard/api.py`
- `src/app/page.dashboard/view.ts`
- `src/app/page.services/api.py`
- `src/app/page.tools/api.py`

### DB / 테스트

- `src/model/db/migrations/007_remove_gitlab_build_flow.sql`
- `src/model/db/migrations/007_remove_gitlab_build_flow.down.sql`
- `tests/api/test_images_templates_catalog.py`

### 문서

- `README.md`
- `docs/docker-infra-design.md`
- `docs/docker-infra-runtime.md`
- `docs/docker-infra-development-todo.md`
- `devlog.md`

## 검증

- `wiz_project_build(projectName="main", clean=false)` 통과
- `wiz_project_build(projectName="main", clean=true)` 통과
- `python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest` 통과
- `git diff --check` 통과
- live smoke
  - DB migration `007` 적용 확인
  - `/wiz/api/page.templates/load`에서 `gitlab_ce` 템플릿 미노출 확인
  - `/wiz/api/page.dashboard/overview`에서 `gitlab` integration 미노출 확인
  - `/wiz/api/page.system/load` HTTP `200` 확인
