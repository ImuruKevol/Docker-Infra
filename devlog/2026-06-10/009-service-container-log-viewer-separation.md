# 컨테이너 로그를 터미널이 아닌 전용 로그 뷰어로 분리

## 사용자 요청

리뷰 ID: `nwhvoiagnbhoffjzgjhavqczqbjooatm`

리뷰 내용:
- 로그를 선택하니 그냥 터미널이 연결되고, 로그는 제대로 뜨지 않으며 입력도 안 되는 터미널처럼 보인다.

## 변경 파일

- `src/app/page.services/view.pug`
  - 컨테이너 로그를 xterm 터미널 모달이 아닌 별도 로그 뷰어 모달로 표시하도록 추가했다.
  - 로그 뷰어는 텍스트 로그 영역, 다시 보기, 지우기, 닫기 버튼만 제공한다.
- `src/app/page.services/view.ts`
  - `containerLogs*` 상태와 WebSocket 연결 흐름을 분리했다.
  - 로그 메뉴 선택 시 터미널 모달을 열지 않고 `create_logs` 이벤트로 로그 스트림을 시작한다.
  - 수신 로그를 텍스트로 누적하고 자동으로 하단으로 스크롤한다.
- `src/app/page.services/socket.py`
  - 전용 `create_logs`/`close_logs` 이벤트를 추가하고 `log_status`, `log_output`, `log_exit`, `log_error` 이벤트로 로그 전용 스트림을 보낸다.
- `tests/api/test_services_preflight.py`
  - 로그 메뉴가 전용 로그 뷰어와 전용 socket 이벤트에 연결되는 정적 계약을 보강했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.services/socket.py src/model/struct/nodes_terminal.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_container_context_log_streaming_is_wired` 통과.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `build/dist/build/main.js`에 `create_logs`, `log_output`, `services-container-logs-output` 반영 확인.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 포함한 `curl -I https://infra-dev.nanoha.kr/dashboard`가 `200 OK`로 응답함을 확인했다.

## 남은 확인

- 실제 로그인 브라우저에서 실행 중인 컨테이너 로그 스트림 출력은 테스트 계정/대상 컨테이너가 없어 수동 확인하지 못했다.
