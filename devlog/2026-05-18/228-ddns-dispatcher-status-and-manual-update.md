# 228. DDNS dispatcher 마지막 요청 표시와 수동 API 호출 추가

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 도메인 관리 화면에 NetworkManager dispatcher agent 마지막 호출 정보도 표시해줘. 마지막으로 언제 DDNS 서버에 요청을 했는지, 마지막 요청 값(IP)은 뭔지. 그리고 수동으로 버튼을 눌러서 API를 호출할 수 있는 기능도 필요해.

## 변경 요약

- DDNS endpoint 목록에 NetworkManager dispatcher의 마지막 DDNS 요청 시각, 마지막 요청 IP, 대상 hostname, agent record 수를 표시했다.
- DDNS endpoint별 `API 호출` 버튼을 추가해 현재 등록된 DDNS 레코드를 수동으로 강제 갱신할 수 있게 했다.
- 수동 호출 성공 시 DDNS registration의 `target_host`, `last_sync_at`, metadata와 dispatcher state file을 함께 갱신하도록 했다.
- dispatcher agent state에 `endpoint_id`, `last_sent_at`을 기록하고 endpoint별 상태 요약을 API 응답에 포함했다.
- dispatcher state를 DB 등록 정보로 seed할 때 기존 agent state의 최신 IP를 불필요하게 덮어쓰지 않도록 병합 로직을 보강했다.

## 변경 파일

- `src/model/struct/domains_ddns.py`
- `src/model/struct/local_command_scripts.py`
- `src/app/page.domains/api.py`
- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `tests/api/test_domain_management_ui.py`
- `devlog.md`
- `devlog/2026-05-18/228-ddns-dispatcher-status-and-manual-update.md`

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/domains_ddns.py src/model/struct/local_command_scripts.py src/app/page.domains/api.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_services_preflight tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_installer_contract tests.api.test_backup_registry_nodes tests.api.test_node_reporter tests.api.test_local_executor`: 38개 테스트 통과, 3개 skip
- `git diff --check`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 수동 호출은 등록 완료 상태의 DDNS 레코드가 있을 때만 동작한다.
- 실제 DDNS 서버 API와 public IP 조회 endpoint 접근성은 운영 네트워크에서 별도 확인이 필요하다.
