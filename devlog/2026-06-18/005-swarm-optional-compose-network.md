# Swarm 선택 연동과 Compose 배포 네트워크 분리

- **ID**: 005
- **날짜**: 2026-06-18
- **유형**: 버그 수정

## 작업 요약

서버의 Docker 사용 가능 상태와 Swarm 연결 상태를 분리했습니다. Swarm에 묶이지 않은 서버도 Compose 배포 대상으로 선택될 수 있도록 배치, Compose 검증, 배포, 런타임 상태 갱신, AI/MCP 컨텍스트, 대시보드와 서버 상세 표시를 함께 조정했습니다.

## 원문 요청사항

```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: vxfutfdgxcpbmljmzjoogvliygrjppol
- 제목: docker swarm 로직 개선
- 요청 링크: https://infra-dev.nanoha.kr/dashboard
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 신규
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 포함됨
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 리뷰어 요청 내용

현재 서버를 등록 시 docker swarm 연동 상태가 곧 상태값으로 표시되고 있음. 근데 이건 엄밀히 말해 맞지 않음.
일단 docker swarm에 묶어놓지 않아도 서비스 배포 시 문제가 없도록 개선해줘. 특히 AI agent에서 알아서 요청할 때나 MCP, 프롬프트 등에서 이 부분이 충분히 반영이 되어야 해. 현재는 어차피 서비스가 같은 서버에 뜨는 형식이라 크게 상관은 없을 것 같은데 확인은 필요해.
단, docker-compose.yaml 생성 시 자동으로 docker swarm network로 고정되는 로직은 보정이 필요해. swarm으로 묶여있지 않은 서버에 생성할 때는 다른 이름의 network를 생성하도록 해야해.
그리고 대시보드, 서버 상세 화면에서도 반영이 되어야 해.
```

## 변경 파일 목록

- `src/model/struct/compose_rules.py`, `src/model/struct/compose_validator.py`, `src/model/struct/services_compose.py`: Swarm용 `docker_infra_overlay`와 Compose용 `docker_infra_bridge` 네트워크 선택을 분리했습니다.
- `src/model/struct/services.py`, `src/model/struct/services_update.py`, `src/model/struct/services_placement.py`: 선택 서버의 Swarm 연결 여부에 따라 배포 모드와 네트워크를 저장/검증하도록 수정했습니다.
- `src/model/struct/services_deploy.py`, `src/model/struct/services_status.py`, `src/model/struct/services_delete.py`, `src/model/struct/local_command_catalog.py`, `config/docker_infra.py`: 비 Swarm 서버 배포에 `docker compose up/down`과 bridge network 준비 경로를 추가했습니다.
- `src/model/struct/nodes_shared.py`, `src/model/struct/nodes_local_master.py`: 서버 상태를 Swarm active/inactive에 종속하지 않고 Docker 확인 결과 중심으로 표시하도록 조정했습니다.
- `src/model/struct/ai_assistant.py`, `src/model/struct/template_ai.py`, `src/model/struct/codex_runtime.py`, `tools/docker_infra_mcp.py`: AI/MCP 컨텍스트와 Compose 계약에 Swarm/Compose 네트워크 선택 기준을 반영했습니다.
- `src/model/struct/infra_catalog_registry.py`, `src/app/page.dashboard/view.ts`, `src/app/page.dashboard/view.pug`, `src/app/page.servers/view.ts`, `src/app/page.servers/view.pug`: 대시보드와 서버 상세에 배포 모드/Swarm 연결 상태를 별도 배지로 노출했습니다.
- `tests/api/test_compose_validator.py`: Compose 모드에서 bridge 네트워크를 주입하는 정적 검증 테스트를 추가했습니다.
- `devlog.md`, `devlog/2026-06-18/005-swarm-optional-compose-network.md`: 작업 devlog를 추가했습니다.

## 검증 결과

- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile ...`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_compose_validator.ComposeValidateStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_port_allocation_avoids_well_known_published_ports tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_certbot_issue_waits_for_runtime_and_exposes_renewal_ops tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_delete_contract_is_wired tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_docker_infra_mcp_accepts_codex_stdio_json`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 참고: `tests.api.test_services_preflight` 전체 실행은 기존 서비스 생성 화면 정적 토큰 기대값(`변수 {{editableTemplateFields().length}}개`, 관련 템플릿 지원 토큰) 불일치 2건으로 실패했습니다. 이번 Swarm/Compose 변경 경로와 직접 관련된 정적 테스트는 통과했습니다.

## 남은 리스크

- 실제 원격 비 Swarm 서버에서의 `docker compose up` 배포는 이 환경에서 라이브로 실행하지 못했습니다.
- Compose 삭제 시 원격 서버의 named volume 정리는 기존 로컬 stack volume 정리 수준을 유지하므로, 원격 Compose named volume까지 완전 삭제가 필요한 경우 후속 보강이 필요합니다.
