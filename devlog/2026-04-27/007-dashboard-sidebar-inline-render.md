# Dashboard 사이드바 직접 렌더링으로 빈 네비게이션 복구

- **ID**: 007
- **날짜**: 2026-04-27
- **유형**: 버그 수정

## 작업 요약
Dashboard 접근 시 `wiz-component-nav-sidebar`가 plain element로만 남아 내부 템플릿이 렌더링되지 않는 문제를 확인했다.
`layout.sidebar`에서 사이드바 마크업을 직접 렌더링하도록 변경하고, 메뉴 활성 클래스 계산을 같은 컴포넌트에 추가해 실제 네비게이션이 표시되도록 복구했다.

## 변경 파일 목록
- `src/app/layout.sidebar/view.pug`
  - `wiz-component-nav-sidebar` 대신 직접 렌더링되는 sidebar template 추가
  - 프로필/메뉴 영역을 모바일, 데스크톱 레이아웃에서 재사용하도록 정리
- `src/app/layout.sidebar/view.ts`
  - 현재 경로 기준 활성 메뉴 클래스 계산 함수 추가
- `src/angular/angular.json`
  - 중간 검증에서 되돌렸던 AOT 설정을 유지 상태(`true`)로 복원

## 검증
- WIZ 일반 빌드 성공 (`clean: false`)
- `http://localhost:3334/dashboard`에서 사이드바 메뉴(`Dashboard`, `게시물`, `멤버`) 렌더링 확인
- `posts` 경로는 현재 인증 리다이렉트로 인해 같은 패턴을 추가 검증하지 못함