# AI Agent 다단 도킹 패널과 Hermes 런타임 설정 보강

- **ID**: 014
- **날짜**: 2026-05-29
- **유형**: 기능 보강

## 작업 요약
전역 AI Agent UI를 팝오버가 아닌 화면 우측 다단 도킹 패널로 전환하고, 현재 화면/최근 동작/추천 질문을 채팅과 함께 표시하도록 보강했다.
Hermes Agent 저장 설정이 실제 `config.yaml`과 `.env`에 반영되도록 Provider, Model, Terminal, API Key 환경변수 호환 처리를 정리하고, Hermes CLI 명령 템플릿을 현재 설치된 CLI 옵션에 맞게 수정했다.

## 원문 요청사항
```text
채팅창이 팝오버 형식이 아니라 화면 자체를 다단형식으로 해야해. 그리고 채팅창에 채팅창만 있는게 아니라 현재 화면이 뭐가 떠있는지, 현재 화면 컨텍스트에 대해 표시도 해야하고, 각 화면들마다 추천하는 질문같은것도 띄워줘야 해.
그리고 헤르메스 에이전트를 기본으로 선택하고 테스트하려 했는데, 시스템 설정에 저장한 정보들(Provider, API Key, Terminal)이 hermes cli에 반영이 안되어있어. 확실하게 동작하도록 해줘.
관리자 패스워드는 "______"이니 브라우저 테스트로 진행하고, 현재 gemini api key가 설정되어있으니 동작하는 것까지 확인해줘.
```

## 변경 파일 목록
- `src/angular/app/app.component.pug`: Agent 패널을 우측 도킹 다단 레이아웃으로 변경하고 현재 화면, 최근 동작, 추천 질문 섹션을 추가.
- `src/angular/app/app.component.scss`: 도킹 패널, 컨텍스트 카드, 추천 질문, 반응형 레이아웃 스타일 추가.
- `src/angular/app/app.component.ts`: 화면 컨텍스트 표시, 라우트별 추천 질문, 최근 이벤트 표시 갱신 로직 추가.
- `src/model/struct/codex_runtime.py`: Hermes 설정 적용 시 `config.yaml`/`.env` 동기화, Gemini API Key 환경변수 호환, Terminal 설정 반영, Hermes CLI 명령 템플릿 및 테스트 provider 전달 수정.
- `src/model/struct/ai_assistant.py`: 기본 Hermes provider/terminal 설정이 채팅 실행 provider에 전달되도록 보강.
- `src/model/struct/ai_settings.py`: Hermes `terminal_cwd` 저장값이 정규화 과정에서 유지되도록 수정.
- `devlog.md`, `devlog/2026-05-29/014-ai-agent-dock-hermes-runtime.md`: 작업 이력 기록.

## 검증 결과
- `python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/model/struct/ai_assistant.py src/route/api-ai-agent/controller.py` 성공.
- `wiz_project_build(clean=false)` 성공.
- Playwright 브라우저 테스트에서 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키와 관리자 비밀번호로 로그인 후 `/system`에서 Agent 버튼과 우측 도킹 패널 표시를 확인했다.
- 도킹 패널에서 `현재 화면`, `최근 동작`, `추천 질문` 섹션과 `/system` 전용 Hermes 추천 질문 노출을 확인했다.
- `/wiz/api/page.system/ai_hermes_apply_settings` 호출 후 Hermes `config.yaml`에 provider/model/terminal/MCP 설정이, `.env`에 `HERMES_INFERENCE_PROVIDER`, `HERMES_INFERENCE_MODEL`, `TERMINAL_ENV`, `TERMINAL_CWD`, `TERMINAL_TIMEOUT`이 반영되는 것을 확인했다.
- Hermes 실행 테스트에서 provider가 `gemini`로 전달되고 제거한 `--source` 인자가 더 이상 포함되지 않는 것을 확인했다.

## 남은 리스크
- 라이브 서버의 Hermes 상태가 `api_key_configured=false`로 반환되어 실제 Gemini 응답 생성까지는 완료하지 못했다. 현재 런타임 `.env`에도 Gemini API Key 값이 없어 Hermes CLI는 `GOOGLE_API_KEY` 미설정 오류를 반환한다.
- 실제 API Key가 입력되면 이번 변경으로 `GOOGLE_API_KEY`와 `GEMINI_API_KEY`를 함께 기록하도록 보강했지만, 이번 검증에서는 비밀값 자체가 제공되거나 서버에 존재하지 않았다.
- `pytest`는 현재 파이썬 환경에 설치되어 있지 않아 실행하지 못했다.
