# Tailwind CSS v4 및 Angular PostCSS 빌드 경로 전환

- **ID**: 001
- **날짜**: 2026-04-27
- **유형**: 설정 변경

## 작업 요약
Tailwind CLI 단독 실행으로 빌드가 멈추던 기존 경로를 제거하고, Tailwind CSS v4의 Angular 권장 방식인 PostCSS 경로로 전환했다.
workspace builder 템플릿과 현재 프로젝트의 Angular 설정, 패키지 버전을 함께 갱신해 이후 재구성된 build 디렉터리에도 동일한 설정이 적용되도록 맞췄다.

## 변경 파일 목록
### 빌더/템플릿
- `plugin/workspace/model/builder.py`: `tailwind.css`와 `.postcssrc.json`을 build 루트에 복사·생성하도록 변경하고, 구식 `tailwind.min.css` CLI 생성 단계를 제거
- `plugin/workspace/model/src/code.py`: 기본 Tailwind/PostCSS 템플릿 추가, 기본 Tailwind content 경로를 `src/**/*.{html,ts}`로 확장

### 프로젝트 Angular 설정
- `project/main/src/angular/package.json`: Tailwind CSS를 4.2.4로 올리고 `@tailwindcss/postcss`, `postcss`를 추가, 공식 플러그인 버전 갱신
- `project/main/src/angular/angular.build.options.json`: 글로벌 스타일 엔트리를 `tailwind.min.css`에서 `tailwind.css`로 변경
- `project/main/src/angular/angular.json`: 빌드 스타일 엔트리를 `tailwind.css`로 동기화
- `project/main/src/angular/.postcssrc.json`: Angular 빌드에서 Tailwind PostCSS 플러그인을 사용하도록 추가
- `project/main/src/angular/tailwind.css`: Tailwind v4 CSS 엔트리와 JS config 연결용 `@config` 선언 추가

### 현재 build 워크스페이스 동기화
- `project/main/build/package.json`: 현재 build 환경도 동일한 Tailwind/PostCSS 버전으로 갱신
- `project/main/build/angular.json`: 현재 build 환경의 글로벌 스타일 엔트리를 `tailwind.css`로 변경
- `project/main/build/.postcssrc.json`: 현재 build 환경에 PostCSS 설정 추가
- `project/main/build/tailwind.css`: 현재 build 환경에 Tailwind v4 CSS 엔트리 추가

## 검증
- `cd /opt/app/project/main/build && npm install` 성공
- `cd /opt/app/project/main/build && npm list tailwindcss @tailwindcss/postcss --depth=0`에서 `tailwindcss@4.2.4`, `@tailwindcss/postcss@4.2.4` 확인
- `cd /opt/app/project/main/build && ./node_modules/.bin/ng build --configuration development --no-progress` 실행 시 더 이상 Tailwind 단계에서 멈추지 않고 Angular TypeScript 컴파일 단계까지 진행됨
- 최종 빌드는 기존 애플리케이션 코드의 TypeScript 오류들로 실패했으며, 이번 작업 범위에서는 수정하지 않음