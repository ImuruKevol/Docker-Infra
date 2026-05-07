# Docker Infra

Docker Infra는 Docker Swarm과 Docker Compose를 중심으로 개발/검증 인프라를 관리하기 위한 WIZ 기반 서비스입니다.

## 문서

- 핵심 설계 문서: [docs/docker-infra-design.md](docs/docker-infra-design.md)
- 실제 개발 TODO: [docs/docker-infra-development-todo.md](docs/docker-infra-development-todo.md)
- 개발/테스트 실행 환경: [docs/docker-infra-runtime.md](docs/docker-infra-runtime.md)

## 현재 구현 상태

현재 단계는 P6 Compose 검증 기반 구성입니다.

- 샘플 게시판, 멤버, 마이페이지 화면 제거
- 사용자 계층 없는 password-only 인증, rate limit, session cookie 정책 추가
- Docker Infra 메뉴와 주요 페이지 골격 추가
- `/openapi.json`, `/swagger`, `/api/system/health` 초기 계약 추가
- 개발용 PostgreSQL 16 compose와 테스트용 disposable compose 분리
- 테스트 runtime root와 proxy sandbox 디렉토리 정책 추가
- PostgreSQL migration CLI와 핵심 테이블 20종 schema 추가
- system settings 대표 CRUD API와 secret masking 응답 추가
- 최초 설치 마법사와 local master 자동 등록 API 추가
- 일반 설정, 연동 enabled 상태, secret masking 조회, 동적 메뉴 표시 추가
- Job/Step/Log 모델과 생성, 상태 전이, 로그 append, cancel/retry API 추가
- secret registry 기반 로그 저장 전 masking과 로그 검색/다운로드 API 추가
- Docker/Swarm/proxy local command adapter와 `/api/system/local-command/check` 추가
- local master Swarm manager/overlay network 보장 API 추가
- slave 최초 password 접속 확인, 관리용 SSH key file/fingerprint 저장, SSH/Docker check, Swarm join Job API 추가
- reporter token 발급, metric ingestion, 서버 상세/컨테이너 목록 API와 화면 추가
- Compose YAML parser 기반 검증과 deploy/network/healthcheck 정책 보강 API 추가

## 개발/테스트 compose

개발 DB:

```bash
docker compose -f docker/compose/development.yaml up -d postgres
```

API 테스트 DB:

```bash
docker compose -f docker/compose/test.yaml --profile api up -d postgres
```

테스트 파일 root cleanup:

```bash
/opt/conda/envs/docker-infra/bin/python tests/cleanup/reset_test_environment.py
```

Migration과 설치:

```bash
/opt/conda/envs/docker-infra/bin/python scripts/docker_infra_migrate.py up
curl -X POST /api/system/setup
```

## WIZ 소스 구조

- PostgreSQL 연결과 migration runner: `src/model/db/postgres.py`, `src/model/db/migration.py`
- Docker Infra 도메인 로직: `src/model/struct/*.py`와 도메인별 하위 Struct(`jobs_*`, `nodes_*` 등)
- 도메인 진입점: `src/model/struct.py`
- REST API: `src/route/*/controller.py`
- 화면 전용 API: `src/app/page.*/api.py`

route/controller와 app `api.py`는 도메인 파일을 직접 import하지 않고 `wiz.model("struct")` 진입점을 통해 호출합니다.
`wiz.response` 호출은 WIZ의 예외 기반 응답 종료 패턴 때문에 `try/except` 블록 밖에 두고, 보호 REST route와 페이지는 `user` controller에서 인증을 확인합니다.

## 주요 메뉴

- 서버 관리
- 서비스 관리
- 도메인 관리
- 이미지 관리
- 템플릿 관리
- 시스템 설정
- 도구 다운로드

## 민감 설정

연동 설정은 workspace root의 `config.env`와 `domain.txt`에 준비되어 있습니다. 이 파일의 값은 문서, 로그, devlog, 테스트 결과에 출력하지 않습니다.
WIZ backend 런타임 설정은 `project/main/config/docker_infra.py`에서 `config.env`를 읽고, `wiz.docker-infra` systemd service도 같은 파일을 `EnvironmentFile`로 주입합니다.

실제 저장소 구현 시에는 다음 원칙을 지킵니다.

- Harbor, GitLab, Cloudflare token/password는 암호화 저장
- API 응답과 화면에는 masking 값만 표시
- 테스트 로그와 Job 로그는 secret masking 후 저장
- Job 로그 검색/다운로드 결과도 저장된 masking 값을 유지
- Local Executor는 고정 adapter만 실행하고 destructive command는 allowlist가 필요
- SSH password는 최초 연결 확인에만 사용하고 저장하지 않으며, 이후 명령은 DB에 저장된 key file과 fingerprint 정보를 사용
- Reporter token은 hash만 저장하고 발급 응답에서만 원문 token을 표시
- Compose 검증은 `container_name`, `hostname`, 비고정 network를 거절하고 오류 field path를 반환
- 테스트 종료 및 실패 시 생성된 DB row와 파일을 cleanup

## WIZ root config

`[WIZ Project Root]/config/boot.py`

```python
import os
from pathlib import Path

from season.util import stdClass

SESSION_COOKIE_NAME = "docker_infra_session"
SESSION_TTL_SECONDS = 60 * 60 * 12
CONFIG_ENV_PATH = Path(__file__).resolve().parents[1] / "config.env"

def _config_env():
    if not CONFIG_ENV_PATH.is_file():
        return {}
    values = {}
    for line in CONFIG_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values

def _runtime_value(name):
    return os.environ.get(name, _config_env().get(name))

def _env_bool(name, default=None):
    value = _runtime_value(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}

def _apply_session_cookie_policy(flask_app, secure=False):
    flask_app.config["SESSION_COOKIE_NAME"] = SESSION_COOKIE_NAME
    flask_app.config["SESSION_COOKIE_HTTPONLY"] = True
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    flask_app.config["SESSION_COOKIE_SECURE"] = bool(secure)
    flask_app.config["PERMANENT_SESSION_LIFETIME"] = SESSION_TTL_SECONDS

def bootstrap(app, config):
    secure = _env_bool("DOCKER_INFRA_SESSION_COOKIE_SECURE", False)
    _apply_session_cookie_policy(app.flask, secure=secure)

def before_request(wiz):
    flask = wiz.server.package.flask
    secure = _env_bool("DOCKER_INFRA_SESSION_COOKIE_SECURE", flask.request.is_secure)
    _apply_session_cookie_policy(flask.current_app, secure=secure)

def after_request(wiz, response):
    return response

event = stdClass(
    before_request=before_request,
    after_request=after_request,
)

secret_key = _runtime_value("DOCKER_INFRA_SECRET_KEY") or "season-wiz-secret"

socketio = dict()
socketio['async_mode'] = 'threading'
socketio['cors_allowed_origins'] = '*'
socketio['async_handlers'] = True
socketio['always_connect'] = False
socketio['manage_session'] = True

run = dict()
run['allow_unsafe_werkzeug'] = True
run['host'] = "0.0.0.0"
run['port'] = 3001
run['use_reloader'] = False

```