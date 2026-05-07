# Docker Infra 마스터 노드와 Swarm 로드밸런싱 설계 반영

- **ID**: 002
- **날짜**: 2026-05-06
- **유형**: 문서 업데이트

## 사용자 원 요청

사용자가 다음 내용을 설계 문서에 반영해 달라고 요청했다.

- `docker stack deploy` 시 기본 오케스트레이션 및 로드밸런싱이 적용되어야 하며, nginx/apache2와 유기적으로 설정되어야 함
- 마스터 노드는 별도 지정이 아니라 Docker Infra 서비스가 실행되는 서버이며, 해당 서버에 nginx/apache2가 설치되어 있다는 전제로 문서를 수정해야 함
- 사용자 관리 등 사용자 계층은 앞으로도 도입할 생각이 전혀 없음

## 작업 요약

Docker Infra 실행 서버를 local master, Swarm manager, proxy host, 도메인 진입점으로 명시했다. `docker stack deploy` 배포 단계에서 Swarm replica, rolling update, restart policy, routing mesh/VIP 기반 로드밸런싱을 적용하고, nginx/apache2가 local master의 published port를 upstream으로 사용하도록 설계를 보강했다.

또한 사용자 계층, 권한 관리, RBAC가 향후에도 도입되지 않는다는 원칙을 문서 전반에 반영하고, Harbor/Cloudflare/감사 로그 문구에서 사용자 확장을 암시하는 표현을 제거했다.

## 변경 파일 목록

### 프로젝트 문서

- `docs/docker-infra-design.md`: 마스터 노드 정의, Swarm 로드밸런싱, proxy 연동, 사용자 계층 영구 제외 설계 반영

### 작업 기록

- `devlog.md`: 2026-05-06 002 항목 추가
- `devlog/2026-05-06/002-master-node-swarm-load-balancing.md`: 상세 작업 기록 추가

## 검증

- Markdown 문서 수정 확인
- 사용자 계층 관련 표현이 "도입하지 않는다"는 방향으로 정리되어 있는지 확인
- devlog 요약 row와 상세 파일 경로 일치 확인
- `git diff --check` 통과 확인
- 신규/수정 문서 trailing whitespace 없음 확인
