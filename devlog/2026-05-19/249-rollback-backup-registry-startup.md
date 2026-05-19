# 249. 롤백 전 백업 저장소 부분 기동 감지와 자동 시작 추가

- 날짜: 2026-05-19
- 리뷰 ID: zpohqovvxevuifffyabfrkowvcfssjat
- 분류: ux

## 원 요청

```text
Error response from daemon: Get "http://220.82.71.78:5000/v2/": dial tcp 220.82.71.78:5000: connect: connection refused
롤백 동작에서 위와 같은 에러 로그가 떴어.
```

## 변경 파일

- `src/model/struct/services_deploy.py`
- `src/model/struct/backup_system_runtime.py`
- `src/model/struct/local_command_catalog.py`
- `tests/api/test_backup_system_runtime.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-19/249-rollback-backup-registry-startup.md`

## 변경 내용

- 백업 저장소 Compose 상태 확인이 실행 중 컨테이너만 보지 않도록 `docker compose ps -a --format json`을 사용하게 했다.
- Harbor 필수 서비스 전체가 실행 중일 때만 백업 저장소 상태를 `running`으로 판정하도록 했다.
- 스냅샷 롤백 배포에서 registry login 전에 백업 저장소 상태를 갱신하고, 중지/부분 기동 상태면 먼저 `backup_system.enable()`로 시작하도록 했다.
- registry가 막 시작되는 중이면 Docker login을 최대 12회 재시도하며 처리 로그에 대기 상태를 남기도록 했다.

## 확인 결과

- 현재 백업 저장소는 `log`만 `running`이고 `registry`, `proxy`, `core`, `postgresql` 등이 `exited` 상태라 5000 포트가 열려 있지 않음을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_deploy.py src/model/struct/backup_system_runtime.py src/model/struct/local_command_catalog.py src/app/page.services/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_runtime tests.api.test_services_preflight tests.api.test_backup_system_ui tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_images_templates_catalog` 통과 (`30 tests`, `skipped=2`).
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `curl -k -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/services` 200 확인.
- `git -C /root/docker-infra/project/main diff --check` 통과.

## 남은 리스크

- 실제 `wiki_service` 재롤백/재배포는 운영 Docker stack 변경을 동반하므로 수행하지 않았다.
- 현재 백업 저장소 컨테이너를 수동으로 시작하지는 않았고, 다음 스냅샷 롤백 배포 시 코드 경로에서 먼저 시작된다.
