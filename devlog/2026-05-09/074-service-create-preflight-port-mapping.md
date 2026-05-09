# 074. 서비스 생성 저장 전 자동 점검과 도메인 포트 매핑 보강

## 사용자 요청

서비스 관리 화면의 남은 작업을 이어서 진행한다. 서비스 생성 시 볼륨, nginx 설정, 컨테이너 이름 등 백그라운드에서 자동 중복 확인과 검증이 필요한 부분이 많으므로 실제로 검증/확인을 하는지도 확인한다.

## 변경 사항

- `/services/create`에 저장 전 자동 점검 API와 화면 영역을 추가했다.
- 자동 점검에서 Compose 검증, 이미지 존재 확인, 컨테이너/Docker service 이름 자동 생성 확인, 볼륨 이름/경로 확인, 공개 포트 충돌 자동 조정 preview, 도메인 중복, nginx 설정 경로, SSL 처리 방식을 확인하도록 했다.
- 저장 시에도 동일한 preflight를 다시 실행해서 차단 항목이 있으면 서비스 생성을 막도록 했다.
- 서비스 생성 wizard가 선택한 도메인 연결 포트의 compose service, 내부 port, 공개 port를 metadata로 저장하도록 했다.
- 배포 직전 공개 port가 자동 조정되면 `service_domains.metadata.published_port`에 반영하도록 했다.
- 서비스 상세 도메인 표시에서 내부 port와 실제 서버 공개 port가 다를 경우 함께 표시하도록 했다.
- 관련 TODO 문서에 완료된 사전 점검과 남은 작업을 반영했다.
- 서비스 생성 자동 점검 계약이 유지되도록 정적 테스트를 추가했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-09/074-service-create-preflight-port-mapping.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.services.create/api.py`
- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/model/struct.py`
- `src/model/struct/services.py`
- `src/model/struct/services_deploy.py`
- `src/model/struct/services_ports.py`
- `src/model/struct/services_preflight.py`
- `src/model/struct/services_wizard.py`
- `tests/api/test_services_preflight.py`

## 검증

- `python -m py_compile src/model/struct/services_preflight.py src/model/struct/services_wizard.py src/model/struct/services_ports.py src/model/struct/services_deploy.py src/model/struct/services.py src/model/struct.py src/app/page.services.create/api.py src/app/page.services/api.py`
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract.WizStructureContractTest`
- `wiz_project_build(clean=false, projectName="main")`
- `git diff --check`
