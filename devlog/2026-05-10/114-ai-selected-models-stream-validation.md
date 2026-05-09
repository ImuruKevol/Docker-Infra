# 114. AI 사용 모델 선택 범위와 진행 스트림 표시 정리

## 사용자 요청

> 모델은 전부 다 표시하는게 아니고 시스템 설정에서 선택한 모델만 표시를 하는거야.
> 그리고 현재 Thinking Stream에 출력되는 텍스트들이 단어 단위로 전부 잘려서 단어 하나하나가 한줄로 표시되고 있어. 보니까 어차피 "\n" 텍스트도 오는걸로 봐서 이걸로 그냥 나누면 될 것 같은데.
> 그리고 생각 과정이 너무 전부 다 표시되어서 정신사나워. 반드시 필요한 내용들만 표시하도록 해줘.
> 그리고 결과가 최종적으로 아래와 같이 출력되고 있어. 현재 제약 사항과 validation을 고려해서 AI 결과를 생성하도록 해줘.
> status · AI 응답을 Docker Infra 설정으로 검증합니다.
>
> error · Compose validation failed.

## 작업 요약

- AI 사용 화면의 모델 옵션을 시스템 설정에서 선택한 OpenAI, Gemini, Ollama 모델만 표시하도록 제한했다.
- API 요청에서 선택 모델이 시스템 설정에 등록된 모델이 아니면 거부하도록 백엔드 검증을 추가했다.
- OpenAI/Gemini/Ollama 스트림에서 raw reasoning/thought chunk를 UI로 직접 노출하지 않고, 진행 상태와 최종 요약 중심으로 표시하도록 정리했다.
- 템플릿 생성/수정, 서비스 생성/수정 화면의 AI 진행 표시를 `\n` 기준으로 합치고 중복/과도한 줄을 줄이도록 변경했다.
- AI 프롬프트와 context에 Docker Infra Compose validation 계약을 추가해 healthcheck, overlay network, forbidden 필드 등 현재 검증 제약을 고려하도록 강화했다.
- validation 실패 시 `Compose validation failed.`만 보이지 않도록 주요 path/message 상세를 스트림 error 메시지에 함께 포함하도록 보강했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-05-10/114-ai-selected-models-stream-validation.md`

## 검증

- `PYTHONDONTWRITEBYTECODE=1 python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/src/app/page.templates/api.py project/main/src/app/page.services/api.py project/main/src/app/page.services.create/api.py`
- `wiz_project_build(projectName="main", clean=false)` 성공
