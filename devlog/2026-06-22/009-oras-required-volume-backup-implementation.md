# ORAS 필수 정책과 named volume 자동 백업 구현

- 날짜: 2026-06-22
- 작업 ID: 009
- 리뷰 ID: vgosoiiihlsnzkukbdizwwevcjgpgjcg

## 사용자 요청

> oras가 없으면 fallback을 넣으면 절대 안돼.
> 서버 관리 화면에서 서버 추가 시 "snap install oras --classic" 명령어를 통해 설치하는 과정이 추가되도록 해야해.
> 일단 서버 관리에 등록된 서버들에는 내가 수동으로 전부 설치해놨어.
>
> 이제 이 문서를 바탕으로 실제 코드에 적용해줘.

## 변경 파일

- `docs/backup-named-volume-snapshot-design.md`
  - ORAS helper/fallback 공급안을 제거하고 target node에 설치된 `oras`만 사용하는 필수 정책으로 정리.
  - 신규 서버 등록 시 `snap install oras --classic` 실행, 백업 시 ORAS 미존재 실패, `full_state`/`volume_only` 정책을 문서화.
- `src/model/struct/nodes_registry.py`
  - 서버 추가 과정에서 관리용 SSH key 등록 후 `command -v oras || snap install oras --classic`을 실행하도록 연결.
  - 설치 실패 시 `NODE_ORAS_INSTALL_FAILED`로 서버 등록을 중단하고 connection check에 `oras_install` 결과를 남김.
- `src/model/struct/service_volume_backups.py`
  - `service_volume_backups` 테이블, Compose named volume 탐지, 실행 중 컨테이너가 있는 node 기준 백업 대상 기록을 추가.
  - Docker 임시 컨테이너로 tar/gzip archive를 만들고 target node의 `oras push`로 Harbor OCI artifact에 업로드.
  - ORAS가 없으면 fallback 없이 `SERVICE_VOLUME_BACKUP_ORAS_REQUIRED`로 실패 처리.
- `src/model/struct/service_image_backup_scheduler.py`
  - 자동/수동 백업 기본 실행을 컨테이너 스냅샷과 named volume 백업 모두 포함하도록 확장.
  - `volume_only` 정책에서는 컨테이너 스냅샷을 건너뛰고 named volume 백업만 실행.
  - 진행 로그에 서비스명, compose 서비스명, volume명을 표시.
- `src/model/struct/service_image_backup_cleanup.py`
  - 서비스별 보존 개수 정책이 image snapshot과 volume artifact 모두에 적용되도록 정리.
- `src/model/struct/services_runtime.py`, `src/app/page.services/view.ts`, `src/app/page.services/view.pug`
  - 서비스 상세 버전 이력 탭에 named volume 백업 이력과 삭제 상태를 함께 표시.
- `src/model/struct/backup_system_policy_defaults.py`, `src/app/page.system/api.py`, `src/app/page.system/view.ts`
  - 백업 정책 기본값과 즉시 실행 payload를 `service_state_snapshot`/`full_state` 기준으로 정리하고 결과 표시를 volume 수량까지 확장.
- `src/model/struct/ai_assistant.py`
  - Agent 템플릿 생성 결과에 named volume 기본 백업 정책을 포함하고, 명시 요청 시에만 `volume_only`를 쓰도록 보정.
- `src/app/page.servers/view.pug`, `src/app/page.servers/view.ts`
  - 서버 추가 UI에 ORAS 설치 과정을 표시하고 action label에 ORAS 설치 상태를 추가.
- `tests/api/test_backup_system_schedule.py`, `tests/api/test_backup_system_cleanup.py`, `tests/api/test_backup_system_ui.py`, `tests/api/test_services_preflight.py`
  - 자동 백업, ORAS 필수 정책, 보존 정책, 서비스 이력 연동 정적/단위 검증을 보강.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/service_volume_backups.py src/model/struct/service_image_backup_scheduler.py src/model/struct/service_image_backup_cleanup.py src/model/struct/services_runtime.py src/model/struct/nodes_registry.py src/model/struct/backup_system_policy_defaults.py src/model/struct/ai_assistant.py tests/api/test_backup_system_schedule.py tests/api/test_backup_system_cleanup.py tests/api/test_backup_system_ui.py tests/api/test_services_preflight.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_backup_system_ui`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_release_contract_is_wired tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_rollback_contract_is_wired`
- `wiz_project_build(projectName="main", clean=false)`
- `git diff --check`

## 남은 리스크

- 실제 원격 서버에서 named volume archive 생성과 `oras push`까지의 end-to-end 실행은 환경 의존 작업이라 이번 검증 범위에서는 수행하지 않았다.
- DB volume은 현재 crash-consistent archive 기준이며, 서비스별 pre-freeze/post-thaw hook과 named volume 복구 UI/API는 후속 구현 범위로 남아 있다.
