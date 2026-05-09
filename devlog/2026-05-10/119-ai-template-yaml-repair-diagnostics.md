# 119. AI 템플릿 수정안 YAML 보정 재요청 진단 강화

- 날짜: 2026-05-10
- 요청: 템플릿 수정안을 보낼 때 AI 보정 후에도 `Compose YAML을 파싱할 수 없습니다` 오류가 반복되는 문제를 해결.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `devlog.md`
- `devlog/2026-05-10/119-ai-template-yaml-repair-diagnostics.md`

## 변경 내용

- AI output 검증 실패 후 재요청할 때 `repair_diagnostics`를 추가해 줄번호가 붙은 `docker-compose.yaml`, `values.default.yaml`, `values.schema.json` 스니펫을 모델에 전달하도록 했다.
- YAML 파싱 오류가 발생하면 해당 줄만 패치하지 말고 전체 YAML을 유효한 Compose 객체 기준으로 다시 작성하도록 repair system prompt를 강화했다.
- `healthcheck.test` 아래에 `interval`, `timeout`, `retries`가 잘못 중첩되는 문제를 줄이기 위해 올바른 healthcheck 구조 예시와 sibling key 규칙을 repair prompt와 일반 template prompt에 추가했다.
- AI output 보정 재요청 횟수를 2회에서 3회로 늘렸다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/app/page.templates/api.py src/app/page.services/api.py src/app/page.services.create/api.py`
- WIZ `wiz_project_build(projectName="main", clean=false)` 성공
