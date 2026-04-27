# Angular 21 WIZ 컴포넌트 NgModule 스코프 복원

- **ID**: 002
- **날짜**: 2026-04-28
- **유형**: 리팩토링

## 작업 요약
Angular 21 업그레이드 후 생성 컴포넌트를 standalone으로 유지할 필요가 있는지 재검토했다. WIZ 프로젝트는 빌더가 Source/Portal 앱을 하나의 Angular 앱으로 합성하는 구조이므로, 생성 컴포넌트에 `standalone: false`를 명시하고 기존 `AppModule.declarations` 스코프를 유지하는 방향으로 정리했다.

## 변경 파일 목록
- `plugin/workspace/model/builder.py`: generated WIZ component를 `standalone: false`로 생성하고 모든 앱 컴포넌트를 `AppModule.declarations`에 포함하도록 복원
- `project/main/src/angular/app/app.module.ts`: `@wiz.declarations` placeholder를 되살려 생성 컴포넌트 선언을 AppModule 중심으로 관리
- `project/main/docs/angular-21-upgrade.md`: Angular 21 standalone 기본값, WIZ NgModule 유지 정책, 전역 AppModule imports, `service.theme` 내용을 문서화

## 검증
- `python -m py_compile plugin/workspace/model/builder.py plugin/workspace/model/src/build/annotator.py` 성공
- WIZ normal build 성공
- 생성 산출물에서 WIZ 컴포넌트 `standalone: false` 및 `AppModule.declarations` 등록 확인
- `/posts/new/edit`에서 navbar 다국어 전환, 다크 모드 전환, Monaco light/dark theme 연동 확인
- 브라우저 검증 기준 console error/warning 없음
