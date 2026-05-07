# Docker Infra 실제 개발 TODO 문서 추가

- **ID**: 003
- **날짜**: 2026-05-06
- **유형**: 문서 추가

## 사용자 원 요청

사용자가 작성된 Docker Infra 설계 문서를 기반으로 실제 개발을 위한 상세 TODO를 작성해 달라고 요청했다. 각 작업별 설계 문서 reference, API/Swagger 기반 테스트, 실제 데이터와 운영 기반 검증, 테스트 데이터 cleanup, Playwright 화면 테스트, 그리고 실제 개발 전 샘플 소스/devlog 정리 작업을 포함해 달라고 요청했다.

## 작업 요약

Docker Infra 개발 TODO 문서를 추가했다. 문서는 샘플 프로젝트 정리, API 계약/Swagger, 테스트 하네스, DB migration, 인증/설치 마법사, Job Queue, local master/서버 관리, Compose/템플릿/파일 저장소, 서비스 배포/Swarm 로드밸런싱, proxy/DNS/SSL, GitLab/Harbor 이미지, 화면, Electron, 운영형 통합 테스트 순서로 구성했다.

각 TODO에는 설계 문서 reference, 작업 범위, 완료 조건, API 테스트와 Playwright 테스트, cleanup 요구사항을 포함했다.

## 변경 파일 목록

### 프로젝트 문서

- `docs/docker-infra-development-todo.md`: Docker Infra 실제 개발 TODO 추가
- `README.md`: 개발 TODO 문서 링크 추가

### 작업 기록

- `devlog.md`: 2026-05-06 003 항목 추가
- `devlog/2026-05-06/003-docker-infra-development-todo.md`: 상세 작업 기록 추가

## 검증

- Markdown 문서 파일 생성 확인
- README 링크 대상 파일 존재 확인
- devlog 요약 row와 상세 파일 경로 일치 확인
- 설계 문서 reference 오타 확인 및 수정
- 신규/수정 문서 trailing whitespace 없음 확인
- `git diff --check` 통과 확인
