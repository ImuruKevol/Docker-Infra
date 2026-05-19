# 248. 롤백 배포 직후 서비스 상세 재조회 오류 방지

- 날짜: 2026-05-19
- 리뷰 ID: zpohqovvxevuifffyabfrkowvcfssjat
- 분류: ux

## 원 요청

```text
롤백 배포 요청 후 서비스 상세가 열리지 않고 에러가 떴어.
```

## 변경 파일

- `src/model/struct/services_deploy.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-19/248-rollback-deploy-detail-reload-guard.md`

## 변경 내용

- 롤백 배포 시작 직후 서비스 상세를 즉시 재조회하지 않고, 반환된 operation으로 처리 로그 모달을 먼저 열도록 했다.
- `deploy_service_background` 응답에 `operation`과 `service`를 top-level로 함께 내려 UI가 추가 상세 조회 없이 진행 상태를 표시할 수 있게 했다.
- 배포 흐름 안에서 배포 관리자 Docker daemon insecure registry 설정을 직접 변경하는 경로를 제거해 DB 컨테이너가 재시작될 수 있는 원인을 줄였다.
- 배포 operation 모달은 필요 시 즉시 상세 refresh를 생략하고 polling부터 시작할 수 있도록 했다.
- `psycopg.OperationalError`도 DB 장애 응답으로 처리해 서비스 API가 WIZ 500으로 터지지 않게 했다.

## 확인 결과

- `/var/log/wiz/docker-infra`에서 `/wiz/api/page.services/detail_service`가 `127.0.0.1:5432` 연결 거부로 실패한 로그를 확인했다.
- `infra-db` 컨테이너가 현재 `Up` 상태이고 `5432` 포트가 열려 있음을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_deploy.py src/model/struct/services_rollback.py src/app/page.services/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight tests.api.test_backup_system_ui tests.api.test_backup_system_schedule tests.api.test_backup_system_cleanup tests.api.test_images_templates_catalog` 통과 (`24 tests`, `skipped=2`).
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `curl -k -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/services` 200 확인.
- `git -C /root/docker-infra/project/main diff --check` 통과.

## 남은 리스크

- 인증 세션이 없어 실제 `detail_service` API를 브라우저 세션으로 직접 재호출하지는 못했다.
- 실제 `wiki_service` 재롤백/재배포는 운영 Docker stack 변경을 동반하므로 수행하지 않았다.
