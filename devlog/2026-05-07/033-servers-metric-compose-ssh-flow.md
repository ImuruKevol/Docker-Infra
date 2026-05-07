# 서버 상세 metric 응답 경량화와 Compose 경고/SSH 등록 흐름 보강

- 날짜: 2026-05-07
- ID: 033

## 사용자 요청

- `cached_detail`, `refresh_metrics` API 응답에 불필요한 정보가 많으니 꼭 필요한 정보만 보내도록 줄여야 했다.
- 로컬 컨테이너 `stop`, `restart` 실행 시 `destructive local command가 allowlist에 없습니다.` 오류가 나는 문제를 해결해야 했다.
- Compose 파일 선택 모달은 숨김 파일과 숨김 디렉토리를 기본적으로 감추고, 토글로만 보이게 해야 했다.
- Compose 파일 등록에서 `container_name`, `healthcheck` 관련 검증 실패는 즉시 차단이 아니라 경고 후 재확인 흐름으로 바꿔야 했다.
- 서버 추가/수정이 여전히 실패하던 `mini2` 서버를 기준으로 실제 SSH 등록 경로를 확인하고 고쳐야 했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/033-servers-metric-compose-ssh-flow.md`
- `config/docker_infra.py`
- `src/model/struct/compose_rules.py`
- `src/model/struct/compose_validator.py`
- `src/model/struct/services.py`
- `src/model/struct/nodes_runtime.py`
- `src/model/struct/nodes_view.py`
- `src/model/struct/ssh_managed.py`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/route/api-nodes/controller.py`

## 작업 내용

- `refresh_metrics`는 전체 서버 객체를 다시 보내지 않고 `node_id`, `latest_metric`만 반환하도록 줄였다. 서버 상세 화면도 이 최소 payload를 기존 선택 상태에 병합하도록 바꿨다.
- `cached_detail`은 상세 렌더에 필요한 `node`, `summary`, `service_groups`, `unmanaged_containers`만 유지하도록 정리했고, flattened container 중복 응답은 제거했다.
- 로컬 destructive command allowlist 기본값에 `docker.container.start`, `docker.container.stop`, `docker.container.restart`를 포함해 별도 env 설정이 없어도 컨테이너 제어가 막히지 않도록 했다.
- Compose 파일 브라우저는 숨김 파일/디렉토리를 기본적으로 제외하고, `숨김 보기/감추기` 토글 버튼으로만 전환되게 바꿨다.
- Compose import는 `FORBIDDEN_CONTAINER_NAME`, `HEALTHCHECK_REQUIRED`를 경고 코드로 취급하도록 validator와 services 흐름을 보강했다. 첫 요청에서는 경고 모달을 띄우고, 재확인 시 `allow_warnings`를 전달해 계속 진행할 수 있게 했다.
- `page.servers` API와 `/api/nodes` route는 예외 클래스가 reload 과정에서 달라져도 JSON 오류 응답을 유지하도록 generic fallback을 추가했다.
- SSH 비밀번호 검증이 실제 터미널과 다르게 실패하던 원인은 PTY 세션이 controlling terminal 없이 실행되던 구조였다. `ssh_managed.py`에서 `setsid + TIOCSCTTY`로 PTY를 정상화해 비밀번호 프롬프트를 안정적으로 처리하도록 수정했다.
- `mini2` 서버를 실제로 다시 등록해 관리용 SSH key와 fingerprint가 DB에 저장되는 것까지 확인했다.

## 검증

- `python -m py_compile src/model/struct/nodes_runtime.py src/app/page.servers/api.py src/route/api-nodes/controller.py`: 통과
- `python -m unittest tests/api/test_wiz_structure_contract.py tests/api/test_node_reporter.py tests/api/test_compose_validator.py`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- live API 검증:
  - `/wiz/api/page.servers/refresh_metrics`: `latest_metric`, `node_id`만 반환하는 것 확인
  - `/wiz/api/page.servers/cached_detail`: `node`, `summary`, `service_groups`, `unmanaged_containers`만 반환하는 것 확인
  - `/wiz/api/page.servers/container_action`: allowlist 오류 대신 JSON `409 CONTAINER_ACTION_FAILED`로 응답하는 것 확인
  - `/wiz/api/page.servers/register_slave`: `mini2` 수정 등록 성공, 관리용 SSH key/fingerprint 저장 확인
  - `/api/nodes`: 동일 정보로 등록 요청 성공 확인
  - `/wiz/api/page.servers/browse_files`: 기본 홈 경로가 `/root`, 숨김 파일 기본 비노출 및 토글 시 노출 확인
  - `/wiz/api/page.servers/import_compose_service`: `FORBIDDEN_CONTAINER_NAME`, `HEALTHCHECK_REQUIRED` 조합이 `COMPOSE_VALIDATION_WARNING`과 `can_continue=true`로 내려오는 것 확인
- `git -C /root/docker-infra/project/main diff --check`: 통과
