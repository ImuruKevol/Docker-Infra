# 070. 새 서비스 생성을 독립 화면으로 전환하고 운영자 입력 항목을 자동화

## 사용자 요청

새 서비스 생성을 모달이 아니라 별도의 화면으로 만들고, 서비스 ID와 컨테이너 이름처럼 운영자가 알 필요 없는 값은 제거한다. 이미지 존재 확인은 로컬 이미지 저장소 후 Docker Hub 순서로 지원하고, 배포 전 포트 충돌은 자동으로 다음 가용 port를 선택해야 한다. 환경변수와 볼륨은 고급 설정으로 숨기고, 템플릿은 1단계 선택 후 잠금 처리한다. 도메인은 등록된 도메인 사용 또는 미사용만 제공하고, SSL은 업로드 인증서가 있으면 자동 사용, 없으면 certbot 자동 발급으로 처리한다. 서버 직접 선택은 제거하고, Compose 템플릿에 여러 service가 포함될 수 있음을 반영한다.

## 변경 사항

- `/services/create` 독립 페이지를 추가하고 서비스 목록의 새 서비스 진입 버튼을 해당 화면으로 연결했다.
- 서비스 목록에 남아 있던 기존 생성 모달 템플릿은 렌더링되지 않도록 비활성화했다.
- 서비스 ID, namespace, 내부 service key, container name 입력을 새 생성 흐름에서 제거하고, 백엔드에서 중복 확인 후 자동 생성하도록 했다.
- Compose 템플릿의 여러 service를 구성 단위로 파싱해 각 구성의 이미지 이름, tag, 내부 port를 입력할 수 있게 했다.
- 템플릿은 1단계 이후 되돌아가도 변경할 수 없도록 잠금 처리했다.
- 환경변수와 볼륨 입력은 고급 설정 토글 안으로 이동했다.
- 이미지 확인 API를 추가해 로컬 `docker image inspect` 후 Docker Hub registry manifest 확인 순서로 동작하게 했다.
- 등록된 도메인 사용 또는 도메인 미사용만 선택하게 하고, 업로드 인증서/자동 certbot 판단은 백엔드에서 처리하도록 했다.
- 직접 서버 선택 UI를 제거하고 자동 배치 흐름으로 맞췄다.
- `docker stack deploy` 직전에 Compose published port를 검사하고, 이미 사용 중이거나 같은 Compose 안에서 중복되는 port는 다음 가용 port로 자동 조정하도록 했다.
- 서비스 생성 결과의 wizard 입력값을 서비스 metadata에 저장해 이후 수정 wizard와 상세 화면에서 활용할 수 있게 했다.
- 전체 TODO와 남은 TODO 문서를 새 생성 화면/도메인/SSL 흐름 기준으로 갱신했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-08/070-service-create-page-operator-flow.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.services/view.pug`
- `src/app/page.services.create/app.json`
- `src/app/page.services.create/api.py`
- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `src/model/struct.py`
- `src/model/struct/services.py`
- `src/model/struct/services_deploy.py`
- `src/model/struct/services_ports.py`
- `src/model/struct/services_wizard.py`

## 검증

- `python -m py_compile src/app/page.services.create/api.py src/model/struct/services_wizard.py src/model/struct/services_ports.py src/model/struct/services_deploy.py src/model/struct/services.py src/model/struct.py`
- `wiz_project_build(clean=false, projectName="main")`
- `PYTHONPATH=. python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract`
- `git diff --check`

실제 `docker stack deploy`, Docker Hub 네트워크 확인, certbot 실행은 운영 대상에 영향을 줄 수 있어 자동 검증에서는 실행하지 않았다.
