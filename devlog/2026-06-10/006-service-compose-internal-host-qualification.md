# 서비스 생성 Compose 내부 DB host namespace 보정

## 사용자 요청

- 리뷰 ID: `alpitwuiyzqcjojprsumwdaaiwbvnkrr`
- 제목: 서비스 생성 시 compose yaml 보완
- 요청 내용: mini3 서버에서 여러 서비스의 DB가 같은 `docker_infra_overlay` 네트워크에 붙고 DB host가 모두 `db`로 생성되어, 다른 서비스 DB로 연결되는 문제를 막도록 compose yaml 생성 로직을 보완.

## 변경 파일

- `src/model/struct/compose_rules.py`
- `src/model/struct/compose_validator.py`
- `src/model/struct/services_wizard.py`
- `tests/api/test_compose_validator.py`
- `devlog.md`
- `devlog/2026-06-10/006-service-compose-internal-host-qualification.md`

## 변경 내용

- Compose 공통 규칙에 내부 서비스 host 참조를 `namespace_service` 형태로 보정하는 유틸을 추가했다.
- `DB_HOST=db`, `DATABASE_URL=postgresql://...@db:5432/...`, `REDIS_URL=redis://redis:6379/0` 같은 환경변수 host 참조를 validator normalized compose 단계에서 보정하도록 연결했다.
- 서비스 생성 wizard의 render 단계에서도 환경변수 key가 host/url/uri/dsn 계열일 때 내부 서비스 참조를 같은 규칙으로 보정하도록 변경했다.
- host 참조가 아닌 `POSTGRES_DB=app`, `APP_NAME=worker` 같은 값은 서비스명과 같아도 보정하지 않도록 회귀 테스트를 추가했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_compose_validator` 통과.
- WIZ MCP `wiz_project_build(projectName="main", clean=false)` 통과.
- fake WIZ 컨텍스트에서 `services_wizard.render()`를 직접 호출해 `DB_HOST: db`가 `DB_HOST: cards_ab12_db`로 보정되고, compose service key `db:`는 유지되는 것을 확인했다.
- 참고: `tests.api.test_services_preflight` 전체 실행은 기존 작업 트리의 서비스 화면 UI 문자열 계약 변경으로 4건 실패했다. 실패 항목은 이번 변경 범위와 무관한 정적 UI 계약 테스트다.
