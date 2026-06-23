# 이미지 검증 Compose 제한 해제와 런타임 image fallback 추가

- **ID**: 029
- **날짜**: 2026-06-22
- **유형**: 버그 수정
- **리뷰 ID**: iygagnmtnjaerziptyiubkzcapwlmyjy

## 작업 요약
버전 변경 모달의 이미지 검증 API가 실제 버전 변경 적용과 같은 Compose 전용 컨텍스트를 사용해 비 Compose 판정 서비스에서 검증 전에 실패하던 문제를 수정했다.
검증 전용 경로는 Compose 배포 제한을 적용하지 않고, Compose 정보를 사용할 수 없거나 Compose 배포가 아니면 런타임 컨테이너의 image ref를 기준으로 입력 tag/digest의 manifest를 확인하도록 fallback을 추가했다.
실제 버전 변경 적용은 기존처럼 Compose 배포 서비스에서만 동작하도록 유지했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

아래와 같이 에러가 뜨는데 해결해줘. 참고로 notedown-server 서비스에서 260622 버전으로 이미지 검증을 눌러봤어. harbor에는 공개로 올라가있는 것을 확인했고.

이미지 확인 실패
컨테이너별 버전 변경은 Docker Compose 배포 서비스에서만 사용할 수 있습니다.

## 리뷰 요약

- 리뷰 ID: iygagnmtnjaerziptyiubkzcapwlmyjy
- 제목: 서비스 관리 상세 - 편의 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/access
```

## 변경 파일 목록
- `src/model/struct/services_update.py`: 이미지 검증용 컨텍스트에서 Compose 제한을 해제하고 런타임 컨테이너 image fallback 추가.
- `tests/api/test_services_preflight.py`: 검증 경로의 `require_compose=False`, 런타임 fallback, image source 계약 토큰 추가.
- `devlog.md`, `devlog/2026-06-22/027-service-container-version-validate-runtime-image.md`: 작업 이력 추가.

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_update.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_container_version_change_is_wired`
- 성공: `wiz_project_build(clean=false)`
- 성공: `git diff --check`
