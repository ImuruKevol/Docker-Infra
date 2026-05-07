# 전역 매크로 목록 버튼 위치 조정과 서버 상세 매크로 실행 로그 스트리밍 적용

- 날짜: 2026-05-07
- ID: 040

## 사용자 요청

- 매크로 화면에서 매크로 추가 버튼의 위치를 왼쪽의 매크로 목록 위쪽으로 이동해줘.
- 서버 상세에서 매크로 탭에서 매크로 실행 시 출력되는 내용을 스트리밍으로 가져오도록 수정해줘.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/040-macros-button-streaming.md`
- `src/app/page.macros/view.pug`
- `src/app/page.servers/view.ts`
- `src/model/struct/macros_runner.py`
- `tests/api/test_server_macros.py`

## 작업 내용

- 전역 매크로 페이지 헤더의 `매크로 추가` 버튼을 제거하고, 왼쪽 매크로 목록 카드 상단으로 옮겼다.
- 서버 상세 매크로 실행은 요청-응답 한 번에 끝내지 않고, job을 즉시 `running` 상태로 반환한 뒤 background task에서 실제 스크립트를 실행하도록 바꿨다.
- local/remote macro 실행 모두 `subprocess.Popen` 기반으로 바꾸고 stdout/stderr를 줄 단위로 `job_logs`에 즉시 적재하도록 정리했다.
- 서버 상세 화면은 매크로 실행 후 `/api/jobs/{job_id}`를 짧은 주기로 poll 하면서 로그와 상태를 계속 갱신하도록 수정했다.
- 서버 변경, 매크로 선택 변경, 화면 종료 시 이전 macro polling timer를 끊어서 stale polling이 남지 않게 정리했다.
- job 상태 badge에 `running`, `canceled` 라벨과 스타일을 추가했다.
- live macro 테스트는 즉시 완료를 기대하지 않고 job 종료까지 기다린 뒤 최종 로그를 검증하도록 갱신했다.

## 검증

- `cd /root/docker-infra/project/main && /opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/macros_runner.py tests/api/test_server_macros.py`: 통과
- `cd /root/docker-infra/project/main && /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract tests.api.test_server_macros.ServerMacrosStaticContractTest`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `systemctl restart wiz.docker-infra`: 완료
- `curl http://127.0.0.1:3001/api/system/health`: 서버 기동 확인
- `cd /root/docker-infra/project/main && DOCKER_INFRA_TEST_PASSWORD='____' /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosLiveFlowTest`: 통과
- `cd /root/docker-infra/project/main && DOCKER_INFRA_TEST_PASSWORD='____' DOCKER_INFRA_BASE_URL='http://127.0.0.1:3001' npx playwright test tests/e2e/specs/servers.spec.ts`: 5 passed
- slow macro live check: 실행 직후 `running`, 중간 poll에서 `start` 로그 확인, 최종 poll에서 `middle`, `end` 로그 확인
- `cd /root/docker-infra/project/main && git diff --check`: 통과
