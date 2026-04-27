# Angular 21 업그레이드 및 zoneless/fetch 전환

- **ID**: 003
- **날짜**: 2026-04-27
- **유형**: 설정 변경 / 리팩토링

## 작업 요약
Angular 런타임과 빌드 도구를 21 계열로 올리고, `zone.js` 의존성과 polyfill 구성을 제거했다.
WIZ 프론트엔드 호출 경로는 jQuery AJAX 대신 fetch 기반으로 전환하고, JSON body를 `wiz.request.query()`에서 읽을 수 있도록 base controller를 보강했다.

## 변경 파일 목록
### Angular 21 및 zoneless 설정
- `package.json`: clean build 시 Angular CLI 21을 사용하도록 루트 CLI 의존성 갱신
- `src/angular/package.json`: Angular/CLI/Material/CDK/compiler 도구를 21 계열로 갱신, TypeScript 5.9 계열 적용, `zone.js`와 `jquery` 의존성 제거
- `src/angular/angular.json`: `zone.js` polyfill 제거, Angular 21 dev-server/extract-i18n schema에 맞춰 `buildTarget` 사용
- `src/angular/app/app.module.ts`: `provideZonelessChangeDetection()` 적용, `@ng-util/monaco-editor` 21의 standalone component/provider API로 변경
- `src/angular/app/app.component.ts`: bootstrap 이후 `enableProdMode()` 중복 호출 제거
- `src/portal/season/libs/ngx-sortablejs/src/test.ts`: 제거된 `zone.js` 테스트 import 정리

### fetch 및 JSON body 처리
- `src/angular/wiz.ts`: `$.ajax` 기반 `wiz.call()`을 fetch 기반 JSON 요청으로 전환
- `src/portal/season/libs/util/request.ts`: 공통 request 유틸을 fetch 기반 POST로 전환
- `src/portal/season/libs/util/file.ts`: jQuery AJAX 업로드를 브라우저 기본 XHR 업로드로 교체하고 파일 입력 생성은 DOM API로 정리
- `src/controller/base.py`: JSON/form/query 요청을 모두 처리하도록 `wiz.request.query()` 오버라이드 추가
- `src/portal/season/controller/base.py`: portal route에서도 JSON body query 오버라이드가 적용되도록 동일 처리 추가
- `src/portal/post/controller/base.py`: post portal app API용 base controller 추가
- `src/portal/post/portal.json`: controller 사용 플래그 활성화
- `src/portal/post/app/list/app.json`, `src/portal/post/app/detail/app.json`: fetch JSON 요청을 읽을 수 있도록 base controller 연결

## 검증
- `project/main/src` 기준 `zone.js`, `jquery`, `$.ajax` 참조 없음 확인
- `src/angular/package.json`, `src/angular/angular.json`, `src/portal/post/portal.json` JSON 파싱 확인
- `wiz_project_build(clean=true)`로 Angular 21 build 워크스페이스 재생성 및 패키지 설치 확인
- `wiz_project_build(clean=false)` 성공
- `project/main/build` 기준 `zone.js`, `jquery`, `$.ajax` 참조 없음 확인
- `npm list` 확인: `@angular/core@21.2.10`, `@angular/cli@21.2.8`, `@angular/material@21.2.8`, `@angular/cdk@21.2.8`, `typescript@5.9.3`
