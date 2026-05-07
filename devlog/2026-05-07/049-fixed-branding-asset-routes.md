# 브랜딩 자산 고정 라우트와 시스템 설정 URL 입력 제거 적용

- **ID**: 049
- **날짜**: 2026-05-07
- **유형**: 기능 개선

## 작업 요약
favicon과 logo를 랜덤 파일명 기반 URL 대신 고정 라우트(`/api/system/assets/favicon`, `/api/system/assets/logo`)로 바꿨다.  
시스템 설정 화면에서는 URL 입력을 제거하고, 저장 시 기존 고정 파일을 덮어쓰는 방식으로 정리했다.

## 원문 요청사항
```text
Favicon과 Logo는 이미지 파일 이름을 고정해서 굳이 URL을 보여주지 않도록 수정해줘. 그래야 기존에 업로드했던 이미지들을 관리할 필요가 없어. 덤으로 페이지가 로드될 때 로고나 favicon 파일 이름을 가져올 필요가 없는 효과도 있어. 그냥 해당 URL로 이미지를 요청하면 기본값으로 리다이렉션을 시키거나 기존 기본값 파일을 불러오면 되니까.
```

## 변경 파일 목록
- `src/model/struct/appearance.py`
  - 브랜딩 자산 경로를 고정 라우트로 정의했다.
  - 업로드 파일은 `favicon.*`, `logo.*` 고정 이름으로 덮어쓰고, 이전 랜덤 파일과 같은 종류의 구 자산을 정리하도록 변경했다.
  - public payload는 파일명 대신 고정 라우트만 내려주고, favicon은 기본 아이콘 fallback을 제공하도록 수정했다.
- `src/portal/season/libs/appearance.ts`
  - 기본 favicon 경로를 고정 라우트로 변경했다.
  - 확장자 기반 `type` 추정을 제거하고, favicon link는 MIME에 덜 의존하도록 단순화했다.
  - 고정 자산 경로 helper를 추가했다.
- `src/app/page.system/view.ts`
  - 일반 설정 초기값과 favicon preview를 고정 라우트 기반으로 정리했다.
- `src/app/page.system/view.pug`
  - Favicon URL / Logo URL 입력을 제거했다.
  - 고정 경로 덮어쓰기 방식을 안내하는 문구로 변경했다.
- `src/app/page.system/api.py`
  - appearance model을 direct path로 읽도록 변경해 시스템 설정 API에서 최신 브랜딩 로직을 사용하게 했다.
- `src/route/api-system-appearance/controller.py`
- `src/route/api-system-assets/controller.py`
- `src/route/api-system-assets-path/controller.py`
  - appearance model direct path 사용으로 브랜딩 route 캐시 의존을 줄였다.

## 검증 결과
- `wiz_project_build(projectName="main", clean=false)` 통과
- `python -m unittest tests.api.test_system_settings_dynamic_menu tests.api.test_wiz_structure_contract` 통과 (`skipped=2`)
- `git diff --check` 통과
- live 확인
  - `/api/system/appearance` 응답이 `favicon_url=/api/system/assets/favicon`, `logo_url=/api/system/assets/logo|''` 형식으로 내려오는 것 확인
  - `/api/system/assets/favicon` 요청 시 기본 favicon 바이너리 응답 확인
  - `/api/system/assets/logo` 요청 시 기본 로고 SVG fallback 응답 확인
  - Playwright에서 `/system` 진입 후 URL input 2개가 제거된 것 확인
  - `data/di_logo.svg`를 logo로 저장한 뒤 `/api/system/appearance`가 파일명 없는 고정 logo route를 반환하는 것 확인
  - 저장 후 로고 이미지 `naturalWidth=150`, `naturalHeight=150`, page error 없음

## 비고
- `appearance` 관련 파이썬 모델은 런타임 캐시 때문에 재시작 없이 교체되지 않아 `wiz.docker-infra` 데몬을 1회 재시작했다.
