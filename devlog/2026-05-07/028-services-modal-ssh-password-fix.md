# 서비스 화면 모달 UX와 SSH 비밀번호 프롬프트 처리 보강

- 날짜: 2026-05-07
- ID: 028

## 사용자 요청

`/services` 화면 작업을 이어서 진행하고, 서버 정보 수정 및 추가 시 `/var/log/wiz/docker-infra`에는 `SSH 비밀번호로 서버에 접속할 수 없습니다`가 남지만 정작 화면에는 `서버 정보를 수정할 수 없습니다.`만 보여주는 문제를 수정해달라는 요청이었다. 사용자가 같은 정보로 터미널에서 직접 접속하면 연결이 되므로, SSH 연결 로직 자체에도 문제가 있을 가능성을 함께 조사해야 했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/028-services-modal-ssh-password-fix.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-runtime.md`
- `src/app/page.access/view.pug`
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.ts`
- `src/model/struct/nodes.py`
- `src/model/struct/nodes_join.py`
- `src/model/struct/nodes_manage.py`
- `src/model/struct/nodes_registry.py`
- `src/model/struct/nodes_runtime.py`
- `src/model/struct/services.py`
- `src/model/struct/services_runtime.py`
- `src/model/struct/services_shared.py`
- `src/model/struct/ssh_executor.py`
- `src/model/struct/ssh_managed.py`
- `tests/api/test_playwright_setup.py`
- `tests/api/test_ssh_managed.py`
- `tests/e2e/specs/services.spec.ts`

## 작업 내용

- `/services` 화면을 목록 + 상세 구조로 재편하고, 서비스 생성 입력을 고정 패널에서 modal wizard로 옮겼다.
- 서비스 생성 modal은 `기본 웹 서비스`와 `직접 Compose 작성` 두 흐름으로 시작하도록 바꿨고, Compose 원문 편집은 고급 설정을 연 경우에만 수정할 수 있게 했다.
- 선택한 서비스의 현재 Compose, 연결된 domain, Compose version 이력, 관련 job 목록을 상세 영역에서 함께 볼 수 있게 했다.
- 서비스 디렉토리 파일 브라우저와 파일 내용 미리보기 modal을 추가했다.
- backend에 `detail_service`, `browse_files`, `read_file` API와 이를 위한 `services_runtime`, `services_shared` model을 추가했다.
- 서버 등록/수정 실패 시 page API가 cross-module 예외를 generic 500으로 흘려보내지 않도록 `page.servers/api.py`에 공통 예외 payload 처리 fallback을 추가했다.
- 서버 등록/수정 모달은 `data.message`가 없더라도 `check.reason`을 우선 표시하도록 바꿔 generic 문구만 뜨는 경우를 줄였다.
- SSH 비밀번호 로그인 helper는 prompt 문자열이 여러 chunk로 쪼개져 들어와도 감지할 수 있도록 rolling buffer 방식으로 수정했고, `password`, `passphrase`, `verification code`, `otp` 계열 prompt를 함께 인식하게 했다.
- SSH executor는 known_hosts 경로 준비 시 `env`를 일관되게 전달하도록 수정했다.
- split password prompt 회귀를 막기 위해 `test_ssh_managed.py`를 추가했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services.py src/model/struct/services_runtime.py src/model/struct/services_shared.py src/model/struct/ssh_managed.py src/model/struct/ssh_executor.py src/model/struct/nodes.py src/model/struct/nodes_registry.py src/model/struct/nodes_manage.py src/model/struct/nodes_join.py src/model/struct/nodes_runtime.py src/app/page.services/api.py src/app/page.servers/api.py tests/api/test_ssh_managed.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_wiz_structure_contract.py tests/api/test_playwright_setup.py tests/api/test_node_reporter.py tests/api/test_ssh_managed.py`: 통과
- `DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001 DOCKER_INFRA_TEST_PASSWORD='____' npm run e2e -- tests/e2e/specs/servers.spec.ts tests/e2e/specs/services.spec.ts`: 통과
- `git -C /root/docker-infra/project/main diff --check`: 통과

## 남은 점

- 실제 실패했던 대상 서버를 같은 credential로 live 재검증한 것은 아니다. 이번 수정은 prompt split과 예외 전달 경로를 바로잡는 데 초점을 맞췄고, 현장 서버 기준 재시도 결과는 별도로 확인이 필요하다.
- `/services`의 deploy/rollback, 실시간 job log streaming, 파일 생성/업로드/다운로드는 아직 후속 작업이다.
