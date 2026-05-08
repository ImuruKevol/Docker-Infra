# 059. Job 제거·내장 Harbor 백업 시스템·관리자용 서비스 wizard 기준 TODO 재작성

## 사용자 요청

구조가 단순화되었으므로 TODO를 전면 재작성하고, 전체 TODO 파일과 남은 TODO 확인 파일을 별도로 작성한다. Job 시스템은 더 이상 필요하지 않으며, Harbor는 외부 연동이 아니라 마스터 노드에 직접 띄우는 서비스 이미지 백업/버전 관리 시스템으로 재정의한다. 서비스 생성/관리는 개발 기초 수준 사용자도 쓸 수 있도록 YAML과 nginx config 직접 편집을 고급 모드로 숨기고 폼 기반 자동화로 구성한다.

## 변경 파일

- `docs/docker-infra-development-todo.md`: 기존 Job/외부 Harbor/GitLab build 중심 TODO를 삭제하고, nginx 고정·Job 제거·내장 Harbor 백업 시스템·서비스 wizard·operation log 기준 전체 백로그로 재작성했다.
- `docs/docker-infra-remaining-todo.md`: 남은 작업만 확인할 수 있는 실행 체크리스트를 별도 파일로 추가했다.
- `devlog.md`: 059 작업 요약 row를 추가했다.
- `devlog/2026-05-08/059-rewrite-todo-for-simplified-product-flow.md`: 상세 devlog를 추가했다.

## 검증

- `git diff --check`로 문서 변경의 whitespace 오류가 없음을 확인했다.
- `wc -l`과 `rg`로 전체 TODO/남은 TODO 파일이 생성되었고, Job 제거, 내장 Harbor 백업 시스템, 고급 모드, operation log 기준이 포함되어 있음을 확인했다.
