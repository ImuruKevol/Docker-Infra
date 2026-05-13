# AI 실행 스트림의 Codex CLI 경로 확인 표시 보강

## 원 요청

AI 수정 및 점검 화면에서 모델 선택이 필요하고, 일반 Codex와 커스텀 Codex CLI 중 실제 어떤 실행 경로를 쓰는지 확인할 수 있어야 한다. 모델 목록 최상단의 Codex는 일반 codex 로그인 세션을 사용하고, API Key 또는 Ollama 모델은 커스텀 Codex CLI를 통해 Codex 파이프라인을 사용해야 한다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `devlog.md`
- `devlog/2026-05-13/161-ai-codex-cli-execution-visibility.md`

## 변경 내용

- Codex 실행 결과 메타데이터를 AI provider 공개 payload에 반영하도록 정리했다.
- AI 스트림 완료 직후 `Codex 실행 확인` 상태 이벤트를 추가해 `일반 codex` 또는 `커스텀 Codex CLI`, 모델명, 실제 실행 파일 경로를 화면 진행 로그에서 확인할 수 있게 했다.
- 비 Codex 모델은 기존대로 커스텀 Codex CLI 경유 메타데이터가 유지되며, Codex 선택은 일반 codex 로그인 세션 경로로 표시된다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/model/struct/ai_settings.py`
- `git diff --check src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/app/page.services/view.ts src/app/page.services/view.pug src/app/page.system/view.ts src/app/page.system/view.pug src/app/page.system/api.py`
- `wiz_project_build(projectName="main", clean=false)` 성공
