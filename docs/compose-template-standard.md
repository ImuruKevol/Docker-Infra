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

## AI Draft Rules

- 템플릿 관리 화면의 AI 초안은 위 Required Files 전체를 채우는 JSON output만 적용한다.
- AI가 만든 `docker-compose.yaml`의 모든 `{{ variable_name }}` placeholder는 `values.default.yaml`과 `values.schema.json`에 동시에 정의되어야 한다.
- AI 초안은 자동 저장하지 않으며, 사용자가 README/Compose/기본값/Schema를 검토한 뒤 저장한다.
- AI 초안은 서비스 생성/수정/점검용 AI와 분리된 `compose_template` 범위로 실행한다.
- AI output에는 `description`, `primary_image`, `category`, 배포 대상 서버, 구체 도메인, 런타임 조치가 포함되면 안 된다.

## AI Permission Scope

- 허용 MCP 도구: `infra_context`, `docker_search`, `docker_image_check`
- 허용 목적: Docker Infra의 정적 Compose 제약 확인, 이미지 후보 검색, 이미지 태그 존재 확인
- 차단 MCP 도구군: `server_list`, `server_port_check`, `server_collect`, `ssh_command`, `container_logs`, `container_action`, `service_stack_status`, `dns_lookup`, `tcp_connect_check`, `http_probe`, `browser_probe`
- 차단 조치: 템플릿 자동 저장, 서비스 배포, 컨테이너 조작, SSH 실행, 로그 수집, 네트워크 프로브, 특정 서버/포트/도메인 선택
- 적용 방식: AI는 초안만 반환하고, 화면에서 사용자가 검토 후 저장한다.

## MCP Contract

- MCP 서버는 `docker_infra`만 사용한다.
- `infra_context`는 네트워크명, Compose 규칙, 템플릿 규격 같은 정적 정책 확인에만 사용한다.
- `docker_search`는 이미지명이 불명확할 때 후보를 좁히는 용도로만 사용한다.
- `docker_image_check`는 반환할 이미지 태그가 실제로 존재하는지 확인하는 용도로만 사용한다.
- 허용되지 않은 MCP 도구가 없다는 사실을 사용자-facing README나 summary에 노출하지 않는다.

## Compose Rules

- `container_name`, `hostname`, 외부 network 의존은 사용하지 않는다.
- 공개 대상 service에는 healthcheck와 ports를 정의한다.
- 내부 DB/cache는 ports를 노출하지 않고 Compose service name으로만 연결한다.
- 내부 service 참조는 `{{ namespace }}_db`처럼 namespace placeholder를 사용한다.
