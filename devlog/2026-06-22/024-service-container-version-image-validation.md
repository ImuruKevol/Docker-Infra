# 버전 변경 모달 이미지 존재 검증 버튼 추가

- **ID**: 024
- **날짜**: 2026-06-22
- **유형**: UX/API 기능 추가
- **리뷰 ID**: iygagnmtnjaerziptyiubkzcapwlmyjy

## 작업 요약
서비스 상세의 컨테이너 `버전 변경` 모달에 입력한 tag/digest 이미지가 실제 registry manifest로 확인되는지 검증하는 전용 버튼을 추가했다.
검증은 Compose 파일 변경이나 컨테이너 재기동 없이 대상 서버의 Docker CLI로 `docker manifest inspect`를 실행해 결과만 모달에 표시한다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

버전 변경 모달에 해당 이미지의 해당 버전(태그)에 해당하는 이미지가 실제 존재하는지 확인하는 검증 전용 버튼을 추가해줘.

## 리뷰 요약

- 리뷰 ID: iygagnmtnjaerziptyiubkzcapwlmyjy
- 제목: 서비스 관리 상세 - 편의 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/access
```

## 변경 파일 목록
- `src/app/page.services/view.pug`: 버전 입력 옆 `이미지 검증` 버튼과 검증 결과 표시 영역 추가.
- `src/app/page.services/view.ts`: 검증 busy/result 상태, 입력 변경 시 결과 초기화, `service_container_version_validate` 호출 로직 추가.
- `src/app/page.services/api.py`: `service_container_version_validate` API 함수 추가.
- `src/model/struct/services_update.py`: 버전 변경 대상 컨텍스트 공통화와 `validate_container_version_image` manifest 검증 로직 추가.
- `src/model/struct/local_command_catalog.py`, `config/docker_infra.py`: `docker.image.manifest.inspect` 로컬 실행 명령과 allowlist 추가.
- `tests/api/test_services_preflight.py`: 검증 버튼/API/manifest 명령 연결 정적 계약 검증 추가.
- `devlog.md`, `devlog/2026-06-22/024-service-container-version-image-validation.md`: 작업 이력 추가.

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_update.py src/model/struct/local_command_catalog.py src/app/page.services/api.py config/docker_infra.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_container_version_change_is_wired`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_local_executor.LocalExecutorStaticContractTest`
- 성공: `wiz_project_build(clean=true)`
- 성공: `git diff --check`
- 참고: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest` 전체 실행은 기존 `page.service.create` 템플릿 문구 기대값 불일치로 `test_service_create_preflight_contract_is_wired`, `test_service_create_supports_templates_and_draft_sources` 2건이 실패했다.
