# ORAS absolute path 오류 수정과 named volume 백업 실수행

- **ID**: 012
- **날짜**: 2026-06-22
- **유형**: 버그 수정 및 운영 확인
- **리뷰 ID**: vgosoiiihlsnzkukbdizwwevcjgpgjcg

## 원문 요청사항

```text
아래와 같이 named volume 백업 시 에러가 뜨고 있어. 수정하고 볼륨 백업을 수행해줘.

등록 서비스 기준 named volume 백업 대상 2개를 확인했습니다.
명함 관리 서비스 / db / bus_f7b72d_mariadb_data named volume 백업을 시작합니다.
명함 관리 서비스 / db / bus_f7b72d_mariadb_data named volume 백업 실패: named volume 백업 명령 실행에 실패했습니다.
notedown-server / notedown-server / notedown_server_70d632_notedown_data named volume 백업을 시작합니다.
notedown-server / notedown-server / notedown_server_70d632_notedown_data named volume 백업 실패: named volume 백업 명령 실행에 실패했습니다.
```

## 원인

ORAS 1.3.2가 absolute file path push를 기본 차단해, `/tmp/docker-infra-volume-backup.../<archive>.tar.gz`를 직접 전달한 `oras push`가 실패했다.

## 변경 파일 목록

- `src/model/struct/service_volume_backups.py`
  - archive 생성 후 작업 디렉터리로 `cd "$work"`한 뒤 상대 경로 archive를 `oras push`에 전달하도록 수정.
  - 백업 명령 실패 시 마지막 stderr/stdout 라인을 `ServiceError` 메시지에 붙여 다음 장애 원인을 화면에서 바로 확인할 수 있게 보강.
- `tests/api/test_backup_system_cleanup.py`
  - ORAS push가 상대 경로 archive media spec을 사용하고 실패 상세 메시지를 구성하는 계약을 검증.
- `devlog.md`, `devlog/2026-06-22/012-volume-backup-oras-path-fix-run.md`
  - 작업 기록 추가.

## 백업 수행 결과

- `bus_f7b72d_mariadb_data`
  - 상태: `backup_succeeded`
  - artifact: `172.16.0.224:5000/bus_f7b72d/volume-db-bus_f7b72d_mariadb_data:20260622065114-mini3`
- `notedown_server_70d632_notedown_data`
  - 상태: `backup_succeeded`
  - artifact: `172.16.0.224:5000/notedown_server_70d632/volume-notedown-server-notedown_server_70d632_notedown_data:20260622065112-mini3`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/service_volume_backups.py tests/api/test_backup_system_cleanup.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_cleanup tests.api.test_backup_system_schedule tests.api.test_backup_system_ui`
- `wiz_project_build(projectName="main", clean=false)`
- `git diff --check`
- mini3 서버 ORAS 확인: `oras version` 1.3.2
- DB `service_volume_backups`의 두 대상 volume이 `backup_succeeded`와 Harbor artifact ref로 갱신됨을 확인.

## 남은 리스크

- 이번 수행은 문제로 보고된 두 named volume에 대한 수동 재시도이며, 전체 자동 백업 scheduler의 다음 예약 실행은 별도 운영 시점에 다시 확인해야 한다.
- DB 계열 volume의 시점 일관성은 기존 설계와 동일하게 crash-consistent archive 기준이다.
