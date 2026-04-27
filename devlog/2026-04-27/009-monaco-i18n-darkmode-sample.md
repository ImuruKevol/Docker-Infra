# 글 작성 화면 Monaco/i18n/dark mode 샘플 의존성 명시화

- **ID**: 009
- **날짜**: 2026-04-27
- **유형**: 기능 추가

## 작업 요약
글 작성 화면의 Monaco Editor, 다국어 처리, 다크 모드 샘플을 Angular 21 standalone component 구조에 맞게 정리했다. Monaco와 TranslateModule 의존성은 빌더의 템플릿 문자열 감지가 아니라 `@dependencies` 선언으로 명시하도록 변경했다.

## 변경 파일 목록
- `plugin/workspace/model/builder.py`: Monaco/translate 템플릿 감지 기반 의존성 추가 로직 제거
- `plugin/workspace/model/src/build/annotator.py`: `@dependencies`, `@directives` annotation parser가 여러 명시 항목을 처리하도록 일반화
- `project/main/src/portal/post/app/detail/view.ts`: `NuMonacoEditorComponent`, `TranslateModule` explicit dependency 선언 추가

## 검증
- `python -m py_compile plugin/workspace/model/builder.py plugin/workspace/model/src/build/annotator.py` 성공
- WIZ normal build 성공
- `/posts/new/edit`에서 언어 전환, 다크 모드 전환, Monaco Editor 렌더링 확인
- 브라우저 reload 기준 console error/warning 없음
