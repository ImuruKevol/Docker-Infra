# 243. wiki_service 스냅샷 백업 컨테이너 매칭 오류 수정

- 날짜: 2026-05-19
- 리뷰 ID: zpohqovvxevuifffyabfrkowvcfssjat
- 분류: ux

## 원 요청

```text
wiki_service에 대해 스냅샷 백업을 누르니 "서비스 스냅샷을 백업할 수 없습니다." 에러가 떴어.
```

## 변경 파일

- `src/model/struct/service_image_snapshot_runner.py`
- `src/model/struct/services_runtime.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `tests/api/test_services_preflight.py`

## 변경 내용

- 서비스 namespace에 `_`가 여러 개 포함된 경우에도 Swarm 런타임 서비스명에서 Compose 서비스명을 정확히 분리하도록 수정했다.
- WIZ 번들 환경에서 서로 다른 모듈 인스턴스의 `ServiceError`가 API까지 전달되지 못하는 경우를 보완해, 스냅샷 실패 사유가 JSON 응답으로 반환되도록 했다.
- 서비스 단위 스냅샷 실패 시 실패한 Compose 서비스별 사유를 모달에 표시하도록 했다.

## 확인 결과

- `/var/log/wiz/docker-infra`에서 `wiki_service_af4f85_*` 컨테이너 매칭 실패와 uncaught `ServiceError`를 확인했다.
- `wiki_service_af4f85_db -> db`, `wiki_service_af4f85_mediawiki -> mediawiki` 분리 로직을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight tests.api.test_backup_system_ui tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_images_templates_catalog` 통과 (`24 tests`, `skipped=2`).
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `git -C /root/docker-infra/project/main diff --check` 통과.

## 남은 리스크

- 실제 `wiki_service` 스냅샷 백업 재실행은 서비스 일시 정지와 백업 저장소 push를 동반하므로 수행하지 않았다.
