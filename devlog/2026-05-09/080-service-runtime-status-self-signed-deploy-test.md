# 080. 서비스 배포 런타임 상태와 자체 인증서 실배포 테스트

## 사용자 요청

이어서 진행하고, 실제 docker 배포 및 롤백 동작 확인 테스트는 SSL 적용 부분만 openssl 명령어를 통한 자체 인증서를 사용하는 로직으로 대체해서 서비스 배포 흐름 전체를 테스트해달라고 요청함.

## 변경 사항

- 서비스 배포 성공 후 stack service/task, 컨테이너, 도메인/nginx/SSL 상태를 다시 수집해 `services.metadata.runtime_status`에 저장하고 서비스 상세 화면에서 확인할 수 있게 함.
- 테스트 환경에서 `DOCKER_INFRA_SSL_SELF_SIGNED_TEST=true`를 주입하면 certbot 대신 `openssl req -x509`로 자체 인증서를 발급하고 nginx SSL server block에 적용하도록 분리함.
- 자체 인증서처럼 만료 임박 상태로 분석되는 인증서도 실제 만료 전이면 nginx 적용 가능한 인증서로 인정하도록 수정함.
- 공개 포트가 있는 서비스는 host nginx가 접근 가능한 local master 노드에 자동 배치되도록 deploy 직전에 placement constraint를 보정함.
- 서비스 생성 wizard와 기본 Compose 생성 경로에서 공개 포트를 `mode: host` long syntax로 생성하도록 변경함.
- 서비스 생성 preflight의 create/update SQL에서 `None` service_id 파라미터가 PostgreSQL 타입 추론 오류를 만들던 경로를 create/update 쿼리로 분리함.
- TODO 문서에 배포 후 런타임 상태 확인과 실제 배포/롤백 검증 완료 항목을 반영함.

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/local_command_scripts.py`
- `src/model/struct/service_nginx.py`
- `src/model/struct/service_nginx_certificates.py`
- `src/model/struct/services.py`
- `src/model/struct/services_compose.py`
- `src/model/struct/services_deploy.py`
- `src/model/struct/services_preflight.py`
- `src/model/struct/services_runtime.py`
- `src/model/struct/services_status.py`
- `src/model/struct/services_wizard.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `tests/api/test_services_preflight.py`

## 검증

- `python -m py_compile`로 변경된 서비스 배포/인증서/Compose 관련 Python 파일 문법 확인.
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest`
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_wiz_structure_contract.WizStructureContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(clean=false, projectName="main")`
- `DOCKER_INFRA_SSL_SELF_SIGNED_TEST=true`가 주입된 별도 WIZ 테스트 서버에서 `nginx:1.29.5` 서비스 생성, Docker stack 배포, OpenSSL 자체 인증서 발급, nginx HTTPS 응답 확인, `nginx:1.29.4` 업데이트 배포, rollback plan, rollback, 재배포까지 확인.
- 테스트 리소스는 stack, nginx site config, 자체 인증서 디렉토리, 테스트 DB row 기준으로 정리함.
