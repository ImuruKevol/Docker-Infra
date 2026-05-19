# 242. 서비스 상세 스냅샷 백업 버튼과 버전 이력 연동 보강

- 날짜: 2026-05-19
- 리뷰 ID: zpohqovvxevuifffyabfrkowvcfssjat
- 분류: ux

## 원 요청

```text
시스템 설정에서 수동 백업 실행 시 스냅샷까지 백업이 진행된다는 모달을 띄운 후 진행이 되어야 해.
그리고 서비스 관리 화면에서 해당 서비스 상세에서 백업을 할 수 있는 버튼이 있어야 해. 물론 여기도 스냅샷으로 백업이 되어야 하고, 잠깐 서비스가 중지될 수 있다는 경고 메세지도 띄워야 해.
그리고 서비스별로 스냅샷 백업에 대해서는 버전 이력 탭과도 연동이 되어야 해.
```

## 변경 파일

- `src/app/page.system/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/model/struct/services_runtime.py`
- `tests/api/test_backup_system_ui.py`
- `tests/api/test_services_preflight.py`

## 변경 내용

- 시스템 설정의 수동 백업 확인 모달에 컨테이너 스냅샷 포함과 일시 정지 가능성 안내를 추가하고, 실행 요청에 `include_snapshots: true`, `snapshot_pause: true`를 명시했다.
- 서비스 상세 헤더에 서비스 단위 스냅샷 백업 버튼을 추가하고, 실행 전 컨테이너가 잠깐 일시 정지될 수 있음을 확인받도록 했다.
- 서비스 단위 스냅샷 백업 요청이 현재 Compose 이미지 목록을 기록한 뒤 각 컨테이너 스냅샷 백업을 수행하도록 확장했다.
- 버전 이력 데이터에 이미지/스냅샷 백업 요약을 연결하고, 버전 카드에 스냅샷 백업 수를 표시하도록 했다.
- 서비스 상세의 사용자 노출 문구에서 Harbor 명칭을 백업 저장소로 정리했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_ui tests.api.test_services_preflight tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_images_templates_catalog` 통과 (`24 tests`, `skipped=2`).
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `git -C /root/docker-infra/project/main diff --check` 통과.

## 남은 리스크

- 실제 Docker 서비스에 대한 스냅샷 백업 실행은 테스트 환경에서 수행하지 않았다.
