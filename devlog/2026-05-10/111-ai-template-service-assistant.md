# 111. 템플릿/서비스 AI 생성 계약과 자동 구성 UI 연결

## 사용자 요청

> 이제 설정한 AI 모델들을 이용해서 템플릿 관리 화면과 서비스 관리 화면에 AI 기능을 추가해야해.
> 템플릿, 서비스 추가 및 수정 시 AI를 활용해서 Docker Infra에 최적화하여 사용자가 원하는 설정 및 값들을 자동으로 생성을 해야해.
> 그럼 일단 먼저 템플릿과 서비스의 설정에 대한 확실한 정의가 필요해. 확실하게 기능 정의 및 설정에 대해 확실하게 원하는 Input, Output을 정해놓고, AI 기능을 붙여줘.

## 작업 요약

- 템플릿 AI 입력/출력 계약을 `intent`, `mode`, `current`, `constraints` 입력과 `template`, `files`, `summary`, `warnings` 출력으로 고정했다.
- 서비스 AI 입력/출력 계약을 `intent`, `mode`, `form`, `components`, `base_content`, `templates`, `zones` 입력과 `form`, `components`, `template_id`, `summary`, `warnings` 출력으로 고정했다.
- 시스템 AI 설정에서 저장한 OpenAI, Gemini, Ollama 설정을 사용해 JSON 응답을 요청하고, Docker Infra 템플릿/서비스 구조로 정규화하는 모델을 추가했다.
- 템플릿 관리 화면에서 AI 초안 모달을 열어 Compose, 기본값, JSON Schema, README 초안을 생성하고 미리보기 검증 결과를 적용하도록 연결했다.
- 신규 서비스 생성 화면에서 선택된 템플릿 또는 가져온 Compose 기준으로 서비스 폼과 컴포넌트 설정을 AI가 채우도록 연결했다.
- 서비스 수정 모달에서 현재 서비스 설정과 요청을 기반으로 이미지, 포트, 환경변수, 볼륨, 도메인 수정안을 적용하도록 연결했다.
- AI 응답이 기존 Compose 렌더링과 어긋나지 않도록 서비스 컴포넌트 키는 현재 템플릿/서비스 정의를 우선 보존하도록 정규화했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `src/model/struct.py`
- `src/app/page.templates/api.py`
- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `src/app/page.services.create/api.py`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-05-10/111-ai-template-service-assistant.md`

## 검증

- `python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/src/model/struct.py project/main/src/app/page.templates/api.py project/main/src/app/page.services.create/api.py project/main/src/app/page.services/api.py`
- `wiz_project_build(projectName="main", clean=false)` 성공
