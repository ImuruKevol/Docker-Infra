# 컨테이너 버전 변경 런타임 이미지 불일치 재적용 보정

## 사용자 원문

서비스 상세의 구성 탭에는 버전이 latest라고 표시되어있는 상태에서 버전 변경 모달에서 260622라고 입력 후 검증 후 변경 적용을 했는데 아래 에러 메세지가 표시되고 있어.

---
입력한 버전이 현재 버전과 같습니다. 같은 tag의 digest 갱신이 필요하면 강제 다시 불러오기를 선택하세요.

## 배경

ReviewOps 리뷰 ID: `iygagnmtnjaerziptyiubkzcapwlmyjy`

이전 실패 경로에서 Compose 파일은 이미 목표 tag로 변경됐지만 실제 컨테이너 런타임 이미지는 아직 이전 tag일 수 있다. 기존 버전 변경 로직은 Compose 파일의 image만 비교해 `next_image == previous_image`이면 같은 버전으로 판단했기 때문에, 화면/런타임은 `latest`인데 Compose 파일만 `260622`인 불일치 상태에서 적용이 막힐 수 있었다.

## 변경 파일

- `src/model/struct/services_update.py`
  - 컨테이너 버전 변경 컨텍스트에 실제 런타임 이미지(`runtime_image`)를 함께 담도록 했다.
  - 목표 이미지와 런타임 이미지가 다른 경우 `SERVICE_IMAGE_VERSION_UNCHANGED`로 막지 않고 재적용하도록 했다.
  - Compose 파일은 이미 목표 tag여도 런타임이 다른 tag이면 `apply_force`를 켜서 compose/swarm 적용 경로가 컨테이너를 다시 만들도록 했다.
  - 같은 tag의 digest 갱신만 필요한 경우는 기존처럼 강제 다시 불러오기 체크가 필요하도록 유지했다.
- `tests/api/test_services_preflight.py`
  - 컨테이너 버전 변경 정적 계약 테스트에 런타임 이미지 불일치 재적용 토큰을 추가했다.
- `devlog.md`
  - 이번 작업 요약 행을 추가했다.
- `devlog/2026-06-23/007-service-container-version-runtime-mismatch-apply.md`
  - 이번 작업 상세 기록을 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_update.py src/model/struct/local_command_catalog.py config/docker_infra.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_container_version_change_is_wired`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_local_executor.LocalExecutorStaticContractTest`
- `git diff --check -- src/model/struct/services_update.py tests/api/test_services_preflight.py`
- `wiz_project_build(clean=false)`

모두 통과했다.

## 남은 리스크

실제 `notedown-server` 운영 컨테이너의 버전 변경 명령은 실행하지 않았다. 런타임 재적용 시 Swarm manager 상태, registry 인증, Harbor 접근 권한 문제는 별도로 실패할 수 있다.
