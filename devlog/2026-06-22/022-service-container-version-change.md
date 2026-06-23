# 서비스 상세 컨테이너별 버전 변경 기능 추가

- **ID**: 022
- **날짜**: 2026-06-22
- **유형**: UX/API 기능 추가
- **리뷰 ID**: iygagnmtnjaerziptyiubkzcapwlmyjy

## 작업 요약
서비스 상세 화면의 컨테이너 컨텍스트 메뉴에 `버전 변경` 액션을 추가했다.
버전 입력 모달에서 볼륨에 저장되지 않은 데이터 손실 경고와 같은 tag 강제 재불러오기 옵션을 제공하고, 적용 시 해당 Compose 서비스만 `docker compose up -d --no-deps`로 재기동하도록 연결했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: iygagnmtnjaerziptyiubkzcapwlmyjy
- 제목: 서비스 관리 상세 - 편의 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/access

## 리뷰어 요청 내용

- 각 컨테이너마다 있는 컨텍스트 메뉴에 "버전 변경" 기능 추가 필요. 해당 버튼을 누르면 버전을 입력할 수 있는 간단한 모달이 나오고, 버전 변경 시 볼륨에 저장되지 않은 데이터들은 날아갈 수 있다는 경고들을 표시해줘.
  - 확인을 누르면 해당 서비스의 docker-compose.yaml 파일에서 해당 컨테이너의 버전 부분을 입력한 버전으로 변경 후 해당 서버에서 "docker compose up -d" 명령어를 통해 버전이 변경된 컨테이너만 다시 시작할 수 있도록 해줘.
- 이 때 체크박스를 하나 추가해서, 기존과 버전명은 같지만 dizest id값이 다를 때 강제로 다시 불러올 수 있도록 하는 기능도 필요해.
```

## 변경 파일 목록
- `src/app/page.services/view.pug`: 컨테이너 메뉴의 `버전 변경` 버튼과 버전 입력/경고/강제 재불러오기 모달 추가.
- `src/app/page.services/view.ts`: 버전 변경 모달 상태, 제출 로직, API 호출, 작업 라벨 추가.
- `src/app/page.services/api.py`: `service_container_version_change` API 엔드포인트 추가.
- `src/model/struct/services_update.py`: Compose image 버전 변경, 변경 이력 저장, 대상 컨테이너 Compose 서비스 재기동 로직 추가.
- `src/model/struct/local_command_catalog.py`, `config/docker_infra.py`: 로컬 master에서 대상 Compose 서비스만 up/pull할 수 있는 허용 명령 추가.
- `src/model/struct/infra_catalog_registry.py`: 컨테이너 버전 변경 operation 라벨 추가.
- `tests/api/test_services_preflight.py`: UI/API/model/local command 연결 정적 계약 검증 추가.
- `devlog.md`, `devlog/2026-06-22/022-service-container-version-change.md`: 작업 이력 추가.

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_update.py src/model/struct/local_command_catalog.py src/app/page.services/api.py config/docker_infra.py src/model/struct/infra_catalog_registry.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_container_version_change_is_wired`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_local_executor.LocalExecutorStaticContractTest`
- 성공: `wiz_project_build(clean=true)`
- 참고: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest` 전체 실행은 기존 `page.service.create` 템플릿 문구 기대값 불일치로 `test_service_create_preflight_contract_is_wired`, `test_service_create_supports_templates_and_draft_sources` 2건이 실패했다.
