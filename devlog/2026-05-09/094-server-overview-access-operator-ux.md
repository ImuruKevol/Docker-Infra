# 094. 서버 관리 개요 UX와 컨테이너 삭제, 운영형 access 화면 적용

## 요청

서버 관리 화면에서 이미 Swarm으로 연결된 상태면 연결 버튼을 보이지 않게 하고, 개요 탭의 개발자 중심 정보를 일반 관리자도 이해할 수 있도록 등록된 서비스 중심으로 바꿔달라는 요청. 컨테이너 삭제 기능 추가와 `/access` 페이지의 개발/테스트용 정보 제거, 업로드된 `src/assets/bg-login.png` 최적화 후 운영 서비스형 화면 적용도 함께 요청됨.

## 변경 파일

- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/model/struct/nodes_runtime.py`
- `src/model/struct/local_command_catalog.py`
- `src/app/page.access/view.pug`
- `src/app/page.access/view.ts`
- `src/assets/bg-login.png`
- `src/assets/bg-login.optimized.webp`
- `tests/e2e/specs/access.spec.ts`
- `tests/e2e/specs/servers.spec.ts`

## 작업 내용

- Swarm 연결 완료 서버는 `Swarm 연결` 버튼을 숨기고, 로직에서도 이미 연결된 서버에 재연결을 실행하지 않도록 막았다.
- 서버 개요 탭의 등록 영역을 `등록된 서비스` 기준으로 재구성했다. 서비스별 상태, 사용 중인 포트, 실행/재시작/중지 일괄 액션, 서비스 상세 바로가기를 중심으로 표시한다.
- 미등록 컨테이너 목록에 삭제 버튼을 추가하고, `docker rm -f` 기반 컨테이너 삭제 액션을 로컬/원격 실행 경로에 연결했다.
- `/access` 화면에서 DB, Runtime, Mode, SameSite 같은 개발/테스트 문구를 제거하고 운영 콘솔 접속 화면으로 재구성했다.
- `bg-login.png`를 1920px 폭 WebP로 최적화해 `bg-login.optimized.webp`를 추가했고, 빌드 산출물에 원본 대용량 PNG가 포함되지 않도록 원본 파일은 제거했다. 배경 파일 크기는 약 8.6MB에서 약 278KB로 줄었다.

## 검증

- `wiz_project_build(clean=false)`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/local_command_catalog.py src/model/struct/nodes_runtime.py`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_playwright_setup tests.api.test_auth_setup.AuthSetupStaticContractTest`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract`: 실패. 이번 작업 파일인 `local_command_catalog.py`는 300줄 제한 안으로 맞췄으나, 기존 대형 파일 `domains.py`, `services_deploy.py`, `services_flow.py`, `services_preflight.py`, `services_wizard.py`, `webserver.py`가 300줄 제한을 초과해 실패했다.
