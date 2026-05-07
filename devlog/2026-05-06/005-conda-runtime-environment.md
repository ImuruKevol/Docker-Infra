# Docker Infra conda 실행 환경 명시

- **ID**: 005
- **날짜**: 2026-05-06
- **유형**: 문서/설정 업데이트

## 사용자 원 요청

사용자가 Docker Infra 작업에 사용할 conda 환경 정보를 제공했고, 앞으로 아래 환경을 사용하도록 TODO나 Codex 설정파일 등에 명시해 달라고 요청했다.

- Python: `/opt/conda/envs/docker-infra/bin/python`
- WIZ: `/opt/conda/envs/docker-infra/bin/wiz`

## 작업 요약

프로젝트용 `AGENTS.md`를 추가해 Codex가 사용할 Python/WIZ 실행 경로와 secret handling 규칙을 명시했다. 실제 개발 TODO 문서에도 실행 환경 섹션을 추가해 자동화, 테스트, 빌드 명령이 `docker-infra` conda 환경의 실행 파일을 우선 사용하도록 기록했다.

## 변경 파일 목록

### Codex 설정

- `AGENTS.md`: Docker Infra conda 환경 경로와 민감 설정 파일 처리 규칙 추가

### 프로젝트 문서

- `docs/docker-infra-development-todo.md`: 실행 환경 섹션 추가

### 작업 기록

- `devlog.md`: 2026-05-06 005 항목 추가
- `devlog/2026-05-06/005-conda-runtime-environment.md`: 상세 작업 기록 추가

## 검증

- conda 환경 Python 경로 확인: `/opt/conda/envs/docker-infra/bin/python --version` → Python 3.14.4
- conda 환경 WIZ 경로 확인: `/opt/conda/envs/docker-infra/bin/wiz --version` → season 2.5.2
- API 테스트를 conda 환경 Python으로 실행: 5개 중 3개 통과, live API 2개는 서버 URL 미설정으로 skip
- WIZ build를 conda 환경 WIZ로 실행: `wiz project build --project main` 성공
- `git diff --check` 통과 확인
- 테스트 중 생성된 `__pycache__` 삭제
