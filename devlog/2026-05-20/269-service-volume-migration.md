# 269. named volume 별도 이관 로직과 서비스 마이그레이션 연동

- 날짜: 2026-05-20
- 요청: named volume은 스냅샷 방식에 절대 포함이 되지 않아. 이 부분은 harbor와 별도로 로직을 만들어서 관리를 해야할 것 같아. 별도 관리 로직을 추가하고, 마이그레이션 로직에도 포함해줘.

## 변경 파일

- `src/model/struct/service_volume_migration.py`
- `src/model/struct/services_migration.py`
- `tests/api/test_service_migration.py`
- `devlog.md`
- `devlog/2026-05-20/269-service-volume-migration.md`

## 변경 내용

- Compose의 named volume을 감지하고 Docker 실제 volume 이름을 계산하는 전용 모델을 추가했다.
- Harbor 이미지 스냅샷과 분리하여 SSH/local shell 파이프라인으로 `tar` 스트림을 전송하고 대상 서버 volume을 재생성하는 로직을 추가했다.
- 서비스 마이그레이션 작업에서 컨테이너 스냅샷 생성 후, 대상 서버 배포 전에 named volume을 먼저 복사하도록 연결했다.
- 마이그레이션 metadata와 operation 결과에 `volume_migration` 결과를 기록하도록 했다.
- 마이그레이션 정적 계약 테스트에 named volume 이관 계약을 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/service_volume_migration.py src/model/struct/services_migration.py tests/api/test_service_migration.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_service_migration`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_service_migration tests.api.test_backup_registry_nodes`
- `rg -n "[ \t]+$" src/model/struct/service_volume_migration.py src/model/struct/services_migration.py tests/api/test_service_migration.py`
- WIZ build: `wiz_project_build(projectName="main", clean=false)` 성공

## 남은 리스크

- 실행 중인 컨테이너의 named volume을 온라인으로 `tar` 복사하므로, 데이터베이스처럼 쓰기 중인 workload는 애플리케이션 정지나 쓰기 차단 없이 완전한 시점 일관성을 보장하지 못한다.
- bind mount와 anonymous volume은 이번 로직 범위에서 제외했다.
