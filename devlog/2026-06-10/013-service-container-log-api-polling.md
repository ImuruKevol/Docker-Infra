# 서비스 컨테이너 로그 조회를 API 폴링 방식으로 분리

## 사용자 요청

- 확인 대상 서비스: 명함 관리 서비스의 app 컨테이너
- 로그 메뉴 선택 시 "로그 스트림 응답이 없습니다."가 표시되는 문제를 확인하고 수정

## 변경 파일

- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-06-10/013-service-container-log-api-polling.md`

## 변경 내용

- 컨테이너 로그 조회용 `service_container_logs_snapshot` API를 추가했다.
- 로그 모달이 WebSocket 터미널 세션 대신 `docker logs --tail` 스냅샷 API를 2초 주기로 호출하도록 변경했다.
- 로그 화면 검증 테스트를 새 API 폴링 경로 기준으로 갱신했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.services/api.py src/app/page.services/socket.py src/model/struct/nodes_terminal.py` 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_container_context_log_streaming_is_wired` 통과
- WIZ `main` 프로젝트 빌드 성공
- 개발 사이트에서 명함 관리 서비스 app 컨테이너 로그 모달 확인
  - 로그 API 응답: 200
  - 상태 표시: 로그 수신 중
  - "로그 스트림 응답이 없습니다." 미표시
  - 터미널 연결 오류 문구 미표시
