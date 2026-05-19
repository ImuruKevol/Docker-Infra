# 244. 서비스/시스템 수동 백업 진행 로그 표시 추가

- 날짜: 2026-05-19
- 리뷰 ID: zpohqovvxevuifffyabfrkowvcfssjat
- 분류: ux

## 원 요청

```text
백업 진행 과정이 간단하게라도 스트리밍 형식같은걸로 보여져야 해. 서비스 관리 화면과 시스템 설정의 수동 백업 둘 다
```

## 변경 파일

- `src/model/struct/service_image_backup_scheduler.py`
- `src/model/struct/services_runtime.py`
- `src/app/page.system/api.py`
- `src/app/page.system/view.ts`
- `src/app/page.system/view.pug`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `tests/api/test_backup_system_ui.py`
- `tests/api/test_services_preflight.py`
- `tests/api/test_backup_system_schedule.py`
- `devlog.md`
- `devlog/2026-05-19/244-backup-progress-streaming-ui.md`

## 변경 내용

- 시스템 설정의 수동 백업을 백그라운드 operation으로 실행하고, `operation_logs.output`을 주기적으로 조회해 진행 로그 패널에 표시하도록 했다.
- 서비스 상세의 스냅샷 백업도 백그라운드 operation으로 실행해 기존 처리 로그 모달에서 시작/대상 확인/서비스별 완료/실패 로그를 갱신하도록 했다.
- 수동 정책 백업과 서비스 스냅샷 백업 runner에 단계별 progress output을 기록하도록 보강했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_ui tests.api.test_services_preflight tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_images_templates_catalog` 통과 (`24 tests`, `skipped=2`).
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `curl -k -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/system` 200 확인.
- `curl -k -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/services` 200 확인.
- `git -C /root/docker-infra/project/main diff --check` 통과.

## 남은 리스크

- 실제 백업 실행은 컨테이너 일시 정지와 백업 저장소 push를 동반하므로 운영 데이터에 영향을 주지 않기 위해 수행하지 않았다.
