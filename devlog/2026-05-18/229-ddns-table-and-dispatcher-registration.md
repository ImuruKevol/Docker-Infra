# 229. DDNS 테이블 UI와 dispatcher 등록 관리 추가

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 각 ddns에 대해 테이블 형식의 디자인으로 수정해줘.
> 그리고 NetworkManager dispatcher의 등록 여부를 확인해서 등록되어있지 않으면 등록할 수 있는 기능도 추가해줘. 디스패처 등록 여부는 DDNS 관리 서버의 헤더 부분에 작은 뱃지 형태로 표시해주고. 내가 직접 확인을 해야하니 등록 기능 추가 후에 현재 등록해놓은 dispatcher는 삭제해줘.

## 변경 요약

- DDNS 관리 서버 목록을 행 단위 테이블 UI로 변경했다.
- DDNS 관리 서버 header에 NetworkManager dispatcher 등록 상태 뱃지를 추가했다.
- dispatcher 미등록/부분 등록 상태에서 `Dispatcher 등록` 버튼을 표시하고, 버튼 클릭 시 `ddns.dispatcher.ensure`를 강제 실행하도록 API를 추가했다.
- dispatcher 상태 조회는 dispatcher 파일, agent 파일, 실행 권한, config 파일 존재 여부를 기준으로 판단하도록 했다.
- 현재 host의 기본 dispatcher 등록 파일과 agent 파일 삭제 명령을 실행했다.

## 변경 파일

- `src/model/struct/domains_ddns.py`
- `src/app/page.domains/api.py`
- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `tests/api/test_domain_management_ui.py`
- `devlog.md`
- `devlog/2026-05-18/229-ddns-table-and-dispatcher-registration.md`

## 확인한 내용

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/domains_ddns.py src/app/page.domains/api.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui`: 5개 테스트 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_services_preflight tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_installer_contract tests.api.test_backup_registry_nodes tests.api.test_node_reporter tests.api.test_local_executor`: 38개 테스트 통과, 3개 skip
- `git diff --check`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `/etc/NetworkManager/dispatcher.d/90-docker-infra-ddns`, `/usr/local/bin/docker-infra-ddns-update` 삭제 명령 실행 완료

## 남은 리스크

- 현재 실행 환경에는 기본 NetworkManager dispatcher directory가 없어, 삭제 전 등록 파일이 존재하지 않았다.
- dispatcher 등록 버튼은 local executor allowlist와 host 권한이 맞아야 성공한다.
- 실제 NetworkManager 이벤트 기반 동작은 운영 host에서 확인이 필요하다.
