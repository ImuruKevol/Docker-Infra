# 204. 서비스 생성 AI Gemini 커스텀 Codex 완료와 진행 표시 수정

## 원 요청

- 리뷰 ID: `hhkjmtlumaejzvipfcmymffpufbvzqjj`
- 제목: 서비스 AI 생성 시 버그
- 요청: 새 서비스를 AI로 만들 때 Codex가 아닌 Gemini 같은 모델을 선택하면 커스텀 Codex CLI를 통해 AI를 호출해야 하는데, "나무위키(https://namu.wiki/)와 같은 위키 서비스가 필요해." 설명에서 AI 진행 상태가 첫 단계에 멈춰 보이는 문제를 Playwright와 로그로 확인하고 고친다.

## 변경 내용

- AI SSE heartbeat 이벤트에 경과 시간, 표시 라벨, 대기 메시지를 포함하도록 보강했다.
- 비 Codex 모델 provider 공개 정보와 실행 확인 상태에 `커스텀 Codex CLI` 라벨이 표시되도록 정리했다.
- 서비스 생성 화면의 AI 진행 상태가 heartbeat 이벤트를 표시하고, Gemini 선택 시 `Gemini / gemini-3.1-flash-lite · 커스텀 Codex CLI`로 실행 경로를 보여주도록 수정했다.
- 커스텀 Codex CLI의 Gemini chat-completions 어댑터가 assistant text delta 전에 Responses `OutputItemAdded`를 내보내지 않아 debug 빌드에서 `OutputTextDelta without active item` panic이 발생하던 문제를 수정했다.
- chat-completions 어댑터가 텍스트 응답 시작/완료 이벤트를 Responses 호환 순서로 내보내도록 바꾸고 회귀 테스트를 추가했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `/root/docker-infra/codex/codex-rs/codex-api/src/sse/chat_completions.rs`
- `/root/docker-infra/codex/codex-rs/codex-api/tests/sse_end_to_end.rs`
- `devlog.md`
- `devlog/2026-05-14/204-service-create-ai-gemini-progress-heartbeat.md`

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/model/struct/ai_assistant.py` 통과.
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `git diff --check` 통과.
- `cargo test -p codex-api chat_completions_adapter_streams_text_and_tool_calls` 통과.
- `cargo build -p codex-cli --bin codex` 통과.
- 커스텀 Codex CLI 최소 Gemini 호출이 `{"ok":true}`로 정상 종료되는 것을 확인했다.
- 직접 SSE 호출에서 Gemini provider가 `cli_label: 커스텀 Codex CLI`와 heartbeat 메시지를 반환하고, 같은 리뷰 문구로 31초에 `done` 이벤트와 MediaWiki/MariaDB 2개 컴포넌트 초안을 반환하는 것을 확인했다.
- Playwright로 `http://127.0.0.1:3001/services/create`에 로그인 후 Gemini 3.1 Flash Lite를 선택하고 같은 요청 문구를 입력했을 때, 화면이 `구성 확인` 단계로 이동하고 `mediawiki:1.41`, `mariadb:10.6` 컴포넌트를 표시하는 것을 확인했다.

## 남은 리스크

- 실제 최종 초안 품질과 완료 시간은 Gemini API 응답 속도, 모델 상태, 커스텀 Codex CLI 실행 시간에 영향을 받는다.
