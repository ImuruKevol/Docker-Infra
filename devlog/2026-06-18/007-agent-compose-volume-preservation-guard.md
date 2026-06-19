# 에이전트 작업 중 Compose 볼륨 보존 가드 보강

## 원 요청

- Compose 서비스 삭제 시 `docker compose down --volumes`로 볼륨을 지우는 것은 맞지만, 에이전트를 통한 작업이나 마이그레이션, 버전 릴리즈 등에서는 볼륨이 삭제되면 안 되므로 안전한지 확인.

## 확인 및 변경 내용

- 서비스 삭제 경로
  - `src/model/struct/services_delete.py`에서만 `remove_volumes=True`와 원격 `docker compose down --volumes`를 사용한다.
- 재배포/마이그레이션 경로
  - `src/model/struct/services_deploy.py`의 Compose force recreate는 로컬/원격 모두 `down`만 사용하고 `--volumes`를 붙이지 않는다.
  - `src/model/struct/services_migration.py`는 `force_recreate=True`로 배포를 재호출하지만 `remove_volumes`를 전달하지 않는다.
- 릴리즈/롤백 경로
  - `src/model/struct/services_release.py`, `src/model/struct/services_rollback.py`는 Compose 파일/버전 기록만 다루고 `service.compose.down`을 호출하지 않는다.
- 에이전트/MCP 경로 보강
  - `tools/docker_infra_mcp.py`에 persistent Docker volume deletion guard를 추가해 기본적으로 아래 명령을 차단한다.
    - `docker compose down --volumes`
    - `docker-compose down -v`
    - `docker compose rm --volumes`
    - `docker volume rm/remove/prune`
    - `docker system prune --volumes`
  - Docker Infra context가 명시적으로 `allow_volume_destruction`, `allow_persistent_volume_delete`, `allow_compose_volume_delete` 중 하나를 제공한 경우에만 MCP shell command에서 허용한다.
  - `src/model/struct/codex_runtime.py`, `src/model/struct/ai_assistant.py`, `src/model/struct/template_ai.py`의 agent/MCP prompt와 runtime context에 repair/migration/release/rollback/redeploy 작업 중 persistent volume deletion 금지를 명시했다.
- 테스트 보강
  - `tests/api/test_services_preflight.py`에 Compose 볼륨 삭제가 서비스 삭제 경로에만 제한되는지, MCP가 볼륨 삭제 shell command를 기본 차단하는지 검증을 추가했다.

## 변경 파일

- `tools/docker_infra_mcp.py`
- `src/model/struct/codex_runtime.py`
- `src/model/struct/ai_assistant.py`
- `src/model/struct/template_ai.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-06-18/007-agent-compose-volume-preservation-guard.md`

## 검증 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile tools/docker_infra_mcp.py src/model/struct/codex_runtime.py src/model/struct/ai_assistant.py src/model/struct/template_ai.py tests/api/test_services_preflight.py`
  - 결과: 통과
- 대상 단위 테스트
  - 명령: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_compose_validator.ComposeValidateStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_docker_infra_mcp_accepts_codex_stdio_json tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_docker_infra_mcp_blocks_persistent_volume_deletion_by_default tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_delete_contract_is_wired tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_compose_volume_removal_is_limited_to_service_delete tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_port_allocation_avoids_well_known_published_ports tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_certbot_issue_waits_for_runtime_and_exposes_renewal_ops`
  - 결과: 10 tests 통과
- `wiz_project_build(projectName="main", clean=false)`
  - 결과: 통과
- 전체 `tests.api.test_services_preflight`
  - 결과: 23 tests 중 기존 서비스 생성 UI 정적 계약 2건 실패 유지
  - 실패: `test_service_create_preflight_contract_is_wired`, `test_service_create_supports_templates_and_draft_sources`

## 남은 리스크

- MCP shell command 가드는 대표적인 Docker CLI volume deletion 패턴을 차단한다. Docker CLI를 우회하는 custom script 내부에서 동적으로 볼륨 삭제 명령을 생성하는 경우까지 정적 문자열로 완전히 판별하지는 못한다.
