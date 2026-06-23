# 버전 변경 적용 전 이미지 검증 필수화

- **ID**: 030
- **날짜**: 2026-06-22
- **유형**: UX/API 안전장치 보강
- **리뷰 ID**: iygagnmtnjaerziptyiubkzcapwlmyjy

## 작업 요약
버전 변경 모달에서 이미지 검증이 성공한 현재 입력 버전일 때만 `변경 적용` 버튼이 활성화되도록 수정했다.
서버 측 `change_container_version`에서도 Compose 파일 수정 전에 대상 image ref의 manifest 검증을 다시 실행하고, 실패하면 Compose 파일을 변경하지 않고 거부하도록 보강했다.
Compose 배포 판정값만으로 변경 적용을 막지 않고, Compose 파일과 대상 Compose 서비스가 실제로 해석되면 적용 경로를 진행하도록 조정했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

- 당연하지만 버전 변경 시 이미지 검증이 되지 않으면 변경을 하지 못하도록 해야해.
- 변경 적용 버튼을 누르니 "컨테이너별 버전 변경은 Docker Compose 배포 서비스에서만 사용할 수 있습니다." 라는 에러가 떴어.

## 리뷰 요약

- 리뷰 ID: iygagnmtnjaerziptyiubkzcapwlmyjy
- 제목: 서비스 관리 상세 - 편의 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/access
```

## 변경 파일 목록
- `src/app/page.services/view.ts`: 이미지 검증 성공 결과가 현재 입력 버전과 일치할 때만 적용 가능하도록 UI guard 추가.
- `src/app/page.services/view.pug`: 적용 버튼 title에 검증 필요 상태 연결.
- `src/model/struct/services_update.py`: 변경 적용 전 manifest 검증 필수화와 Compose 판정 선제 차단 완화.
- `tests/api/test_services_preflight.py`: 적용 전 검증 필수화와 서버 검증 실패 차단 계약 토큰 추가.
- `devlog.md`, `devlog/2026-06-22/029-service-container-version-validate-runtime-image.md`, `devlog/2026-06-22/030-service-container-version-change-requires-validation.md`: 작업 이력 및 번호 충돌 정리.

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_update.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_container_version_change_is_wired`
- 성공: `wiz_project_build(clean=false)`
- 성공: `git diff --check`
- 참고: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest` 전체 실행은 기존 `page.service.create` 템플릿 문구 기대값 불일치로 `test_service_create_preflight_contract_is_wired`, `test_service_create_supports_templates_and_draft_sources` 2건이 실패했다.
