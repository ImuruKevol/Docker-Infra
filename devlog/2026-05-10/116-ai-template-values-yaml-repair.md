# 116. AI 템플릿 values YAML 보정과 placeholder 기본값 보강

## 사용자 요청

> ollama로 생성한 gitlab-runner-stack 템플릿을 gemini 3.1 flash lite로 수정하려 했더니 아래 에러 메세지가 떴어.
>
> while scanning a simple key
>   in "<unicode string>", line 3, column 1:
>     gitlab_runner_registration_token ...
>     ^
> could not find expected ':'
>   in "<unicode string>", line 4, column 1:
>     gitlab_runner_executor: "shell"
>     ^

## 작업 요약

- 템플릿 AI 프롬프트에 `values.default.yaml`은 반드시 `key: value` 형태의 YAML mapping이어야 한다는 지시를 추가했다.
- 토큰, 비밀번호, 키 같은 민감 placeholder는 빈 문자열 기본값과 `metadata.generated_secrets`를 사용하도록 지시를 보강했다.
- AI 템플릿 정규화 단계에서 `values.default.yaml`을 YAML 객체로 먼저 검증하도록 했다.
- AI가 최상위 값을 `key value` 또는 `key = value` 형태로 반환한 경우에만 제한적으로 `key: value`로 보정한 뒤 다시 YAML로 파싱하도록 했다.
- Compose의 `{{ placeholder }}` 중 `values.default.yaml`에 빠진 키가 있으면 빈 기본값으로 보강해 렌더 검증 실패를 줄였다.
- 템플릿 preview 검증 실패 시 TemplateError의 추가 상세도 스트림 error에 포함되도록 보강했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `devlog.md`
- `devlog/2026-05-10/116-ai-template-values-yaml-repair.md`

## 검증

- `PYTHONDONTWRITEBYTECODE=1 python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/src/app/page.templates/api.py`
- `wiz_project_build(projectName="main", clean=false)` 성공
