# 개발/테스트 compose와 runtime 격리 정책 추가

- **ID**: 007
- **날짜**: 2026-05-06
- **유형**: 개발/테스트 환경

## 사용자 원 요청

사용자가 이전 작업에 이어 계속 진행해 달라고 요청했다.

## 작업 요약

TODO P0-03에 맞춰 Docker Infra 개발/테스트 실행 환경을 프로젝트 내부 기준으로 분리했다. WIZ 작업 지침에 따라 workspace root의 기존 `docker/docker-compose.yaml`은 수정하지 않고 참고만 했으며, current WIZ project인 `project/main` 안에 개발용 PostgreSQL 16 compose와 테스트용 disposable PostgreSQL compose를 추가했다.

테스트 runtime root는 `.runtime/test` 아래로 격리하고, nginx/apache2 proxy sandbox 설정 디렉토리를 프로젝트 내부에 정의했다. Swarm 통합 테스트는 Docker socket을 사용하는 `swarm` profile로 분리했다. DB migration은 P2 단계 작업이므로 현재는 테스트 DB를 disposable container로 재생성하는 reset 정책을 문서화하고, 테스트 schema init SQL만 추가했다.

## 변경 파일 목록

### Compose/runtime

- `docker/compose/development.yaml`: 개발용 PostgreSQL 16 compose 추가
- `docker/compose/test.yaml`: API, Swarm, proxy profile이 분리된 테스트 compose 추가
- `docker/postgres/init-test.sql`: 테스트 DB의 `docker_infra_test` schema 초기화 SQL 추가
- `docker/sandbox/nginx/conf.d/.gitkeep`: nginx sandbox 설정 디렉토리 유지
- `docker/sandbox/apache2/sites-enabled/.gitkeep`: apache2 sandbox 설정 디렉토리 유지

### 문서/설정

- `.gitignore`: `.runtime/`과 local compose env 파일 ignore 추가
- `README.md`: runtime 문서와 compose 실행 명령 추가
- `docs/docker-infra-design.md`: PostgreSQL compose 기준을 project-local dev/test compose로 갱신
- `docs/docker-infra-runtime.md`: 개발/테스트 compose, runtime root, DB reset, cleanup 정책 추가
- `config-sample/database.py`: 샘플 post DB 설정 제거, P2 전 framework/session fallback 설명으로 정리

### 테스트/cleanup

- `tests/api/test_environment_compose.py`: compose 분리, profile, sandbox dir, cleanup helper 구조 검증 추가
- `tests/cleanup/reset_test_environment.py`: project-local `.runtime/test` 파일 root cleanup helper 추가

### Source app

- `src/app/page.dashboard/api.py`: 대시보드 checklist를 P0-03 진행 상태에 맞게 갱신

### 작업 기록

- `devlog.md`: 007 항목 추가
- `devlog/2026-05-06/007-dev-test-compose-runtime-isolation.md`: 상세 작업 기록 추가

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: 12개 중 9개 통과, live API 3개는 `DOCKER_INFRA_BASE_URL` 미설정으로 skip
- `/opt/conda/envs/docker-infra/bin/python -m py_compile tests/cleanup/reset_test_environment.py tests/api/test_environment_compose.py config-sample/database.py` 실행: 성공
- compose YAML을 PyYAML로 파싱: `docker/compose/development.yaml`, `docker/compose/test.yaml` 모두 성공
- `docker compose -f docker/compose/development.yaml config` 실행: 성공
- `docker compose -f docker/compose/test.yaml --profile api --profile swarm --profile proxy config` 실행: 성공
- `/opt/conda/envs/docker-infra/bin/python tests/cleanup/reset_test_environment.py` 실행: 테스트 runtime root cleanup 성공
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main` 실행: 성공
- `git diff --check` 실행: 통과
- 검증 중 생성된 `.runtime`과 `__pycache__` 삭제 완료

## Cleanup

이번 작업은 실제 DB row, Docker container, Docker volume, Swarm resource, proxy 실제 설정, 외부 DNS/Harbor/GitLab 리소스를 생성하지 않았다. 테스트 중 만든 project-local `.runtime/test` 디렉토리와 Python bytecode cache는 삭제했다.
