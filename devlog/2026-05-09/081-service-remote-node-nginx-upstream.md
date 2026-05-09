# 081. 원격 노드 배치 서비스의 nginx upstream 적용

## 사용자 요청

공개 포트가 있는 서비스도 서버 정보에서 IP를 가져와 nginx 설정을 바꾸면 되므로, 서비스 관리 관련 남은 작업을 이어서 진행해달라고 요청함.

## 변경 사항

- 공개 포트 서비스의 local master 강제 배치 보정을 제거하고, 배포 후 실제 Swarm task가 배치된 노드를 기준으로 nginx upstream을 계산하도록 변경함.
- `docker stack ps`, `docker node ls`, `docker node inspect` 결과와 `nodes` 테이블의 `swarm_node_id/host`를 매칭해 `service_domains.metadata.proxy_host`를 저장함.
- 등록된 서버 row가 있으면 해당 서버의 host를 우선 사용하고, 아직 등록되지 않은 Swarm 노드는 `docker node inspect`의 `Status.Addr`를 fallback으로 사용함.
- nginx server block의 `proxy_pass`를 `127.0.0.1:{port}` 고정에서 `{proxy_host}:{published_port}` 기반으로 변경함.
- 서비스 상세 실행 상태 영역에 도메인별 nginx proxy 대상 서버와 포트를 표시함.
- TODO 문서에서 공개 port 서비스의 처리 기준을 local master 강제 배치에서 실제 배치 노드 IP 기반 upstream으로 정정함.

## 변경 파일

- `src/model/struct/local_command_catalog.py`
- `src/model/struct/services_deploy.py`
- `src/model/struct/services_deploy_targets.py`
- `src/model/struct/service_nginx.py`
- `src/model/struct/services_status.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `tests/api/test_services_preflight.py`

## 검증

- `python -m py_compile`로 변경 Python 파일 문법 확인.
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest`
- `PYTHONPATH=. python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_wiz_structure_contract.WizStructureContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(clean=false, projectName="main")`
- `DOCKER_INFRA_SSL_SELF_SIGNED_TEST=true` 별도 WIZ 테스트 서버에서 mini3 원격 노드 강제 배치 서비스 생성, Docker stack 배포, OpenSSL 자체 인증서 발급, nginx HTTPS 응답 확인, 이미지 버전 변경 후 재배포, rollback plan, rollback, 재배포까지 확인.
- 테스트 결과 nginx proxy host가 mini3의 Swarm IP로 설정되고 HTTPS 응답이 정상임을 확인함.
- 테스트 stack, nginx site config, 자체 인증서 디렉토리, 테스트 DB row, 임시 WIZ 테스트 서버를 정리함.
