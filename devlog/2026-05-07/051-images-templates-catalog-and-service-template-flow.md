# 051. 이미지/템플릿 관리 화면 완성과 기본 템플릿 seed, 서비스 생성 템플릿 연동 적용

- 일시: 2026-05-07
- 사용자 요청:
  - "이제 이미지 관리 화면과 템플릿 관리 화면을 완성해야해. 이미지 관리는 harbor API를 통해 harbor에 등록된 project, project별 이미지들, 태그 목록 등을 가져올 수 있어야 해. 그리고 각 서버의 로컬 저장소에 있는 이미지들도 조회를 하고 관리를 할 수 있어야 해. 로컬 저장소나 harbor 둘다 이미지를 삭제할 수 있어야 해. 템플릿 관리 화면은 기본적인 monaco editor를 이용한 docker compose 템플릿 수정 등 관리 기능을 제공해야해. 근데 지금은 아무런 템플릿이 등록되어있지 않으니 자주 사용하는 이미지들을 알아서 찾아서 등록해줘. DB, WAS, Service 등등. compose 템플릿은 서비스 생성 시 서비스와 잘 호환이 되는 형태로 관리가 되어야 해."

## 처리 내용

1. 이미지 관리 화면을 Harbor/로컬 서버 2개 탭 구조로 재구성했다.
2. Harbor API 연동 모델을 추가해 project 목록, repository 목록, artifact/tag 목록을 조회하고 digest 기준 삭제를 지원했다.
3. 각 서버의 로컬 Docker image 목록 조회와 로컬 이미지 삭제를 지원하도록 local executor/SSH 경로를 연결했다.
4. 템플릿 저장소 모델을 추가하고 Monaco 기반 템플릿 편집 화면에서 Compose, 기본값, schema, README, 렌더 미리보기를 관리할 수 있게 했다.
5. 템플릿이 비어 있는 경우 기본 seed 템플릿 7종을 자동 등록하도록 추가했다.
   - Nginx 정적 웹
   - Node.js API
   - Spring Boot API
   - PostgreSQL DB
   - MariaDB DB
   - Redis Cache
   - RabbitMQ Queue
6. 서비스 생성 화면에서 템플릿을 검색형 select로 선택하고, 템플릿 기본값으로 Compose 초안을 채운 뒤 저장할 수 있게 연결했다.
7. 템플릿 미리보기는 저장 전에도 현재 편집 중인 Compose/기본값으로 다시 렌더하도록 preview API를 추가했다.
8. 이미지/템플릿 live smoke 및 서비스 화면 E2E를 추가/보강했다.

## 변경 파일

- 설정/모델
  - `config/docker_infra.py`
  - `src/model/struct.py`
  - `src/model/struct/local_command_catalog.py`
  - `src/model/struct/images.py`
  - `src/model/struct/images_harbor.py`
  - `src/model/struct/images_shared.py`
  - `src/model/struct/templates.py`
  - `src/model/struct/templates_seed.py`
  - `src/model/struct/templates_shared.py`
  - `src/model/struct/templates_store.py`
- 이미지 화면
  - `src/app/page.images/api.py`
  - `src/app/page.images/view.ts`
  - `src/app/page.images/view.pug`
- 템플릿 화면
  - `src/app/page.templates/api.py`
  - `src/app/page.templates/view.ts`
  - `src/app/page.templates/view.pug`
- 서비스 화면 연동
  - `src/app/page.services/api.py`
  - `src/app/page.services/view.ts`
  - `src/app/page.services/view.pug`
- 테스트
  - `tests/api/test_images_templates_catalog.py`
  - `tests/e2e/specs/services.spec.ts`

## 검증

- `wiz_project_build(projectName="main", clean=false)` 통과
- `python -m compileall /root/docker-infra/project/main/src/model /root/docker-infra/project/main/src/app /root/docker-infra/project/main/tests/api` 통과
- `python -m unittest tests.api.test_wiz_structure_contract tests.api.test_compose_validator tests.api.test_images_templates_catalog` 통과
- `DOCKER_INFRA_TEST_PASSWORD='____' python -m unittest tests.api.test_images_templates_catalog` live 통과
- `DOCKER_INFRA_TEST_PASSWORD='____' DOCKER_INFRA_BASE_URL='http://127.0.0.1:3001' npx playwright test tests/e2e/specs/services.spec.ts` 통과
- live API 확인
  - `/wiz/api/page.templates/load` -> `200`, seed 템플릿 `7`개 확인
  - `/wiz/api/page.images/load` -> `200`, 등록 서버 `2`대 확인
  - `/wiz/api/page.images/harbor_detail` -> `200`, 첫 Harbor 프로젝트 `keycloud` 조회 확인
  - `/wiz/api/page.images/local_detail` -> `200`, 선택 서버 로컬 이미지 `6`개 확인
