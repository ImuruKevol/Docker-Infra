# Tailwind dark variant 기반 테마 적용 단순화

- **ID**: 003
- **날짜**: 2026-04-28
- **유형**: 리팩토링

## 작업 요약
테마 변경 시 템플릿마다 `tone()`/`editorTone()` helper로 light/dark 클래스를 선택하던 구조를 Tailwind `dark:` variant 중심으로 단순화했다. `service.theme`은 전역 상태 저장과 `html.dark` 토글만 담당하고, 일반 UI 색상 전환은 CSS가 처리하도록 정리했다.

## 변경 파일 목록
- `src/angular/tailwind.css`: Tailwind v4 class 기반 dark variant 선언 추가
- `src/portal/season/libs/src/theme.ts`: `tone()` helper 제거
- `src/app/component.nav.sidebar/view.ts`, `src/app/component.nav.sidebar/view.pug`: navbar 테마 분기를 Tailwind `dark:` class로 치환
- `src/app/layout.sidebar/view.pug`: shell 배경/텍스트/사이드바 색상을 정적 `dark:` class로 치환
- `src/portal/post/app/detail/view.ts`, `src/portal/post/app/detail/view.pug`: 글 작성 화면의 `editorTone()` 제거 및 `dark:` class 적용, Monaco는 `theme.change` 이벤트로 JS 옵션만 갱신
- `src/portal/season/README.md`, `docs/angular-21-upgrade.md`: `service.theme` 문서를 Tailwind `dark:` 사용 패턴으로 갱신
- `src/assets/lang/ko.json`, `src/assets/lang/en.json`: 샘플 문구를 WIZ NgModule scope 기준으로 갱신

## 검증
- WIZ normal build 성공
- `/posts/new/edit`에서 다크 모드 토글 시 `html.dark` 적용 확인
- sidebar/panel 배경이 Tailwind `dark:` class로 전환되는 것 확인
- Monaco Editor가 다크 모드에서 `vs-dark`, 라이트 모드에서 `vs` 테마로 전환되는 것 확인