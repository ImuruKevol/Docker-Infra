# 컨테이너 버전 변경 Compose 네트워크 컨텍스트 보정

## 사용자 원문

여전히 화면에서 "컨테이너 버전을 변경할 수 없습니다." 에러가 뜨고 있어.

## 배경

ReviewOps 리뷰 ID: `iygagnmtnjaerziptyiubkzcapwlmyjy`

이전 적용 단계에서 `notedown-server`의 Compose 파일은 `docker_infra_overlay` 네트워크를 사용하고 있었지만, 버전 변경 검증에는 서비스 저장 정책에서 계산한 compose/bridge 컨텍스트가 전달되어 `docker_infra_bridge network만 사용할 수 있습니다` 검증 오류가 발생할 수 있었다.

## 변경 파일

- `src/model/struct/services_update.py`
  - Compose 파일의 root/service networks를 읽어 `docker_infra_overlay`면 swarm/overlay, `docker_infra_bridge`면 compose/bridge로 검증 컨텍스트를 재계산하도록 추가했다.
  - 컨테이너 버전 변경 적용 경로가 보정된 컨텍스트를 사용하도록 했다.
  - 적용 이력 생성 시 누락될 수 있던 `service_id`, `container_id` 지역 변수를 명시했다.
- `tests/api/test_services_preflight.py`
  - 컨테이너 버전 변경 정적 계약 테스트에 Compose 네트워크 컨텍스트 보정 토큰을 추가했다.
- `devlog.md`
  - 이번 작업 요약 행을 추가했다.
- `devlog/2026-06-23/003-service-container-version-compose-network-context.md`
  - 이번 작업 상세 기록을 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_update.py src/model/struct/local_command_catalog.py config/docker_infra.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_container_version_change_is_wired`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_local_executor.LocalExecutorStaticContractTest`
- `git diff --check -- src/model/struct/services_update.py tests/api/test_services_preflight.py`
- `wiz_project_build(clean=false)`

모두 통과했다.

## 남은 리스크

실제 `notedown-server` 운영 컨테이너의 버전 변경 명령은 실행하지 않았다. 실제 적용 시 Swarm manager 상태, registry 인증, Harbor 접근 권한 문제는 런타임에서 별도로 실패할 수 있다.
