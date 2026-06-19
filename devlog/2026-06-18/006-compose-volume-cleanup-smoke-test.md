# Compose 원격 볼륨 삭제 보강과 Swarm/비Swarm smoke 검증

## 원 요청

- 스웜 서버, 비스웜 서버에 docker compose up을 간단하게 테스트를 진행하여 검증.
- 남은 리스크로 남긴 "원격 Compose named volume 완전 삭제" 보강.

## 변경 파일

- `src/model/struct/local_command_catalog.py`
  - `service.compose.down` 명령에 `remove_volumes` 옵션을 추가해 삭제 경로에서만 `docker compose down --volumes`를 실행하도록 보강.
- `src/model/struct/services_delete.py`
  - Compose 배포 삭제 시 local master와 remote node 모두 `down --volumes`를 사용하도록 변경.
  - 원격 Compose 파일이 없는 fallback 삭제에서도 Compose project label과 `${STACK}_` prefix 기반 named volume을 수집해 강제 제거하도록 보강.
  - Compose 삭제 경로에서는 별도 stack volume 제거 단계를 중복 실행하지 않도록 skip 처리.
- `tests/api/test_services_preflight.py`
  - 서비스 삭제 정적 계약 테스트에 Compose down, `--volumes`, Compose project label cleanup 검증 토큰 추가.
- `devlog.md`
- `devlog/2026-06-18/006-compose-volume-cleanup-smoke-test.md`

## 검증 결과

- Swarm 연결 서버 smoke
  - 대상: `mini2` / `172.16.0.225:22`
  - 상태: Docker Swarm `active`, Docker Compose `v5.1.3`
  - 검증: `docker_infra_bridge` 네트워크 기준 `docker compose up -d`, 컨테이너 실행, named volume 생성, `docker compose down --volumes`, 컨테이너/볼륨 제거 확인.
  - 결과: `swarm compose smoke ok: project=reviewops_vxf_swarm image=debian:bookworm-slim network=docker_infra_bridge volume_removed=true`
- 비Swarm 서버 smoke
  - 대상: `ktw-gpu` / `dizest.nanoha.kr:55556`
  - 상태: Docker Swarm `inactive`, Docker Compose `v2.33.1`
  - 검증: `docker_infra_bridge` 네트워크 기준 `docker compose up -d`, 컨테이너 실행, named volume 생성, `docker compose down --volumes`, 컨테이너/볼륨 제거 확인.
  - 결과: `non-swarm compose smoke ok: project=reviewops_vxf_compose image=postgres:15 network=docker_infra_bridge volume_removed=true`
- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...`
  - 결과: 통과
- 대상 단위 테스트
  - 명령: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_compose_validator.ComposeValidateStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_port_allocation_avoids_well_known_published_ports tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_certbot_issue_waits_for_runtime_and_exposes_renewal_ops tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_delete_contract_is_wired tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_docker_infra_mcp_accepts_codex_stdio_json`
  - 결과: 8 tests 통과
- `wiz_project_build(projectName="main", clean=false)`
  - 결과: 통과
- 전체 `tests.api.test_services_preflight`
  - 결과: 22 tests 중 기존 서비스 생성 UI 정적 계약 2건 실패 유지
  - 실패: `test_service_create_preflight_contract_is_wired`, `test_service_create_supports_templates_and_draft_sources`

## 남은 리스크

- 요청된 Swarm/비Swarm Compose up/down 및 named volume 제거 경로는 실제 원격 서버에서 확인 완료.
- 추가 비Swarm 후보였던 `lenovo` 서버는 SSH host key mismatch로 이번 검증 대상에서 제외했고, 비Swarm 검증은 `ktw-gpu`로 대체했다.
