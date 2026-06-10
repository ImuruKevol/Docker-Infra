# 서비스 상세 컨테이너 로그 스트리밍 메뉴 추가

## 사용자 요청

작업 시작

리뷰 ID: `nwhvoiagnbhoffjzgjhavqczqbjooatm`

리뷰 내용:
- 서비스 상세에서 각 컨테이너들의 컨텍스트 메뉴에 로그 메뉴도 추가해줘.
- `docker logs` 명령어로 출력되는 로그들을 계속 `-f` 옵션을 준 것처럼 확인할 수 있어야 해.

## 변경 파일

- `src/app/page.services/view.pug`
  - 외부 오픈/내부 전용 컨테이너 컨텍스트 메뉴에 `로그` 항목을 추가했다.
  - 기존 xterm 모달의 연결 버튼 표시를 터미널/로그 모드별로 바꿨다.
- `src/app/page.services/view.ts`
  - 컨테이너 로그 모드를 추가하고, 로그 보기/재연결/상태 문구를 터미널 모달과 함께 사용하도록 연결했다.
  - 로그 모드에서는 WebSocket 생성 요청에 `mode: logs`, `tail: 200`을 전달하고 입력 전송은 막았다.
- `src/app/page.services/socket.py`
  - 컨테이너 세션 생성 시 `terminal`/`logs` 모드를 구분하고 로그 모드에서 `create_container_logs_session`을 호출하도록 했다.
- `src/model/struct/nodes_terminal.py`
  - 컨테이너 존재 확인과 `docker logs --tail 200 -f` 기반 PTY 세션 생성을 추가했다.
- `tests/api/test_services_preflight.py`
  - 컨텍스트 메뉴 로그 스트리밍 연결 계약을 정적 테스트로 추가했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.services/socket.py src/model/struct/nodes_terminal.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_container_context_log_streaming_is_wired` 통과.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 포함한 `curl -I https://infra-dev.nanoha.kr/dashboard`가 `200 OK`로 응답함을 확인했다.
- 기존 `test_service_detail_operator_runtime_summary_is_wired` 단일 실행은 현재 작업트리의 비관련 정적 계약 불일치(`Compose 원문 및 Nginx 설정` 문구 기대값)로 실패했다.
