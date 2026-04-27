# Angular 21 중첩 WIZ 컴포넌트 렌더링 복구

- **ID**: 008
- **날짜**: 2026-04-27
- **유형**: 버그 수정

## 작업 요약
Angular 21 AOT/esbuild 빌드에서 WIZ App/Portal App을 NgModule 선언에만 의존해 생성하면 템플릿 내부의 WIZ 커스텀 태그가 plain element로 남는 문제를 수정했다.
빌더가 생성 컴포넌트를 standalone으로 만들고 템플릿에 등장하는 WIZ 자식 컴포넌트를 imports에 자동 포함하도록 변경했으며, 사이드바를 다시 `wiz-component-nav-sidebar` 사용 구조로 되돌렸다.

## 변경 파일 목록
- `plugin/workspace/model/builder.py`: 생성 컴포넌트에 `standalone: true`와 공통 Angular imports 및 템플릿 기반 WIZ child component imports를 자동 주입하도록 수정.
- `src/angular/app/app.module.ts`: standalone 생성 방식에 맞춰 생성 컴포넌트 선언 placeholder를 제거하고 AppComponent만 선언하도록 정리.
- `src/app/layout.sidebar/view.pug`: ngTemplate inline 우회를 제거하고 `wiz-component-nav-sidebar`, `wiz-portal-season-modal`, `wiz-portal-season-loading-season`을 직접 사용하도록 복구.
- `src/app/layout.sidebar/view.ts`: inline template 전용 active class 헬퍼를 제거하고 레이아웃 책임만 남김.
- `src/portal/post/model/struct/post.py`: 게시물 응답에 `author`, `summary` alias를 보강.
- `src/portal/post/app/list/api.py`, `src/portal/post/app/detail/api.py`: 실행 중 캐시가 이전 모델 응답을 반환해도 화면이 안정적으로 동작하도록 기존 API 함수 내부에서 응답 필드 보강.
- `src/portal/post/app/list/view.pug`, `src/portal/post/app/detail/view.pug`: `author`/`author_name` 양쪽 필드를 지원하도록 표시 fallback 추가.

## 검증
- `mcp_wiz_wiz_project_build(clean=false)` 성공.
- `/dashboard`, `/posts`, `/posts/post_notice/view`, `/posts/post_notice/edit`, `/posts/post_notice/settings`, `/posts/new/edit`, `/members`, `/mypage`, `/access` 브라우저 순회 확인.
- 중첩 WIZ 커스텀 컴포넌트 빈 host 0개 확인.
- `wiz-portal-season-modal` 검증 메시지 표시 확인.
