# 시스템 설정 화면의 파일 업로드 template ref 오류를 제거해 Angular 런타임 예외 수정

- 날짜: 2026-05-07
- ID: 046

## 사용자 요청

- "Uncaught (in promise) RuntimeError: NG0301"
- "Uncaught (in promise) TypeError: Cannot read properties of null (reading 'componentOffset')"

## 변경 파일

- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`

## 작업 내용

- Playwright로 `/system` 화면을 직접 재현해 `NG0301`이 `page.system` 템플릿에서 발생하는 것을 확인했다.
- 원인은 Pug 템플릿의 `input(#faviconUpload ...)`, `input(#logoUpload ...)` 문법이 Angular 빌드 결과에서 `#faviconUpload="#faviconUpload"`처럼 잘못 컴파일되는 점이었다.
- template reference variable을 제거하고, 숨김 file input에 고정 `id`를 부여한 뒤 버튼이 `openAssetPicker()`로 해당 input을 열도록 변경했다.
- 업로드 처리도 `HTMLInputElement` 직접 참조 대신 `(change)` 이벤트를 받아 `event.target.files`를 읽도록 수정했다.
- 수정 후 `/dashboard`, `/servers`, `/services`, `/domains`, `/system`, `/macros`, `/tools`를 모두 다시 열어 pageerror/console error가 없는지 확인했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m compileall src/app/page.system src/angular src/portal/season/libs`: 통과
- `systemctl restart wiz.docker-infra`: 완료
- Playwright live smoke:
  - `/system` 재현 시 `NG0301` 없음
  - `/dashboard`, `/servers`, `/services`, `/domains`, `/system`, `/macros`, `/tools` pageerror/console error 없음
- `git diff --check`: 통과
