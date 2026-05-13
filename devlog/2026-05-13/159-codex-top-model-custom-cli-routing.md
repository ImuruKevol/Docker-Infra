# 159. AI 모델 목록 Codex 상단 항목과 커스텀 CLI 경유 표시 정리

## 사용자 요청

모델 목록에서 맨 위에는 그냥 Codex를 추가하는거야. 그래서 이걸 선택하면 일반 codex를 사용하고, 다른 모델 호출 시(API Key, ollama)에는 커스텀 CLI를 호출하도록 해서 Codex의 파이프라인 로직은 그대로 이용하도록 하고 싶은거야. 다른 모델 호출 시 커스텀 codex cli를 호출하고 있는지 확인해줘.

## 변경 내용

- 서비스 AI 모델 목록의 첫 항목을 `Codex` 단일 항목으로 정리했다.
- `Codex` 선택값은 `codex`로 처리하고 일반 `codex` CLI 로그인 세션을 사용하도록 고정했다.
- OpenAI/Gemini/Ollama 모델 항목 설명에 `커스텀 Codex CLI 경유`를 표시했다.
- AI 진행 이벤트 provider 정보에 `일반 codex` 또는 `커스텀 Codex CLI` 실행 경로 라벨을 포함했다.
- 시스템 설정의 Codex 실행 CLI 입력은 일반 codex 기준으로 고정했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `src/model/struct/ai_settings.py`
- `src/model/struct/codex_runtime.py`
- `src/app/page.system/view.ts`
- `src/app/page.system/view.pug`
- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-05-13/159-codex-top-model-custom-cli-routing.md`

## 확인 결과

- 저장된 Codex 세션 `019e1ef7-5550-71e1-96f2-571b116fb678`를 resume해 이전 작업 맥락을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile`로 변경 Python 파일 문법 검사를 통과했다.
- `/usr/local/bin/codex --version`으로 일반 Codex CLI를 확인했다.
- `codex/codex-rs/target/debug/codex --version`으로 커스텀 Codex CLI 실행 파일을 확인했다.
- `codex_runtime._run_codex()`에서 `provider["type"] == "codex"`는 일반 Codex CLI, 그 외 provider는 `self.codex_executable()` 커스텀 CLI를 호출하는 분기를 확인했다.
- `wiz_project_build(projectName=main, clean=false)` 빌드에 성공했다.
