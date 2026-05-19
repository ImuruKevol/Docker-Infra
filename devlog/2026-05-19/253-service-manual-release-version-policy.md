# 서비스 버전 이력을 수동 릴리즈 전용으로 전환

## 사용자 요청

- 리뷰 ID: `tlljwmjyzwmrfwwfnzgkjhcunqbktnwv`
- 원문: "심지어 서비스를 저장된 스냅샷 기준으로 롤백 시에도 버전이 남는 것 같아. 이러면 안돼... 작업 진행해줘."
- 리뷰 요약: 서비스 버전 이력은 AI 생성/수정/점검, Compose/Nginx 설정 변경, 롤백 중 자동으로 남기지 않고 사용자가 수동 릴리즈할 때만 남겨야 한다. 수동 릴리즈 시 Compose만 남길지 스냅샷 백업도 함께 수행할지 선택할 수 있어야 한다.

## 변경 내용

- `src/model/struct/services_release.py`를 추가해 `manual_release` source의 수동 릴리즈만 `compose_versions`를 생성하도록 분리했다.
- `src/model/struct/services.py`에 `ServiceReleaseMixin`을 연결하고 서비스 생성 시 자동 버전/이미지 이력 생성을 제거했다.
- `src/model/struct/services_update.py`에서 서비스 수정과 Compose 원문 저장 시 `compose_versions` 및 이미지 이력을 만들던 경로를 제거했다.
- `src/model/struct/services_rollback.py`에서 저장된 버전 기준 롤백 시 새 Compose 버전을 만들지 않도록 변경했다.
- `src/model/struct/service_image_backup_actions.py`에서 이미지 복원 시 새 Compose 버전을 만들지 않도록 변경했다.
- `src/model/struct/services_deploy.py`에서 배포 조정 정보를 최신 Compose 버전 메타데이터에 쓰지 않도록 변경했다.
- `src/model/struct/services_runtime.py`에서 스냅샷/이미지 기록이 명시적인 `compose_version_id`가 있을 때만 버전에 연결되도록 조정했다.
- `src/app/page.services/api.py`에 `release_service` API를 추가하고, 스냅샷 포함 릴리즈 선택 시 새 릴리즈 버전에 연결된 스냅샷 백업을 백그라운드로 시작하도록 했다.
- `src/app/page.services/view.ts`, `src/app/page.services/view.pug`에 수동 릴리즈 모달과 Compose-only / 스냅샷 포함 선택 UI를 추가하고, 저장 문구를 초안 저장 중심으로 정리했다.
- `tests/api/test_services_preflight.py`의 정적 계약을 새 릴리즈 정책에 맞게 갱신했다.

## 변경 파일

- `src/model/struct/services.py`
- `src/model/struct/services_release.py`
- `src/model/struct/services_update.py`
- `src/model/struct/services_rollback.py`
- `src/model/struct/services_runtime.py`
- `src/model/struct/services_deploy.py`
- `src/model/struct/service_image_backup_actions.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-19/253-service-manual-release-version-policy.md`

## 확인 결과

- `PYTHONDONTWRITEBYTECODE=1 python -m unittest tests.api.test_services_preflight` 통과.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `rg "INSERT INTO compose_versions|UPDATE compose_versions|SELECT COALESCE(max(version)" project/main/src/model/struct project/main/src/app -g '*.py'` 확인 결과, Compose 버전 생성 SQL은 `services_release.py`에만 남았다.
- `curl -I -b 'season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/services` 응답 `200 OK` 확인.

## 남은 리스크

- 기존 DB에 이미 자동 생성되어 있던 과거 `compose_versions` 행은 이번 변경에서 삭제하지 않았다.
- 스냅샷 포함 릴리즈의 실제 컨테이너 snapshot/push 성공 여부는 운영 환경의 백업 저장소와 컨테이너 상태에 따라 백그라운드 작업 로그에서 확인해야 한다.
