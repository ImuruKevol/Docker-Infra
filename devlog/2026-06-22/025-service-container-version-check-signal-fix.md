# 이미지 검증 결과 표시 signal 이름 오류 수정

- **ID**: 025
- **날짜**: 2026-06-22
- **유형**: 버그 수정
- **리뷰 ID**: iygagnmtnjaerziptyiubkzcapwlmyjy

## 작업 요약
버전 변경 모달의 이미지 검증 결과 표시 영역에서 존재하지 않는 `versionChangeCheckResult()`를 호출하던 템플릿 바인딩을 실제 signal 이름인 `versionCheckResult()`로 수정했다.
정적 계약 테스트의 기대 토큰도 동일하게 보정했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

이미지 검증을 누르고 이미지가 있다면 있다고 표시하고, 없으면 없다고 표시를 해야하는데 지금은 아무것도 안뜨고 있어. TypeError: ctx_r0.versionChangeCheckResult is not a function 에러가 뜨네

## 리뷰 요약

- 리뷰 ID: iygagnmtnjaerziptyiubkzcapwlmyjy
- 제목: 서비스 관리 상세 - 편의 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/access
```

## 변경 파일 목록
- `src/app/page.services/view.pug`: 이미지 검증 결과 표시 바인딩을 `versionCheckResult()`로 수정.
- `tests/api/test_services_preflight.py`: 정적 계약 테스트 토큰을 실제 signal 이름으로 수정.
- `devlog.md`, `devlog/2026-06-22/025-service-container-version-check-signal-fix.md`: 작업 이력 추가.

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_container_version_change_is_wired`
- 성공: `rg -n "versionChangeCheckResult" src/app/page.services tests/api/test_services_preflight.py` 결과 없음
- 성공: `wiz_project_build(clean=false)`
- 성공: `git diff --check`
