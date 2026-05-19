# 백업 스냅샷 실행과 로컬 이미지 정리

- **ID**: 241
- **날짜**: 2026-05-19
- **유형**: 기능 추가

## 작업 요약
수동 백업 실행 시 컨테이너 스냅샷도 함께 처리하도록 백업 스케줄러와 시스템 화면 호출 payload를 보강했다.
이미지와 스냅샷을 백업 저장소에 push한 뒤 로컬 Docker에 남는 백업 태그를 정리하고, 이미지 관리 화면의 사용자 노출 명칭을 Harbor에서 백업 저장소로 변경했다.

## 원문 요청사항
```text
작업 진행해줘.

일단 지금 백업 실행(수동 백업) 시 스냅샷까지 저장하는 기능이 없음.
그리고 이미지 백업 후에는 로컬 저장소와 Harbor에 둘다 저장이 된 상태인데, Harbor에 push한 후에는 로컬 저장소에서는 해당 이미지를 삭제해줘.
그리고 이미지 관리 화면에서 Harbor라는 이름 말고 백업 저장소 라는 이름으로 바꿔줘.
```

## 변경 파일 목록
- `src/model/struct/service_image_backup_scheduler.py`
  - 강제 실행 수동 백업에서 스냅샷을 기본 포함하고, 수동 실행은 이미지 백업 한도와 별도로 스냅샷 후보를 처리하도록 수정.
- `src/model/struct/service_image_backup_runner.py`
  - 이미지 push 후 로컬 백업 태그를 `docker image rm`으로 정리하고, 백업 중 새로 pull한 원본 이미지도 함께 정리하도록 수정.
- `src/model/struct/service_image_snapshot_runner.py`
  - `docker commit`으로 생성한 스냅샷 이미지를 push 후 로컬에서 정리하도록 수정.
- `src/app/page.system/api.py`
  - 수동 백업 API가 스냅샷 포함 payload를 스케줄러에 전달하도록 수정.
- `src/app/page.system/view.ts`
  - 수동 백업 확인 문구와 호출 payload에 스냅샷 포함 의도를 반영.
- `src/app/page.images/view.pug`
  - 이미지 관리 화면의 Harbor 사용자 노출 문구를 백업 저장소로 변경.
- `src/app/page.images/view.ts`
  - 이미지 관리 화면의 alert/confirm 문구를 백업 저장소 기준으로 변경.
- `tests/api/test_backup_system_schedule.py`
  - 수동 강제 백업이 정책 옵션이 꺼져 있어도 스냅샷을 포함하는지 검증 추가.
- `tests/api/test_backup_system_cleanup.py`
  - push 후 로컬 백업 이미지 정리 명령 계약 검증 추가.
- `tests/api/test_images_templates_catalog.py`
  - 이미지 관리 화면의 백업 저장소 표기 계약 검증 추가.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_images_templates_catalog.ImagesStaticContractTest`
  - 결과: 8개 테스트 통과.
- `wiz_project_build(projectName="main", clean=false)`
  - 결과: 성공.
