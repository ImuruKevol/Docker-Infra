# 서비스 AI Agent 설계

- 기준일: 2026-05-28
- 리뷰 ID: cxaqmytxjrdnjjdcuazqouethjqeipfv
- 대상 화면: `/services/create`, `/services` AI 검사/수정
- 목적: 사용자가 원하는 서비스만 설명해도 Docker Infra가 Codex, Claude Code, 헤르메스 에이전트 기반으로 AI 초안 생성, 상태 점검, 보정, 배포 후 오류 수정까지 안전하게 처리하는 실행 계약을 고정한다.

## 1. 설계 목표

서비스 AI는 사용자를 대신해 Docker Infra 서버를 실제로 점검하고 조치할 수 있는 Agent다. 실제 저장, 배포, 도메인 변경, 컨테이너 조작은 Docker Infra의 검증 API와 Docker Infra MCP를 통해 수행하며, MCP는 Docker Infra 자체 삭제와 OS 치명 동작만 차단한다.

AI 실행 단위는 `Codex`, `Claude Code`, `헤르메스 에이전트` 세 가지 Agent로 제한한다. Docker Infra는 외부 LLM provider API를 직접 호출하지 않고, 선택된 Agent CLI에 Docker Infra MCP 컨텍스트, 상세 도구 계약, critical guard 정책을 주입한다.

핵심 원칙은 다음과 같다.

- AI는 초안과 판단을 만든다. Docker Infra는 검증과 실행을 담당한다.
- AI 호출은 매번 임시 Agent runtime home에서 실행하며, Docker Infra MCP의 critical guard를 전제로 full-control Agent 실행을 허용한다.
- AI에는 secret 원문을 넘기지 않는다. secret은 key 이름과 생성 요청만 넘긴다.
- AI가 사용할 MCP tool은 기본적으로 전체 Docker Infra MCP 도구를 노출한다. scope는 결과 JSON 계약과 UI 적용 흐름을 구분하기 위한 정보이며, 권한 차단 기준은 아니다.
- 배포, 저장, DNS/nginx 변경은 Docker Infra API가 수행한다. Agent는 MCP로 서버 상태 확인, SSH 명령, 컨테이너 조치, 네트워크 probe를 수행할 수 있으나 Docker Infra control plane과 OS critical resource는 보호된다.
- 모든 AI 결과는 JSON contract, Compose validator, preflight, operation/audit log를 통과해야 화면에 적용된다.
- 상태 저장 데이터는 CephFS 또는 local bind mount 계약을 따른다. Agent는 새 Docker-managed volume을 만들거나 volume artifact 백업/복원 경로를 제안하지 않는다.

## 2. 작업 Scope

| Scope | 목적 | AI 산출물 | 실행 가능 MCP | Critical guard |
|---|---|---|---|---|
| `service_draft` | 자연어 요구사항을 서비스 초안으로 변환 | Compose, form, components, domain 후보, warnings | 전체 Docker Infra MCP 도구 | Docker Infra 자체 삭제, control service/container 제거, OS 종료/재부팅/디스크 wipe/format, OS critical path 재귀 삭제 |
| `service_preflight_repair` | 1차 초안을 Docker Infra 검사 결과로 보정 | 최종 Compose 초안과 수정 사유 | 전체 Docker Infra MCP 도구 | 동일 |
| `post_deploy_verification` | 배포 완료 후 실제 접속과 기능 동작 대기/검증 | 검증 판정, 추가 수정 필요 여부, 재호출 근거 | 전체 Docker Infra MCP 도구 | 동일 |
| `runtime_inspection` | 배포 후 장애 상태와 로그 분석 | 원인 요약, 수정 Compose 제안, 수동 조치 제안 | 전체 Docker Infra MCP 도구 | 동일 |
| `runtime_repair` | 장애 컨테이너 조치와 수정/재배포까지 포함 | 수정 Compose, `runtime_actions`, 재배포 제안 | 전체 Docker Infra MCP 도구 | 동일 |
| `operator_debug` | 운영자/개발자용 임시 진단 | 진단 요약 | 전체 Docker Infra MCP 도구 | 동일 |

