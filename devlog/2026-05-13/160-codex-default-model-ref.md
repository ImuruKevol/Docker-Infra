# 160. AI 모델 선택 기본값 Codex 우선 고정

## 사용자 요청

? 작업이 진행이 안된 것 같아. 확인하고 이어서 다시 진행해줘.

## 변경 내용

- 저장된 Codex 세션을 resume해 이전 작업의 남은 확인 포인트를 다시 확인했다.
- AI 수정 및 점검 화면의 모델 목록 기본 선택값을 항상 `codex`로 반환하도록 조정했다.
- OpenAI/Gemini/Ollama 설정이 켜져 있어도 모델 목록 로드 시 상단 `Codex` 항목이 기본 선택되도록 했다.
- 기존 라우팅대로 `Codex`는 일반 codex CLI, API Key/Ollama 계열은 커스텀 Codex CLI를 사용하는 분기를 재확인했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `devlog.md`
- `devlog/2026-05-13/160-codex-default-model-ref.md`

## 확인 결과

- 저장된 Codex 세션 `019e1ef7-5550-71e1-96f2-571b116fb678`를 resume해 남은 수정 포인트를 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/src/model/struct/codex_runtime.py project/main/src/model/struct/ai_settings.py`를 통과했다.
- `codex_runtime._run_codex()`에서 `provider["type"] == "codex"`는 일반 Codex CLI, 그 외 provider는 `self.codex_executable()` 커스텀 CLI와 `--model-provider`를 사용하는 것을 확인했다.
- `wiz_project_build(projectName=main, clean=false)` 빌드에 성공했다.
- 빌드 산출물 `build/dist/build/main.js`에 AI 진행 이벤트의 `cli_label` 표시가 반영된 것을 확인했다.
