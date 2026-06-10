# AI Agent 응답 텍스트 드래그 선택 유지 보강

- 날짜: 2026-06-08
- ID: 006
- 리뷰 ID: klffpnhvpdesiwbdgxbcrjlcfoeilcnh

## 사용자 원 요청

이전에 있었던 버그가 계속 발생하고 있어. 결과를 복사하려고 마우스로 드래그해서 긁으니까 블록이 바로 해제되는 버그가 있어.

## 변경 파일

- `src/angular/app/app.component.ts`
- `src/angular/app/app.component.scss`
- `tests/api/test_ai_agent_history.py`
- `tests/e2e/specs/ai-agent-selection.spec.ts`
- `devlog.md`
- `devlog/2026-06-08/006-ai-agent-selection-preserve.md`

## 작업 내용

- AI Agent 응답/히스토리 본문에서 마우스 드래그 선택 중이거나 선택 직후에는 Agent 패널 렌더와 컨텍스트 갱신 렌더를 지연하도록 이벤트 추적을 보강했다.
- 선택 가능 영역을 응답 Markdown/메시지/히스토리 상세 본문으로 제한하고, 버튼/입력/리사이즈 핸들 등 조작 요소에서는 선택 보호가 걸리지 않도록 분리했다.
- 응답 본문과 Markdown 내부 요소에 명시적인 `user-select: text` 스타일을 적용하고, 후속 액션 버튼 영역은 선택되지 않도록 정리했다.
- 선택 보호 로직 정적 계약 테스트와 브라우저 Selection 유지 E2E 스펙을 추가했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history`: 통과
- `wiz_project_build(clean=false)`: 통과
- `DOCKER_INFRA_BASE_URL=https://infra-dev.nanoha.kr DOCKER_INFRA_TEST_PASSWORD=... npx playwright test tests/e2e/specs/ai-agent-selection.spec.ts --project=chromium`: 통과
- 실제 브라우저 수동 검증에서 devmode 쿠키 적용 후 AI Agent 응답 문단을 마우스로 드래그 선택했고, 외부 DOM 변경으로 렌더 예약이 발생한 뒤에도 선택 문자열이 유지됨을 확인했다.

## 참고

- `npm --prefix src/angular run build`는 `@angular-devkit/build-angular:browser-esbuild` 빌더 패키지가 `src/angular` 경로에 설치되어 있지 않아 실행되지 않았다. WIZ 빌드는 동일 Angular 번들을 정상 생성했다.