`ssh_command`는 등록 서버에 대해 operator-level 명령 실행을 허용한다. MCP handler는 destructive 전체를 막는 방식이 아니라 `PERMISSION_MODE=agent_full_control_except_critical_destruction` 기준으로 Docker Infra 자체 삭제와 OS 치명 동작만 차단한다. AI는 우선 목적이 좁은 MCP 도구를 사용하고, 부족한 경우 `ssh_command`로 직접 확인/조치한다.

Storage 관련 예외는 더 엄격하게 본다. Agent가 `service_draft`, `service_preflight_repair`, `runtime_repair`, `post_deploy_verification` 중 어느 scope로 실행되더라도 최종 서비스 Compose는 Docker Infra storage normalizer를 통과해야 한다. top-level `volumes:`가 남아 있거나 volume artifact 백업/복원을 요구하면 저장/실행 단계에서 차단한다.

## 3. AI에 넘길 입력

AI 요청 payload는 다음 그룹으로 구성한다.

| 그룹 | 필드 | 설명 |
|---|---|---|
| 세션 | `review_id`, `operation_id`, `task_scope`, `ai_phase`, `mode`, `service_id` | 요청 단위 추적과 audit 연결 |
| 사용자 의도 | `intent`, `operator_message`, `language` | 사용자의 자연어 요구와 추가 코멘트 |
| 서비스 상태 | `form`, `components`, `base_content`, `domains`, `service`, `runtime_status`, `recent_operations` | 생성/수정/복구 대상의 현재 상태 |
| Docker Infra 컨텍스트 | `docker_infra_context`, `zones`, `placement`, `runtime_values` | 등록 서버, 자동 배치, overlay network, 서비스 root, 도메인 후보 |
| Storage 컨텍스트 | `storage_context` | 독립/Swarm 서버 모드, 기본 backend, CephFS health, mount root, Docker-managed volume 금지 여부 |
| 검증 계약 | `contract`, `output_format`, `compose_validation`, `input_contract`, `output_contract` | AI output과 Compose가 반드시 지킬 스키마 |
| 권한 계약 | `ai_permission_scope`, `mcp_guidance`, `terminal_actions` | 이번 요청에서 가능한 MCP와 금지된 실행 범위 |
| 검사 결과 | `docker_infra_inspection`, `runtime_diagnostics`, `client_runtime_issues` | deterministic preflight와 런타임 오류 신호 |

### 전달 금지 값

- API token, password, private key 원문
- DB connection string 원문
- DDNS key 원문
- SSH private key 내용
- 서비스 환경변수 secret value 원문
- 등록 서버의 secret성 내부 설정

필요한 경우 `secret_key`, `secret_ref`, `configured: true`, `masked: true` 같은 형태만 전달한다.

## 4. AI 출력 계약

서비스 생성/수정 AI는 JSON 객체 하나만 반환한다.

```json
{
  "form": {
    "name": "서비스 이름",
    "description": "한국어 설명",
    "domain_mode": "registered|none",
    "zone_id": "등록 도메인 ID",
    "domain_prefix": "app",
    "domain_target_key": "web",
    "domain_target_port": 8080,
    "domains": []
  },
  "components": [
    {
      "key": "web",
      "image_name": "nginx",
      "image_tag": "alpine",
      "ports": [{"target": 80, "published": 18080, "protocol": "tcp", "mode": "ingress"}],
      "env_vars": [],
      "volumes": []
    }
  ],
  "base_content": "version: '3.8'\nservices:\n  ...",
  "generated_secret_keys": [],
  "summary": "한국어 요약",
  "warnings": [],
  "notes": [],
  "thinking_summary": "결정 근거 요약"
}
```

상태 저장 경로가 있으면 JSON 또는 Compose metadata에 다음 형태가 포함되어야 한다.

```json
{
  "storage": {
    "backend": "cephfs|local_bind|auto",
    "mounts": [
      {
        "name": "data",
        "target": "/app/data",
        "quota": "20GiB",
        "snapshot_policy": "default"
      }
    ]
  }
}
```

