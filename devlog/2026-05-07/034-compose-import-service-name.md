# Compose 파일 등록 모달에 서비스 이름 입력 추가

- 날짜: 2026-05-07
- ID: 034

## 사용자 요청

- Compose 파일로 서비스를 등록할 경우 서비스 이름은 입력을 받아야 한다는 요청이었다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/034-compose-import-service-name.md`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `tests/e2e/specs/servers.spec.ts`

## 작업 내용

- 서버 화면의 Compose 파일 선택 모달에 `서비스 이름` 입력 필드를 추가했다.
- 모달을 열 때는 컨테이너 이름이나 runtime 서비스명이 있으면 기본값으로 채우고, 없으면 빈 값으로 시작하게 정리했다.
- 등록 버튼은 서비스 이름이 비어 있으면 비활성화되도록 바꿨고, 등록 직전에도 이름 검사를 한 번 더 수행한다.
- Compose import API 호출 시 입력한 서비스 이름을 `suggested_name`과 `suggested_namespace`의 기준값으로 함께 전달하도록 변경했다.
- Playwright 서버 화면 테스트에 Compose 모달 서비스 이름 입력 확인을 추가했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)`: 통과
- `git -C /root/docker-infra/project/main diff --check`: 통과
- `DOCKER_INFRA_BASE_URL=http://127.0.0.1:3001 DOCKER_INFRA_TEST_PASSWORD=... npx playwright test tests/e2e/specs/servers.spec.ts`: 2 passed
