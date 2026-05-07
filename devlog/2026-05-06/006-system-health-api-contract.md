# 시스템 health API 계약과 라우트 추가

- **ID**: 006
- **날짜**: 2026-05-06
- **유형**: API 계약/프로젝트 구조

## 사용자 원 요청

사용자가 현재 진행 상태를 확인하고 작업을 이어서 진행해 달라고 요청했다.

## 진행 상태 확인

기존 devlog 기준으로 Docker Infra 설계 문서, 마스터 노드/Swarm 로드밸런싱 설계 반영, 실제 개발 TODO, 샘플 소스 정리와 Docker Infra 앱 골격, conda 실행 환경 명시가 완료되어 있었다. TODO 기준으로 P0-01은 완료 흐름에 들어갔고, P0-02는 프로젝트 구조와 health API 기준점이 아직 남아 있어 이 항목을 이어서 진행했다.

## 작업 요약

P0-02의 완료 조건과 테스트 기준을 맞추기 위해 `/api/system/health` source route를 추가했다. route controller는 직접 응답을 조립하지 않고 `src/model/docker_infra/system.py` 도메인 모델에서 health payload를 받아 응답하도록 분리했다. OpenAPI 정적 계약에 health endpoint와 schema를 추가하고, 서버가 준비된 경우 실제 HTTP health 응답까지 검증하는 테스트를 보강했다.

DB migration은 P2 단계 작업이므로 현재 health 응답의 database check는 `not_configured`와 `schema_version: null`로 명시했다.

## 변경 파일 목록

### Source route

- `src/route/api-system-health/app.json`: `/api/system/health` route 등록
- `src/route/api-system-health/controller.py`: health 모델 응답을 JSON status로 반환

### Backend model

- `src/model/docker_infra/system.py`: Docker Infra system health payload 생성 모델 추가

### API 계약

- `docs/api/openapi.json`: `/api/system/health`, `HealthResponse`, `HealthData`, `HealthCheck` schema 추가

### 테스트

- `tests/api/test_openapi_contract.py`: 정적 OpenAPI와 선택적 live health API 검증 추가
- `tests/api/test_system_health_structure.py`: health route 등록과 모델 분리 구조 검증 추가

### Source app

- `src/app/page.dashboard/api.py`: 대시보드 checklist를 현재 진행 상태에 맞게 갱신

### 작업 기록

- `devlog.md`: 006 항목 추가
- `devlog/2026-05-06/006-system-health-api-contract.md`: 상세 작업 기록 추가

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api` 실행: 8개 중 5개 통과, live API 3개는 `DOCKER_INFRA_BASE_URL` 미설정으로 skip
- `/opt/conda/envs/docker-infra/bin/python -m json.tool docs/api/openapi.json` 실행: JSON 파싱 성공
- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 실행: 신규 route/model/test 문법 검사 성공
- WIZ MCP build는 내부적으로 기본 `wiz` 실행 파일을 찾아 실패: `/bin/sh: 1: wiz: not found`
- `/opt/conda/envs/docker-infra/bin/wiz project build --project main` 실행: 성공
- `git diff --check` 실행: 통과
- 검증 중 생성된 `__pycache__` 디렉터리 삭제 완료

## Cleanup

이번 작업은 DB row, 파일 저장소 리소스, Docker/Swarm 리소스, 외부 연동 리소스를 생성하지 않았다.