Compose에 직접 들어가는 source는 Agent가 확정하지 않는다. 자동 템플릿은 `${DOCKER_INFRA_STORAGE_DATA}` 같은 placeholder를 쓰고, 서비스 생성/수정 결과는 Docker Infra가 저장 전에 CephFS 또는 local bind mount host path로 바꾼다.

런타임 수정 AI는 위 계약에 더해 다음을 반환할 수 있다.

```json
{
  "runtime_actions": [
    {
      "action": "restart",
      "node_id": "registered-node-id",
      "container_id": "container-id-or-name",
      "reason": "한국어 사유",
      "executed": false
    }
  ],
  "terminal_action_results": []
}
```

`runtime_actions`는 `terminal_actions.allow_container_actions`가 true일 때만 처리한다. `executed=true`는 AI가 MCP로 이미 실행한 조치를 중복 실행하지 않고 기록만 하라는 의미다.

## 5. Docker Infra가 담당할 일

Docker Infra는 AI 앞뒤의 control plane이다.

1. 사용자 입력을 정규화하고 scope를 결정한다.
2. AI에 넘길 context를 구성하면서 secret을 제거한다.
3. 선택된 Agent runtime에 `ai_permission_scope.mcp_enabled_tools`를 전달한다.
4. AI 1차 초안을 받으면 JSON schema와 Compose validator를 실행한다.
5. 이미지 존재, tag, published port, domain, nginx, placement를 deterministic preflight로 검사한다.
6. storage normalizer로 상태 저장 경로를 CephFS 또는 local bind mount 계약에 맞춘다.
7. 검사 결과를 AI 2차 보정에 넘긴다.
8. 최종 초안을 다시 검증한 뒤 화면에 적용한다.
9. 사용자의 저장/배포 클릭 이후에만 서비스 저장, nginx/DNS 변경, 배포를 실행한다.
10. 런타임 AI 수정은 기존 서비스 상세, operation log, container log, stack status, storage mount 상태를 context로 만들고, 사용자가 허용한 조치만 실행한다.
11. 위험 조치 결과는 operation log와 audit log에 기록한다.

## 6. MCP 도구 정책

MCP 서버 이름은 항상 `docker_infra`다. `infra_context` 응답과 `docker-infra://mcp/contract` resource는 아래 상세 계약을 JSON으로 제공한다.

| MCP tool | 권한 | 용도 | 보호 조건 |
|---|---|---|---|
| `infra_context` | read | 등록 서버, 배치 추천, runtime 값, DDNS endpoint, MCP 상세 계약 조회 | 없음 |
| `server_list` | read | 등록 서버와 SSH 설정 가능 여부 조회 | 없음 |
| `docker_search` | read/network | Docker Hub 이미지 후보 검색 | Docker CLI search timeout/trim |
| `docker_image_check` | read/network/local | local image inspect와 manifest inspect로 이미지 존재 확인 | timeout/trim |
| `server_port_check` | read/remote | 등록 서버의 published port bind 가능 여부 확인 | 등록 서버만 대상 |
| `service_stack_status` | read/local | local swarm manager에서 stack service/task 상태 확인 | stack name 필수 |
| `container_logs` | read/local/remote | 등록 서버의 컨테이너 로그 조회 | tail/timeout 제한 |
| `dns_lookup` | read/network | 서비스 도메인/노드 host DNS 해석 확인 | `allowed_probe_hosts`와 등록 노드 host만 허용 |
| `tcp_connect_check` | read/network | 허용 host:port TCP 연결 확인 | `allowed_probe_hosts`와 등록 노드 host만 허용 |
| `http_probe` | read/network | 허용 URL의 HTTP status, redirect, 본문 일부 확인 | http/https, 허용 host만 |
| `browser_probe` | read/network | 브라우저형 header로 허용 URL title/body snippet 확인 | JavaScript 미실행, 허용 host만 |
| `server_collect` | read/local/remote | system/docker/log 진단 수집 | 등록 서버만 대상, include/tail 제한 |
| `container_action` | runtime mutation | non-Docker-Infra 컨테이너 stop/restart/remove | Docker Infra control container 보호 |
| `ssh_command` | operator command | 등록 서버에서 stored SSH key로 shell 명령 실행 | Docker Infra self-destruction과 OS critical command 차단 |

