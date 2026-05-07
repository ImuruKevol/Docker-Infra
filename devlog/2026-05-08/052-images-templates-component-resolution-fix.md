# 052. 이미지/템플릿 화면 Angular templateUrl 해석 오류 수정

- 일시: 2026-05-08
- 사용자 요청:
  - "ERROR Error: Component 'PageImagesComponent2' is not resolved:
 - templateUrl: ./view.html
Did you run and wait for 'resolveComponentResources()'?

건드린 화면이 깨졌어. 확실하게 확인해줘"

## 처리 내용

1. `/images`, `/templates` 화면을 실제 브라우저에서 다시 열어 `templateUrl` 미해결 런타임 오류를 재현했다.
2. `page.templates` 템플릿에서 Angular가 정적으로 컴파일하지 못하는 표현식들을 제거했다.
   - 템플릿 내부 `filter((item) => ...)` 계산을 `view.ts` helper로 이동
   - Monaco 옵션 object spread를 템플릿 밖 `schemaEditorOptions`, `readmeEditorOptions`로 이동
3. `page.images` 템플릿도 구조 지시문과 표시식을 helper 메서드 위주로 단순화해 Angular 컴파일 경로를 안정화했다.
   - Harbor repository 목록, 로컬 Docker 사용 가능 여부, 선택 서버 표시, `<none>` fallback 등을 `view.ts` helper로 이동
4. 빌드 후 `/images`, `/templates`를 다시 열어 두 화면 모두 page error 없이 진입되는 것을 확인했다.

## 변경 파일

- `src/app/page.images/view.ts`
- `src/app/page.images/view.pug`
- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `devlog.md`

## 검증

- `wiz_project_build(projectName="main", clean=false)` 통과
- Playwright headless smoke 확인
  - `/images` 진입 후 `pageerror` 없음, H1 `이미지 관리` 확인
  - `/templates` 진입 후 `pageerror` 없음, H1 `템플릿 관리` 확인
