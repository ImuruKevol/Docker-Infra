# 020. Docker Infra WIZ model/struct 구조 리팩토링

- 날짜: 2026-05-07
- 원 요청: 사용자가 "현재 이 Docker Infra가 개발된 부분들이 .github 디렉토리에 정의, 정리된 wiz framework의 구조에 대부분 맞지 않아. controller, api, model 등등 모든 부분들이 wiz framework 구조에 맞지 않게 되어있어. 코드들을 전수조사해서 .github 디렉토리에 정의된 wiz framework의 구조에 맞도록 전부 리팩토링해줘. 필요하면 기존에 작성된 문서들이나 codex용 문서들도 수정해줘. 일단 테스트는 리팩토링 후 따로 다시 진행할거니까 리팩토링 위주로 진행해줘."라고 요청했다.
- 범위: Docker Infra model/controller/route/app API의 WIZ 구조 정렬

## 변경 파일

- `src/model/struct.py`
- `src/model/db/postgres.py`
- `src/model/db/migration.py`
- `src/model/db/migrations/*.sql`
- `src/model/struct/auth.py`
- `src/model/struct/compose_validator.py`
- `src/model/struct/jobs.py`
- `src/model/struct/local_executor.py`
- `src/model/struct/nodes.py`
- `src/model/struct/secret_masking.py`
- `src/model/struct/settings.py`
- `src/model/struct/setup.py`
- `src/model/struct/ssh_executor.py`
- `src/model/struct/system.py`
- `src/controller/base.py`
- `src/route/*/controller.py`
- `src/app/page.access/api.py`
- `src/app/page.servers/api.py`
- `src/app/page.system/api.py`
- `scripts/docker_infra_migrate.py`
- `README.md`
- `docs/docker-infra-runtime.md`
- `docs/docker-infra-development-todo.md`
- `tests/api/test_auth_setup.py`
- `tests/api/test_migration_schema.py`
- `tests/api/test_sample_cleanup.py`
- `tests/api/test_system_health_structure.py`
- `devlog.md`
- `devlog/2026-05-07/020-wiz-model-struct-refactor.md`

## 작업 내용

- 기존 `src/model/docker_infra` Python package형 배치를 제거하고 WIZ 기준의 `src/model/db`와 `src/model/struct`로 재배치했다.
- PostgreSQL 연결과 migration runner를 `src/model/db/postgres.py`, `src/model/db/migration.py`로 분리하고 두 파일 모두 `Model` 변수를 제공하게 했다.
- Docker Infra 도메인 로직을 `src/model/struct/*.py`로 이동하고 내부 `from docker_infra...` import와 `sys.path` 삽입을 WIZ `wiz.model(...)` 의존성으로 대체했다.
- `src/model/struct.py`를 Docker Infra root Struct 진입점으로 확장해 `auth`, `settings`, `jobs`, `nodes`, `setup`, `system`, `compose_validator` 등을 노출했다.
- route controller와 page `api.py`가 `wiz.model("docker_infra/...")` 대신 `wiz.model("struct")` 진입점을 통해 도메인 서비스를 호출하도록 정리했다.
- base controller에서 임시 model import path 조작을 제거하고 setup/auth 접근을 root Struct 경유로 변경했다.
- migration CLI는 새 `src/model/db/migration.py`를 importlib로 로드하도록 수정했다.
- README, runtime/TODO 문서, 정적 테스트의 모델 경로 기대값을 새 WIZ 구조에 맞게 갱신했다.

## 검증

- WIZ model loader 유사 방식으로 `struct`와 하위 모델 10종 로드
  - 결과: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_sample_cleanup tests.api.test_system_health_structure.SystemHealthStructureTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_auth_setup.AuthSetupStaticContractTest tests.api.test_compose_validator.ComposeValidateStaticContractTest tests.api.test_local_executor.LocalExecutorStaticContractTest`
  - 결과: 12개 통과
- `/opt/conda/envs/docker-infra/bin/python scripts/docker_infra_migrate.py --help`
  - 결과: migration CLI import와 help 출력 성공
- Python source compile check
  - 결과: 70개 Python 파일 컴파일 성공
- WIZ build
  - 결과: 성공

## Cleanup

- 이번 리팩토링 검증은 DB row나 runtime 파일을 생성하지 않았다.
- Python `__pycache__` 디렉토리를 제거했다.
