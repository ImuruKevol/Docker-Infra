# 118. AI output 검증 실패 시 모델 재요청 보정 루프 적용

- 날짜: 2026-05-10
- 요청: AI API 모델이나 Ollama를 사용해 새 템플릿/서비스를 만들거나 수정할 때, 생성된 output이 정상적으로 저장/검증되지 않으면 코드에서 직접 보정하지 말고 에러 내용을 AI에 다시 요청해 output을 보정하도록 변경.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `devlog.md`
- `devlog/2026-05-10/118-ai-output-repair-retry.md`

## 변경 내용

- 템플릿/서비스 AI 생성 결과가 JSON 파싱, YAML/JSON 파일 검증, Compose 렌더링/검증에서 실패하면 같은 provider/model에 원래 요청, 이전 output, 검증 오류 내용을 다시 전달해 최대 2회 보정 요청하도록 변경했다.
- 스트리밍 생성 경로도 검증 실패 후 보정 재요청 상태를 전달하고, 보정된 최종 output만 `done` 이벤트로 반환하도록 정리했다.
- provider 미설정, provider 요청 실패, 연결 실패처럼 AI가 output을 고칠 수 없는 오류는 보정 재요청하지 않고 기존처럼 즉시 오류로 반환하도록 분리했다.
- 코드에서 AI output의 compose placeholder, values YAML, 기본값을 직접 고치던 보정 흐름은 제거하고, 템플릿 파일 검증 실패는 AI 재요청으로 넘기도록 정리했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/src/app/page.templates/api.py project/main/src/app/page.services/api.py project/main/src/app/page.services.create/api.py`
- WIZ `wiz_project_build(projectName="main", clean=false)` 성공
