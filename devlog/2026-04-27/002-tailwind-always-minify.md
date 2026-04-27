# Tailwind CSS를 항상 minify 산출물로 생성하도록 빌드 경로 조정

- **ID**: 002
- **날짜**: 2026-04-27
- **유형**: 설정 변경

## 작업 요약
Tailwind CSS가 Angular 개발 빌드의 CSS 최적화 설정에 따라 비압축 상태로 남던 문제를 제거하고, builder가 매번 Tailwind CLI로 `tailwind.min.css`를 직접 생성하도록 변경했다.
Angular 스타일 엔트리도 모두 `tailwind.min.css`를 바라보게 맞춰서 개발/운영 구분 없이 Tailwind는 항상 압축본을 사용하도록 정리했다.

## 변경 파일 목록
### 빌더
- `plugin/workspace/model/builder.py`: 빌드 중 `tailwind.css` 입력과 `tailwind.config.js`를 사용해 `tailwind.min.css`를 CLI로 생성하도록 변경하고, CLI 미설치/실패 시 즉시 예외 처리하도록 수정

### 프로젝트 설정
- `project/main/src/angular/package.json`: `@tailwindcss/cli` 의존성 추가
- `project/main/src/angular/angular.build.options.json`: 스타일 엔트리를 `tailwind.min.css`로 변경
- `project/main/src/angular/angular.json`: 현재 Angular 설정도 `tailwind.min.css`로 동기화
- `project/main/build/package.json`: 현재 build 워크스페이스에 `@tailwindcss/cli` 추가
- `project/main/build/angular.json`: 현재 build 워크스페이스의 스타일 엔트리를 `tailwind.min.css`로 변경

## 검증
- `cd /opt/app/project/main/build && npm install --force` 성공
- `cd /opt/app/project/main/build && ./node_modules/.bin/tailwindcss -i tailwind.css -o tailwind.min.css -c tailwind.config.js --minify` 성공
- `cd /opt/app && wiz project build` 성공
- `cd /opt/app/project/main/build && wc -l tailwind.min.css` 결과가 `1`로 확인되어 minified 산출물 생성 검증 완료