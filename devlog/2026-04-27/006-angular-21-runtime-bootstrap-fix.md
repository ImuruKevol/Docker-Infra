# Angular 21 런타임 부트스트랩 및 라우팅 렌더링 복구

- **ID**: 006
- **날짜**: 2026-04-27
- **유형**: 버그 수정

## 작업 요약
Angular 21 전환 후 `@ngx-translate/http-loader` 17의 provider 방식 변경으로 발생한 `NG0201` 런타임 오류를 수정했다.
추가로 Angular 21 `browser-esbuild` 환경에서 JIT/AOT 부트스트랩 경로를 정리해, 빈 화면으로 남던 라우팅 렌더링 문제를 해결했다.

## 변경 파일 목록
- `src/angular/app/app.module.ts`
  - `TranslateHttpLoader`를 Angular 21/ngx-translate 17 방식에 맞게 class provider + config token 조합으로 변경
  - Router 관련 import를 명시적으로 정리
- `src/angular/app/app.component.pug`
  - 루트 `router-outlet`을 항상 렌더링하도록 수정
- `src/angular/main.ts`
  - `@angular/compiler`를 명시적으로 import
  - zone.js 없이 동작하도록 no-op zone 부트스트랩 설정
- `src/angular/angular.json`
  - Angular 21 `browser-esbuild` 빌드를 AOT 모드로 전환

## 검증
- WIZ 일반 빌드 성공 (`clean: false`)
- `http://localhost:3334/access` 브라우저 렌더링 확인
- `/access` 진입 시 콘솔 오류 없이 로그인 화면 표시 확인