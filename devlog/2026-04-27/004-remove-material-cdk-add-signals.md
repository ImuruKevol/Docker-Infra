# Material/CDK 의존성 제거 및 signal 샘플 추가

- **ID**: 004
- **날짜**: 2026-04-27
- **유형**: 리팩토링 / 기능 추가

## 작업 요약
Angular Material UI를 사용하지 않는 방향에 맞춰 `@angular/material`과 `@angular/cdk` 직접 의존성을 제거했다.
기존 대시보드 샘플 화면에 Angular signal 기반 상태 관리 예시를 추가하여 `signal`, `computed`, `set`, `update` 사용 흐름을 확인할 수 있게 했다.

## 변경 파일 목록
### 의존성 정리
- `src/angular/package.json`: 사용하지 않는 `@angular/material`, `@angular/cdk` 의존성 제거

### Signal 샘플
- `src/app/page.dashboard/view.ts`: `stats`, `recentItems`, `loading` 상태를 signal로 전환하고 `publishedRate`, `signalTotal` computed 예시 추가
- `src/app/page.dashboard/view.pug`: signal 호출 문법(`stats()`, `loading()`, `computed()`)을 반영하고 Count/Step 조작 카드 추가

## 검증
- `grep -R "@angular/material\|@angular/cdk" project/main/src` 결과 없음 확인
- `wiz_project_build(clean=true)` 성공
- `project/main/build/package.json`에서 `@angular/material`, `@angular/cdk` 직접 의존성 없음 확인
- `cd project/main/build && npm list @angular/material @angular/cdk --depth=0` 결과 최상위 패키지 없음 확인
- `src/app/page.dashboard/view.ts`, `src/app/page.dashboard/view.pug`, `src/angular/package.json` VS Code Problems 오류 없음 확인
