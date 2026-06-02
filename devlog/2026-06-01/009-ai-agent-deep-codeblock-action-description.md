# AI Agent 동적 코드블럭 스타일 적용과 히스토리 다음 동작 설명 제거

- **ID**: 009
- **날짜**: 2026-06-01
- **유형**: UI 수정

## 작업 요약
AI Agent 응답과 히스토리 상세는 모두 `[innerHTML]`로 렌더링한 공통 `ai-agent-markdown` 경로를 사용하고 있었다.
동적으로 삽입된 코드블럭 노드에는 Angular 컴포넌트 스코프 속성이 붙지 않아 기존 코드블럭 스타일이 적용되지 않는 문제가 있어, 코드블럭/툴바/복사 버튼 스타일을 `::ng-deep` selector로 보강했다.
히스토리 상세의 다음 동작 카드에서는 각 동작의 세 번째 줄 설명(`action.reason`)을 제거했다.

## 원문 요청사항
```text
- 첨부한 스크린샷과 같이 응답 부분에 코드 블럭에 스타일이 제대로 적용되지 않았어. 채팅창에서도 동일한지 확인해줘.
- 히스토리 상세 아래에 다음 동작 목록에서 각 동작별 세 번째 줄의 설명 부분은 제거해줘. 의미가 없어.
```

## 변경 파일 목록
- `src/angular/app/app.component.pug`
  - 히스토리 상세 다음 동작 카드에서 `action.reason` 설명 줄을 제거했다.
- `src/angular/app/app.component.scss`
  - 동적 `[innerHTML]` 코드블럭에도 적용되는 `::ng-deep` 코드블럭/툴바/복사 버튼 스타일을 추가했다.
  - 다크모드 코드블럭 동적 selector를 전역 `.dark` 경로로 보강했다.
  - 제거된 다음 동작 설명 줄의 불필요한 `small` 스타일을 정리했다.
- `tests/api/test_ai_agent_history.py`
  - 동적 코드블럭 스타일 selector와 다음 동작 설명 제거를 정적 계약으로 검증하도록 보강했다.
- `devlog.md`, `devlog/2026-06-01/009-ai-agent-deep-codeblock-action-description.md`
  - 작업 이력을 기록했다.

## 검증 결과
- `python -m py_compile tests/api/test_ai_agent_history.py` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history.AIAgentHistoryStaticContractTest` 성공.
- `git diff --check -- src/angular/app/app.component.pug src/angular/app/app.component.scss tests/api/test_ai_agent_history.py` 성공.
- `wiz_project_build(clean=false, projectName=main)` 성공.
- 빌드 산출물 `build/dist/build/main.js`에서 동적 코드블럭 selector와 다크모드 selector 포함을 확인했다.
- 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true`를 포함해 `https://infra-dev.nanoha.kr/dashboard` 요청 시 `200 text/html; charset=utf-8` 응답을 확인했다.