기본 노출 도구는 전체 MCP 도구다. `mcp_enabled_tools`가 context에 있으면 `tools/list`와 `tools/call`은 해당 목록으로 줄일 수 있지만, 현재 Agent 정책의 기본값은 scope별 축소가 아니라 full-control이다. Codex config의 `enabled_tools`도 같은 전체 목록으로 생성한다.

차단되는 command family는 다음뿐이다.

- OS 종료/재부팅/전원 종료: `shutdown`, `reboot`, `poweroff`, `halt`
- 디스크 format/partition/wipe/write: `mkfs*`, `wipefs`, `fdisk`, `parted`, `dd ... of=...`
- `/`, `/bin`, `/boot`, `/dev`, `/etc`, `/lib*`, `/proc`, `/sbin`, `/sys`, `/usr`, `/var/lib/docker` 재귀 삭제
- `/root/docker-infra`, 현재 `project_root`, `/etc/docker-infra`, `/var/lib/docker-infra` 등 Docker Infra protected root 삭제
- Docker Infra control service/container/stack stop, disable, remove

서비스 AI 흐름에서는 다음도 실행 대상이 아니다.

- 새 Docker-managed volume 생성
- volume artifact 백업/복원 실행
- CephFS mount root 전체 삭제
- OSD slot 생성/삭제 마법사를 우회한 disk partition 작업
- 기존 배포 서비스의 데이터를 일반 검증/수정 flow 안에서 자동 이동

## 7. 생성 플로우

```text
사용자 자연어 입력
  -> Docker Infra context/permission 구성
  -> Codex service_draft 호출
  -> Docker Infra JSON/Compose 정규화
  -> storage_context 기준으로 CephFS/local bind mount 정규화
  -> 이미지/포트/도메인/배치 preflight
  -> Codex service_preflight_repair 호출
  -> Docker Infra 최종 검증
  -> 화면 wizard state 적용
  -> 사용자 저장/배포 클릭
  -> Docker Infra API가 저장/배포/nginx/DNS 실행
```

AI가 초안 단계에서 만든 Compose는 바로 배포하지 않는다. 항상 Docker Infra의 deterministic 검사와 사용자의 최종 확인을 거친다.

## 8. 런타임 검사/수정 플로우

```text
서비스 상세에서 사용자가 AI 검사/수정을 명시적으로 시작
  -> 백그라운드 operation 생성
  -> stack replicas/tasks/containers가 안정화될 때까지 대기
     - 같은 실패 상태가 반복되면 동일 로그를 압축하고, 일정 횟수 후 AI 분석으로 넘어간다.
  -> DNS, IP, port, HTTP probe 실행
  -> CephFS/local mount 상태와 쓰기 가능 여부 확인
  -> 사용자 추가 코멘트와 컨테이너 조치 허용 여부 반영
  -> Docker Infra가 runtime_diagnostics 구성
  -> Codex post_deploy_verification 호출
  -> Docker Infra가 수정 Compose와 runtime_actions 검증
  -> 허용된 container_action만 기록/실행
  -> 수정 Compose 저장 및 필요 시 재배포
  -> 재배포 후 probe 결과를 다시 모아 AI 검증을 재호출
     - 재배포 실패도 최종 횟수 전에는 다음 AI 검증/수정 시도로 이어간다.
  -> 최대 반복 횟수 안에 통과하면 operation succeeded, 아니면 failed/needs_attention
```

컨테이너 stop/restart/remove와 일반 runtime 조치는 Agent가 MCP로 수행할 수 있다. 다만 Docker Infra control plane, OS critical resource, 허용되지 않은 외부 probe 대상은 MCP handler에서 차단된다.

AI 검사/수정은 SSE 요청 안에서 오래 붙잡지 않는다. 사용자가 명시적으로 시작한 `service.ai.verify` operation이 백그라운드에서 상태를 갱신하고, 화면은 서비스 상세의 백그라운드 작업 배너와 처리 로그 모달 polling으로 언제든지 진행 상황을 보여준다. 일반 저장/배포만으로는 AI 검증 operation을 자동 시작하지 않는다.

