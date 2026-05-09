# 112. AI 사용 화면 모델 선택과 Thinking 스트림 UI 추가

## 사용자 요청

> AI 사용하는 쪽에서 어떤 모델을 사용할건지 선택하는 메뉴가 없어
> 그리고 AI의 Thinking 과정도 스트리밍으로 표시를 해줘야 해
> 그리고 템플릿 초안 작성에서 새 템플릿/현재 템플릿 수정이라는게 너무 뭔가 UI/UX적으로 이상해.

## 작업 요약

- 템플릿 AI 초안, 신규 서비스 AI 자동 구성, 서비스 수정 AI 수정안 영역에 AI 모델 선택 Search Select를 추가했다.
- 시스템 AI 설정의 모델 캐시와 기본 런타임 설정을 기반으로 AI 사용 화면에서 선택 가능한 모델 옵션을 제공하도록 `ai_model_options` API를 추가했다.
- AI 생성 요청마다 `model_ref`를 받아 OpenAI, Gemini, Ollama 모델을 명시적으로 선택할 수 있도록 백엔드 provider 선택 로직을 보강했다.
- WIZ app API에 SSE 스트림 엔드포인트를 추가하고, `fetch()` + `ReadableStream`으로 Thinking/진행 이벤트를 UI에 표시하도록 연결했다.
- Gemini는 `includeThoughts` 기반 thought summary 스트림, Ollama는 `message.thinking` 필드, OpenAI는 API 제약상 raw reasoning 대신 진행 상태와 최종 reasoning summary를 표시한다.
- 템플릿 AI 모달의 작업 선택 UI를 `새 초안으로 열기`와 `선택 템플릿에 반영` 카드형 적용 방식으로 바꾸고, 기존 `새 템플릿 생성/현재 템플릿 수정` select를 제거했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
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
- `devlog/2026-05-10/112-ai-model-picker-thinking-stream.md`

## 검증

- `python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/src/app/page.templates/api.py project/main/src/app/page.services.create/api.py project/main/src/app/page.services/api.py`
- `wiz_project_build(projectName="main", clean=false)` 성공
