# Compose 파일 선택 모달 기본 홈 경로와 직접 경로 이동 추가

- 날짜: 2026-05-07
- ID: 031

## 사용자 요청

Compose 파일 선택 모달이 기본적으로 `/`를 보여주지 말고, 선택한 서버에 등록된 사용자의 홈 디렉토리를 기본값으로 열어야 한다는 요청이었다. 또한 경로를 직접 입력해서 원하는 위치로 바로 이동할 수 있어야 했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/031-compose-browser-home-path.md`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/model/struct/nodes_runtime.py`
- `tests/e2e/specs/servers.spec.ts`

## 작업 내용

- 서버 파일 브라우저 기본 경로를 하드코딩된 `/`에서 선택 서버 사용자의 홈 디렉토리로 바꿨다.
- 원격 서버는 SSH로 `$HOME`을 조회하고, 실패하면 `root`는 `/root`, 그 외 계정은 `/home/{username}`으로 보수적으로 fallback 하도록 했다.
- Compose 선택 모달에 경로 입력창과 `이동`, `홈` 버튼을 추가해 절대 경로와 `~/...` 형식, 현재 위치 기준 상대 경로 이동을 지원했다.
- 모달이 열릴 때 응답 전까지 `/`가 잠깐 보이던 상태를 없애고, 홈 디렉토리 확인 중이라는 로딩 상태를 먼저 보여주도록 정리했다.
- 서버 화면 E2E에 Compose 브라우저가 홈 디렉토리에서 시작하고 `/tmp`로 직접 이동할 수 있는 시나리오를 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_runtime.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_wiz_structure_contract.py tests/api/test_node_reporter.py tests/api/test_playwright_setup.py tests/api/test_ssh_managed.py`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- 인증된 API로 `POST /wiz/api/page.servers/browse_files`를 `path=''`로 호출해 기본 경로가 `/root`로 반환되는 것 확인
- `npm run e2e -- tests/e2e/specs/servers.spec.ts`: 환경 조건으로 skip
- `git -C /root/docker-infra/project/main diff --check`: 통과