## 9. 중복 컨테이너 방지

AI 생성/배포 실패 후 재시도에서 중복 컨테이너가 생기는 주요 원인은 세 가지다.

1. 같은 생성 화면에서 재시도할 때 매번 새 namespace/stack을 만드는 경우
2. 이미 진행 중인 배포 operation이 있는데 같은 서비스에 배포를 다시 시작하는 경우
3. Compose service key가 바뀐 상태로 `docker stack deploy`를 실행하면서 이전 stack service가 pruning되지 않는 경우

방지 기준은 다음과 같다.

- 서비스 생성 화면은 `create_session_id`를 payload, `source_ref`, `draft_metadata`에 넣는다.
- backend는 같은 `create_session_id`로 이미 생성된 서비스가 있으면 새 서비스를 만들지 않고 기존 service row를 반환한다.
- 같은 서비스의 `pending/running` 배포 operation이 있으면 새 background deploy thread를 만들지 않고 기존 operation을 반환한다.
- stack 재배포는 `docker stack deploy --prune`을 사용해 Compose에서 사라진 service를 제거한다.
- AI runtime repair가 service key를 바꿀 때는 이전 key 제거 영향이 검증 결과에 포함되어야 한다.

## 10. 수용 기준

- AI 요청 context에 `ai_permission_scope`, `mcp_guidance.enabled_tools`, `PERMISSION_MODE=agent_full_control_except_critical_destruction`이 항상 포함된다.
- Agent runtime은 기본적으로 전체 Docker Infra MCP tool을 `enabled_tools`로 주입한다.
- MCP 서버는 `infra_context`와 `docker-infra://mcp/contract` resource로 상세 tool/permission/critical guard 정의를 제공한다.
- `service_draft`, `service_preflight_repair`, `post_deploy_verification`, `runtime_inspection`, `runtime_repair` 모두 전체 MCP 도구가 보인다.
- post-deploy 검증에서는 허용된 서비스 도메인/노드 host만 DNS/TCP/HTTP probe 대상이 된다.
- AI 검사/수정은 `service.ai.verify` 백그라운드 operation으로 생성되고, `pending/running` 상태도 화면에서 조회 및 polling된다.
- 같은 생성 세션과 같은 배포 operation에 대한 중복 실행은 기존 service/operation으로 수렴한다.
- `container_action`은 기본 허용이며, `terminal_actions.allow_container_actions=false`로 명시한 요청에서만 실패한다. Docker Infra control container는 항상 보호된다.
- AI 출력은 JSON 단일 객체만 허용하고, Docker Infra 검증 실패 시 자동 보정 또는 사용자 오류로 처리한다.
- AI 출력의 상태 저장 경로는 `storage_context`와 `x-docker-infra.storage.mounts` 계약을 따라야 한다.
- 최종 저장 Compose에는 top-level `volumes:`가 남지 않는다.
- 자동 템플릿 생성은 `${DOCKER_INFRA_STORAGE_*}` placeholder를 사용하고 host path를 직접 쓰지 않는다.
- `service.ai.verify`는 storage mount health와 쓰기 가능 여부를 검사 결과에 포함한다.
- secret 원문은 AI context, stream, operation log, devlog에 남지 않는다.

## 11. 남은 구현 과제

- `operator_debug` scope를 실제 UI/API에서 열지 여부 결정
- 위험 MCP 실행 결과를 audit log에 구조화 저장
- `service.ai.verify` 결과를 별도 요약 카드로 노출할지 처리 로그만 사용할지 결정
- 사용자 요구 기능을 검증할 `function_assertion` schema와 UI 입력 방식 정의
- AI 초안/런타임 수정/배포 후 검증에 대한 live API 테스트와 replay fixture 추가
- MCP tool별 timeout, output trim, redaction 정책을 테스트로 고정
- Docker Hub 외 private registry가 필요한 경우 별도 registry 검사 MCP를 추가
- 브라우저 상호작용까지 필요한 서비스에는 별도 `browser_probe` MCP를 추가할지 검토
