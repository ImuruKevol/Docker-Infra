# 관리 화면 보드형 레이아웃과 공통 페이지네이션 적용

## 사용자 요청

ReviewOps 리뷰 ID `hfpghzwqjqivdepiamtcifekwsgcunwt`의 "레이아웃 전체 수정" 요청.

현재 서비스 관리, 서버 관리, 템플릿 관리, 매크로 관리 등 화면들이 왼쪽 목록/오른쪽 콘텐츠 구조라 초기 로딩과 많은 항목 표시가 불리하므로 전부 게시판 형태로 전환하고, 처음/끝/이전/다음/10페이지 단위 표시를 갖춘 공통 페이지네이션을 적용하며 페이지당 dump는 20개로 고정해달라는 요청.

## 변경 파일

- `src/portal/season/app/pagination/view.ts`
- `src/portal/season/app/pagination/view.pug`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `src/model/struct/infra_catalog_registry.py`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.scss`
- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `src/app/page.macros/view.ts`
- `src/app/page.macros/view.pug`
- `src/app/page.operations/api.py`
- `src/app/page.operations/view.ts`
- `src/app/page.operations/view.pug`
- `src/app/page.domains/view.ts`
- `src/app/page.domains/view.pug`
- `src/app/page.images/view.ts`
- `src/app/page.images/view.pug`

## 작업 내용

- 공통 `season` pagination 컴포넌트를 처음/끝, 이전/다음, 10페이지 단위 버튼 표시 구조로 재작성했다.
- 서비스 관리 목록 API를 `page/limit` 기반으로 바꾸고 기본 20건 응답과 pagination metadata를 반환하도록 했다.
- 서비스/서버/템플릿/매크로 관리 화면의 좌측 목록/우측 상세 구조를 보드 목록 + 하단 상세 구조로 변경했다.
- 서비스/서버/템플릿/매크로 초기 진입 시 첫 항목 상세를 자동 로드하지 않고, 상세 URL 또는 명시적 선택 시에만 상세를 로드하도록 조정했다.
- 작업 로그는 페이지당 20건 고정과 공통 pagination 컴포넌트 사용으로 통일했다.
- 도메인, 이미지 관리 화면의 주요 목록에도 20건 단위 공통 pagination을 추가하고, 이미지 화면의 선택 패널은 세로 보드 흐름으로 조정했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)` 성공.
- devmode 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true` 포함 후 `http://127.0.0.1:3001/access`, `/services`, `/servers`, `/templates` HEAD 요청 200 확인.
- 동일 쿠키로 목록 API를 직접 호출했을 때 사용자 세션이 없어 401 `AUTHENTICATION_REQUIRED`가 반환됨을 확인했다. 인증 보호가 적용된 상태라 API 데이터 검증은 로그인 세션 없이 완료하지 못했다.
