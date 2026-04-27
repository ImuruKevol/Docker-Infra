# Navbar 전역 다국어·다크 모드 및 app.module 의존성 스코프 정리

- **ID**: 001
- **날짜**: 2026-04-28
- **유형**: 기능 추가

## 작업 요약
다국어 전환과 다크 모드 토글을 글 작성 화면 내부에서 navbar로 이동하여 앱 전역에서 사용할 수 있도록 정리했다. Angular 21 standalone 생성 구조에서도 소스 작성자는 `app.module.ts`에 전역 의존성을 선언하고, 빌더가 생성 컴포넌트 imports에 반영하도록 개선했다.

## 변경 파일 목록
- `plugin/workspace/model/builder.py`: `src/angular/app/app.module.ts`의 `@dependencies` 선언을 모든 generated standalone 컴포넌트 imports에 공통 반영
- `project/main/src/angular/app/app.module.ts`: `NuMonacoEditorComponent`, `TranslateModule` 전역 standalone dependency 선언 추가
- `project/main/src/portal/season/libs/service.ts`, `project/main/src/portal/season/libs/src/theme.ts`: 전역 theme 상태 및 `html.dark` 적용 helper 추가
- `project/main/src/app/component.nav.sidebar/view.ts`, `project/main/src/app/component.nav.sidebar/view.pug`: navbar 언어 전환과 다크 모드 토글 추가, 메뉴 라벨 다국어화 및 테마 대응
- `project/main/src/app/layout.sidebar/view.pug`, `project/main/src/angular/styles/styles.scss`: 앱 shell 기본 dark mode 배경 적용
- `project/main/src/portal/post/app/detail/view.ts`, `project/main/src/portal/post/app/detail/view.pug`: 화면 내부 언어/테마 토글 제거, 전역 theme 이벤트 기반 Monaco 테마 갱신
- `project/main/src/assets/lang/ko.json`, `project/main/src/assets/lang/en.json`: navbar 번역 리소스 추가
- `project/main/src/portal/season/README.md`: `service.theme` 사용법 문서화

## 검증
- `python -m py_compile plugin/workspace/model/builder.py plugin/workspace/model/src/build/annotator.py` 성공
- WIZ normal build 성공
- 생성된 navbar/post detail standalone 컴포넌트에 app.module 전역 dependency imports 반영 확인
- `/posts/new/edit`에서 navbar KO/EN 전환, 다크 모드 전환, Monaco light/dark theme 연동 확인
- 브라우저 검증 기준 console error/warning 없음
