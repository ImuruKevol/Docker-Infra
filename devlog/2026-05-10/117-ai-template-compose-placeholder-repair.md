# 117. AI 템플릿 Compose placeholder YAML-safe 보정

## 사용자 요청

> 수정 요청을 했더니 여전히
> · Compose validation failed.
> · content: Compose YAML을 파싱할 수 없습니다.
> 이런 에러가 뜨고 있어

## 작업 요약

- AI 템플릿 프롬프트에 Compose scalar placeholder는 반드시 따옴표로 감싸도록 지시를 추가했다.
- AI가 `image: {{ image }}`, `- REGISTRATION_TOKEN={{ token }}`처럼 따옴표 없는 placeholder를 반환한 경우 정규화 단계에서 YAML-safe 문자열로 감싸도록 보정했다.
- AI가 코드 펜스로 `docker-compose.yaml`, `values.default.yaml`, `values.schema.json`, `README.md` 내용을 감싼 경우 파일 내용만 추출하도록 했다.
- `values.default.yaml`의 `...`, `---`, multiline scalar 기본값이 렌더링된 Compose YAML을 깨뜨리지 않도록 안전한 기본값으로 정리했다.
- Compose validation error 요약에 PyYAML의 `reason` 상세도 함께 표시하도록 했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `devlog.md`
- `devlog/2026-05-10/117-ai-template-compose-placeholder-repair.md`

## 검증

- `PYTHONDONTWRITEBYTECODE=1 python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/src/app/page.templates/api.py`
- `wiz_project_build(projectName="main", clean=false)` 성공
