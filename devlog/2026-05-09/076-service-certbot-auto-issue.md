# 076. 인증서 없는 서비스 도메인에 certbot 자동 발급 흐름 연결

## 사용자 요청

서비스 관리 화면의 남은 작업을 이어서 진행한다.

## 변경 사항

- 서비스 도메인에 업로드된 유효 인증서가 없고 `ssl_mode`가 `certbot`이면 배포 과정에서 certbot 무료 인증서를 자동 발급하도록 연결했다.
- certbot 실행은 nginx HTTP server block을 먼저 적용/reload한 뒤 `certbot certonly --nginx`로 실행하고, 발급 성공 후 Let's Encrypt 인증서를 감지해 HTTPS server block을 다시 생성하는 2단계 흐름으로 구성했다.
- `/etc/letsencrypt/live/{domain}/fullchain.pem`, `privkey.pem` 인증서를 자동 감지하고 기존 인증서 분석 로직으로 유효성을 확인하도록 했다.
- certbot 실행 결과를 서비스 배포 operation output에 남기도록 했다.
- certbot 명령을 local executor allowlist에 추가하고, `config.env`에 certbot email/staging 환경변수 키를 추가했다.
- nginx 적용 실패 시 기존 rollback 경로가 certbot 이후 재적용 단계에도 동작하도록 유지했다.
- TODO 문서에서 certbot 자동 발급과 certbot output operation log 항목을 완료로 갱신했다.
- 정적 테스트에 certbot command, allowlist, Let's Encrypt 인증서 감지 계약을 추가했다.

## 변경 파일

- `/root/docker-infra/config.env`
- `config/docker_infra.py`
- `devlog.md`
- `devlog/2026-05-09/076-service-certbot-auto-issue.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/service_nginx.py`
- `tests/api/test_services_preflight.py`

## 검증

- `python -m py_compile src/model/struct/service_nginx.py src/model/struct/local_command_catalog.py src/model/struct/services_deploy.py src/model/struct/services_wizard.py src/model/struct/services_preflight.py src/model/struct.py config/docker_infra.py`
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_wiz_structure_contract.WizStructureContractTest`
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract.WizStructureContractTest`
- `wiz_project_build(clean=false, projectName="main")`
- `git diff --check`

## 비고

- 실제 certbot 실행은 외부 DNS, 80/443 포트, 운영 nginx 설정 파일을 건드리는 배포 시점 작업이라 이번 검증에서는 직접 실행하지 않았다.
