# Compose Template Standard

Compose 템플릿은 사용자가 서비스 이름과 필요한 변수만 입력해 Docker Infra 서비스 초안을 만들기 위한 파일 기반 표준이다. 저장 위치는 WIZ data directory의 `templates/{namespace}/`이며, DB 테이블은 사용하지 않는다.

## Required Files

- `docker-compose.yaml`: `{{ variable_name }}` placeholder를 포함한 Compose 원본
- `values.default.yaml`: placeholder 기본값
- `values.schema.json`: 서비스 생성 화면에서 입력받을 변수 schema
- `README.md`: 서비스 생성 화면에 항상 노출되는 템플릿 운영 메모
- `template.json`: 이름, 노출 여부, metadata

## Schema Rules

- `namespace`는 서비스 이름 기준으로 자동 계산되므로 일반 사용자가 직접 입력하지 않는다.
- `password`, `secret`, `token`, `api_key`, `private_key`가 포함된 변수는 비밀 값으로 간주한다.
- 비밀 값이 비어 있거나 `change_me`, `*_change_me`이면 서비스 초안 적용 시 자동 생성한다.
- 공개 도메인 후보는 `template.json.metadata.public_endpoint`에 `{service, port, label}`로 정의한다.
- 컴포넌트 표시명은 `template.json.metadata.component_labels`에 Compose service key별로 정의한다.
- 분류는 `template.json.metadata.tags` 문자열 배열로 정의한다.

## Storage Rules

- 상태 저장 데이터가 필요한 템플릿은 `x-docker-infra.storage.mounts`를 반드시 포함한다.
- `docker-compose.yaml`의 service mount source에는 `${DOCKER_INFRA_STORAGE_<NAME>}` 형식의 Docker Infra storage placeholder를 사용한다.
- `${DOCKER_INFRA_STORAGE_<NAME>}`는 사용자가 입력하는 값이 아니므로 `values.default.yaml`과 `values.schema.json`에 넣지 않는다.
- 템플릿은 실제 host path나 CephFS 절대 경로를 직접 쓰지 않는다.
- 템플릿은 top-level `volumes:`로 Docker-managed volume을 만들지 않는다.
- 템플릿 렌더러는 실행 대상이 Swarm/Ceph 서버이면 CephFS bind mount path로, 독립 서버이면 local bind mount path로 치환한다.
- snapshot이 필요한 mount는 `snapshot_policy`를 함께 선언한다.

예시:

```yaml
services:
  app:
    image: example/app:latest
    volumes:
      - ${DOCKER_INFRA_STORAGE_DATA}:/app/data

x-docker-infra:
  storage:
    backend: auto
    mounts:
      - name: data
        target: /app/data
        quota: 20GiB
        snapshot_policy: default
```

## AI Draft Rules

- 템플릿 관리 화면의 AI 초안은 위 Required Files 전체를 채우는 JSON output만 적용한다.
- AI가 만든 `docker-compose.yaml`의 모든 `{{ variable_name }}` placeholder는 `values.default.yaml`과 `values.schema.json`에 동시에 정의되어야 한다.
- AI 초안은 자동 저장하지 않으며, 사용자가 README/Compose/기본값/Schema를 검토한 뒤 저장한다.
- AI 초안은 서비스 생성/수정/점검용 AI와 분리된 `compose_template` 범위로 실행한다.
- AI output에는 `description`, `primary_image`, `category`, 배포 대상 서버, 구체 도메인, 런타임 조치가 포함되면 안 된다.
- AI 초안이 DB, Redis, upload directory 같은 상태 저장 경로를 만들면 Storage Rules를 따라야 한다.
- AI 초안은 volume artifact 백업/복원 정책을 만들지 않는다.

## AI Permission Scope

- 허용 MCP 도구: Docker Infra MCP 전체 도구
- 허용 목적: Docker Infra의 Compose 제약 확인, 이미지 후보 검색, 이미지 태그 존재 확인, 등록 서버/런타임 사실 확인, 필요한 operator-level 점검
- 권한 모드: `agent_full_control_except_critical_destruction`
- 차단 조치: Docker Infra 자체 삭제, Docker Infra control service/container/stack stop/remove/disable, OS shutdown/reboot/poweroff/halt, disk format/partition/wipe/write, OS critical path 재귀 삭제
- 적용 방식: AI는 초안만 반환하고, 화면에서 사용자가 검토 후 저장한다.

## MCP Contract

- MCP 서버는 `docker_infra`만 사용한다.
- `infra_context`는 네트워크명, Compose 규칙, 템플릿 규격, 등록 서버, MCP 상세 계약을 제공한다.
- `docker-infra://mcp/contract` resource는 tool별 권한, side effect, critical guard를 JSON으로 제공한다.
- `docker_search`/`docker_image_check`는 이미지 후보와 exact tag 확인에 사용한다.
- 서버/로그/네트워크 도구는 템플릿 품질에 필요한 실제 runtime 사실 확인에 사용할 수 있다.
- MCP 도구 사용 가능 여부 자체를 사용자-facing README나 summary에 노출하지 않는다.

## Compose Rules

- `container_name`, `hostname`, 외부 network 의존은 사용하지 않는다.
- 공개 대상 service에는 healthcheck와 ports를 정의한다.
- 내부 DB/cache는 ports를 노출하지 않고 Compose service name으로만 연결한다.
- 내부 service 참조는 `{{ namespace }}_db`처럼 namespace placeholder를 사용한다.
- 상태 저장 경로는 Docker Infra storage placeholder를 사용하고 top-level `volumes:`는 만들지 않는다.
