# 075. 서비스 배포 후 nginx server block 자동 적용과 rollback 연결

## 사용자 요청

서비스 관리 화면의 남은 작업을 이어서 진행한다. 서비스 생성과 배포에서 백그라운드 자동 확인과 실제 적용 흐름을 계속 보강한다.

## 변경 사항

- `service_domains` row를 기준으로 nginx server block을 생성하는 `service_nginx` 모델을 추가했다.
- 도메인별 설정 파일을 Ubuntu 24.04 기본 nginx 경로인 `/etc/nginx/sites-available`과 `/etc/nginx/sites-enabled` 기준으로 생성/연결하도록 했다.
- 업로드된 유효 SSL 인증서가 있으면 HTTPS server block과 HTTP→HTTPS redirect를 생성하고, 없으면 HTTP proxy server block을 생성하도록 했다.
- nginx 설정 적용 전 기존 설정 파일과 enabled link 상태를 snapshot으로 보관하고, `nginx -t` 또는 reload 실패 시 이전 상태로 복원하도록 했다.
- 서비스 배포 성공 후 stack deploy 결과에 이어 nginx 설정 적용, configtest, reload 결과를 operation output에 기록하도록 연결했다.
- reload 명령이 allowlist에 걸리지 않도록 `proxy.nginx.reload`를 기본 local executor allowlist에 추가했다.
- 서비스 상세의 연결 도메인 영역에서 nginx 적용 여부를 `nginx 적용됨` 또는 `nginx 적용 대기`로 표시하도록 했다.
- TODO 문서에서 nginx server block 자동 생성과 reload 실패 복구 항목을 완료로 갱신했다.
- 정적 테스트에 `service_nginx` 연결, nginx reload allowlist, rollback 관련 계약을 추가했다.

## 변경 파일

- `config/docker_infra.py`
- `devlog.md`
- `devlog/2026-05-09/075-service-nginx-apply-rollback.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/model/struct.py`
- `src/model/struct/service_nginx.py`
- `src/model/struct/services_deploy.py`
- `src/model/struct/services_wizard.py`
- `tests/api/test_services_preflight.py`

## 검증

- `python -m py_compile src/model/struct/service_nginx.py src/model/struct/services_deploy.py src/model/struct/services_wizard.py src/model/struct/services_preflight.py src/model/struct/services_ports.py src/model/struct/services.py src/model/struct.py config/docker_infra.py`
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract.WizStructureContractTest`
- `wiz_project_build(clean=false, projectName="main")`
- `git diff --check`

## 비고

- 실제 nginx reload는 운영 nginx 설정 파일을 수정하는 배포 시점 동작이므로 이번 검증에서는 직접 실행하지 않았다.
- 인증서가 없는 도메인에 대한 certbot 자동 발급과 certbot output operation log 연결은 다음 작업으로 남겨둔다.
