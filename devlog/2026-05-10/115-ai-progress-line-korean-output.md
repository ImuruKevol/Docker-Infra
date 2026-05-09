# 115. AI 진행 상태 갱신 표시와 한국어 결과 생성 지시 보강

## 사용자 요청

> 중간 과정을 아예 생략해버리니 진행 중인지 구분이 안가는 문제가 있어.
> 줄 단위 텍스트들을 하나의 div에 계속 replace해가면서 보여주더라도 뭔가 AI 모델이 생각 중이라는걸 확실하게 알 수 있으면 좋을 것 같아. 지금은 결과를 모두 받아온 후 그냥 chars로 글자 수만 표현이 되고 있는 것 같아. 그리고 결과 요약 메세지 및 설명, readme는 한글로 만들도록 해줘.

## 작업 요약

- AI 스트림의 `delta` 이벤트를 진행 표시에서 버리지 않고, 하나의 `생각 중` 행으로 계속 갱신해 표시하도록 변경했다.
- 스트리밍 중인 JSON 조각을 기준으로 `템플릿 메타데이터 작성 중`, `Compose 작성 중`, `기본값 작성 중`, `Schema 작성 중`, `README 작성 중`, `컴포넌트 설정 작성 중` 같은 현재 생성 섹션을 추정해 보여주도록 했다.
- 템플릿 생성/수정, 서비스 생성/수정 AI 진행 패널에 spinner 아이콘을 추가해 모델이 응답을 생성 중임을 명확히 표시했다.
- AI system prompt에 summary, warnings, thinking_summary, description, README.md 등 사용자 노출 텍스트는 한국어로 작성하도록 지시를 추가했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-05-10/115-ai-progress-line-korean-output.md`

## 검증

- `PYTHONDONTWRITEBYTECODE=1 python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/src/app/page.templates/api.py project/main/src/app/page.services/api.py project/main/src/app/page.services.create/api.py`
- `wiz_project_build(projectName="main", clean=false)` 성공
