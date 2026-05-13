# 181. 사이드 메뉴 카테고리 분리와 도구 다운로드 제거

- 날짜: 2026-05-13
- 리뷰 ID: pxwgfxlhwlhpxnfdokmpjssuukxkuspu
- 분류: ux

## 사용자 원 요청

작업을 시작해줘.

## 리뷰 요청 내용

사이드 메뉴를 일반 사용자가 자주 쓰는 메뉴와 상대적으로 고급 사용자가 보는 메뉴로 나누고, 관련도와 사용자 흐름에 맞게 표시 순서를 재배치한다. 도구 다운로드 메뉴와 화면은 제거한다.

## 변경 파일

- `src/app/component.nav.sidebar/view.ts`
  - 메뉴 데이터를 단일 목록에서 `일반 메뉴`/`고급 메뉴` 그룹 구조로 변경했다.
  - 일반 메뉴 순서를 `대시보드 -> 서비스 관리 -> 도메인 관리`로 배치했다.
  - 고급 메뉴 순서를 `서버 관리 -> 이미지 관리 -> 매크로 -> 작업 로그 -> 시스템 설정`으로 배치했다.
  - 도구 다운로드 메뉴 항목을 제거했다.
- `src/app/component.nav.sidebar/view.pug`
  - 사이드바가 메뉴 그룹별 제목과 항목을 렌더링하도록 변경했다.
- `src/assets/lang/ko.json`
  - 일반/고급 메뉴 라벨과 작업 로그 번역을 추가하고 도구 다운로드 번역을 제거했다.
- `src/assets/lang/en.json`
  - 일반/고급 메뉴 라벨과 작업 로그 번역을 추가하고 Tools 번역을 제거했다.
- `src/app/page.tools/api.py`
- `src/app/page.tools/app.json`
- `src/app/page.tools/view.pug`
- `src/app/page.tools/view.ts`
  - 도구 다운로드 화면을 제거했다.
- `tests/api/test_auth_setup.py`
  - 보호 페이지 기대 목록에서 `page.tools`를 제거하고 현재 보호 페이지 목록에 맞게 갱신했다.
- `tests/api/test_sample_cleanup.py`
  - 페이지 스켈레톤 기대 목록에서 `page.tools`를 제거하고 현재 페이지 목록에 맞게 갱신했다.

## 확인 결과

- `wiz_project_build(clean=true)` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_sample_cleanup tests.api.test_auth_setup.AuthSetupStaticContractTest` 실행 결과 8개 테스트 통과.
- `rg -n "page\.tools|nav\.tools|/tools|도구 다운로드" src/app src/assets tests/api/test_auth_setup.py tests/api/test_sample_cleanup.py` 결과 관련 메뉴/화면 참조 없음.
- `wiz_source_list_apps(appType=page)` 기준 `page.tools`가 제거되고 페이지 수가 10개로 확인됨.

## 남은 리스크

- 실제 배포 환경의 브라우저 화면은 별도 스크린샷 검증을 수행하지 않았다.
