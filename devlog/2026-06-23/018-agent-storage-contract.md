# Agent 기반 생성과 서비스 동작의 CephFS Storage 계약 보강

## 사용자 요청

Agent를 통한 자동 템플릿 생성, Agent를 통한 서비스 관련 동작 등 Agent 관련 동작에서도 CephFS 적용과 Docker-managed volume 제거 방향이 반영되어야 한다. 이 내용이 포함되었는지 확인해달라.

## 변경 파일

- `docs/backup-volume-layered-storage-design.md`
- `docs/ceph-storage-application-plan.md`
- `docs/ceph-storage-reviewops-task-instructions.md`
- `docs/ceph-storage-implementation-feasibility-review.md`
- `docs/service-ai-codex-agent-design.md`
- `docs/compose-template-standard.md`
- `docs/docker-infra-development-todo.md`
- `devlog.md`
- `devlog/2026-06-23/018-agent-storage-contract.md`

## 변경 내용

- Agent가 자동 템플릿 생성, 서비스 생성/수정/import, `service.ai.verify`, runtime repair에서 동일한 CephFS/local bind mount 계약을 따르도록 설계 문서를 보강했다.
- Agent request context에 `storage_context`를 포함하고, AI output은 `x-docker-infra.storage.mounts` 또는 `${DOCKER_INFRA_STORAGE_*}` placeholder를 사용하도록 plan을 정리했다.
- ReviewOps 작업 지시서에 `AI/Agent 생성과 서비스 동작에 Storage 계약 반영` 태스크를 추가했다.
- Compose 템플릿 표준에 Storage Rules를 추가해 top-level `volumes:` 생성 금지와 Docker Infra storage placeholder 사용 규칙을 명시했다.
- 서비스 AI Agent 설계 문서에 storage normalizer, mount health 검증, volume artifact 백업/복원 제안 금지 규칙을 추가했다.

## 확인 결과

- ReviewOps 작업 지시서 13개 body가 모두 1000자 이하임을 확인했다.
- Agent 관련 문서에서 `storage_context`, `${DOCKER_INFRA_STORAGE_*}`, `x-docker-infra.storage.mounts`, `service.ai.verify`, runtime repair 반영 위치를 확인했다.
- 문서 변경만 수행했으므로 애플리케이션 빌드나 UI 테스트는 실행하지 않았다.

## 남은 리스크

- 실제 `ai_assistant.py`, `template_ai.py`, `codex_runtime.py` prompt와 validator 반영은 아직 구현되지 않았다.
- 기존 배포 서비스 데이터 이전은 여전히 제품 자동 기능이 아니며 별도 운영 절차 또는 명시적 Agent 작업으로 다뤄야 한다.
