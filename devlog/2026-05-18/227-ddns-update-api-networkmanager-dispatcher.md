# 227. DDNS update API와 NetworkManager dispatcher 반영

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 아래는 API 예시야. 아래 예시를 반영해줘. IP는 공인 IP를 조회한 후 담아서 보내도록 해야해.
> 그리고 Ubuntu 24.04 기준으로 NetworkManager 디스패처 기능을 이용해 공인 IP 변경 시 바로 API를 호출해서 DDNS가 동작하도록 해야해. 단, DDNS API 호출 시 최소한의 API만 호출하고, 현재 마지막으로 API에 보낸 IP를 기억해서 동일하면 안보내도 되는 등의 최적화도 해야해.
> ---
> curl -sS -X POST "http://ddns.nanoha.kr/api/ddns/update" \
>   -H "Content-Type: application/json" \
>   -H "X-DDNS-Key: ~~~~~~~~~" \
>   -d '{"hostname":"~~~~~~","ip":"~~~~~","record_type":"A"}'

## 변경 요약

- DDNS 기본 API path를 `/api/ddns/update`로 변경하고 기존 endpoint path를 보정하는 018 migration을 추가했다.
- DDNS API 인증 header를 Bearer token에서 `X-DDNS-Key`로 변경했다.
- DDNS 등록 payload를 예시 계약에 맞춰 `hostname`, `ip`, `record_type`만 보내도록 단순화했다.
- 서비스 도메인 DDNS 등록 시 `DOCKER_INFRA_DDNS_PUBLIC_IP_URLS` endpoint로 공인 IP를 조회해 전송하도록 변경했다.
- DDNS 등록 정보 기반으로 dispatcher config와 마지막 전송 IP state file을 생성하고, 같은 IP면 재호출을 건너뛰는 NetworkManager dispatcher agent를 추가했다.
- Ubuntu 24.04 installer에 `network-manager` package와 DDNS dispatcher 환경변수 예시를 추가했다.

## 변경 파일

- `config/docker_infra.py`
- `src/model/db/migrations/018_ddns_update_api_contract.sql`
- `src/model/db/migrations/018_ddns_update_api_contract.down.sql`
- `src/model/struct/domains_ddns.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/local_command_scripts.py`
- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `installer/install.sh`
- `installer/docker-infra.env.example`
- `installer/README.md`
- `docs/docker-infra-deployment.md`
- `README.md`
- `tests/api/test_domain_management_ui.py`
- `tests/api/test_installer_contract.py`
- `devlog.md`
- `devlog/2026-05-18/227-ddns-update-api-networkmanager-dispatcher.md`

## DB 적용

- `src/model/db/migrations/018_ddns_update_api_contract.sql`을 적용했다.
- `schema_migrations`에 `018 / ddns_update_api_contract` checksum을 기록했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/domains_ddns.py src/model/struct/local_command_catalog.py src/model/struct/local_command_scripts.py config/docker_infra.py src/app/page.domains/api.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_services_preflight tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_installer_contract tests.api.test_backup_registry_nodes tests.api.test_node_reporter tests.api.test_local_executor`: 38개 테스트 통과, 3개 skip
- `scripts/docker_infra_migrate.py status`: 018 적용 및 checksum 일치 확인
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 전체 migration runner는 기존 001, 011 checksum mismatch와 012, 014 pending 상태 때문에 여전히 중단될 수 있다.
- NetworkManager dispatcher는 실제 운영 host에서 NetworkManager가 대상 NIC 이벤트를 발생시켜야 즉시 동작한다.
- DDNS 삭제 API 계약은 이번 예시가 update만 제공했기 때문에 기존 DELETE 방식과 실제 DDNS 서버 구현이 다르면 추가 조정이 필요하다.
