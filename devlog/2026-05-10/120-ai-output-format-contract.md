# 120. AI output 포맷 계약과 values 기본값 객체 반환 규칙 추가

- 날짜: 2026-05-10
- 요청: AI가 생성한 `values.default.yaml`이 YAML 객체로 파싱되지 않는 오류가 계속 발생하므로, output으로 생성할 내용들의 포맷과 규칙을 확실하게 정리해서 사용하도록 개선.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `devlog.md`
- `devlog/2026-05-10/120-ai-output-format-contract.md`

## 변경 내용

- 템플릿/서비스 AI 응답에 적용할 `output_format` 계약을 추가하고 생성 요청, 스트리밍 요청, 보정 재요청 컨텍스트에 모두 포함했다.
- 템플릿 output의 `template`, `files.docker-compose.yaml`, `files.values.default.yaml`, `files.values.schema.json`, `files.README.md`별 필수 타입과 규칙을 명시했다.
- `values.default.yaml`은 AI가 손으로 작성한 YAML 문자열 대신 바깥 JSON의 object로 반환하도록 우선 규칙을 정했다. 앱은 기존 정규화 경로에서 object를 안전한 YAML 텍스트로 직렬화한다.
- `values.default.yaml` 검증 실패 오류에 기대 포맷 정보를 포함해, 다음 AI 보정 요청에서 어떤 형식으로 고쳐야 하는지 명확히 전달되도록 했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/app/page.templates/api.py src/app/page.services/api.py src/app/page.services.create/api.py`
- `/opt/conda/envs/docker-infra/bin/python`으로 values object YAML 직렬화/파싱 확인
- WIZ `wiz_project_build(projectName="main", clean=false)` 성공
