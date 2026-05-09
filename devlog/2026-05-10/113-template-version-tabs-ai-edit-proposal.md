# 113. 템플릿 상세 버전 탭 분리와 AI 수정안 적용/롤백 추가

## 사용자 요청

> 템플릿 상세에서 버전 이력, 버전 내용을 그냥 아예 탭 형식으로 분리해줘. 그리고 현재 버전 이력, 버전 내용 위치에 AI를 이용한 수정 기능을 추가해줘. AI 수정 기능은 원하는 바를 작성하면 현재 템플릿 정보를 같이 프롬프트로 추가해서 수정할 수 있도록 해야하고, 변경 내용을 정리해서 어떤 내용이 바뀌었는지 한눈에 알아볼 수 있도록 따로 보여주면서 롤백/적용을 할 수 있어야 해.
> 그리고 현재 AI 초안 기능은 오로지 새 초안 만들기로만 써야해.

## 작업 요약

- 템플릿 상세 편집 영역에 `버전` 탭을 추가하고, 그 안에서 `버전 이력`과 `버전 내용`을 하위 탭으로 분리했다.
- 기존 우측 버전 패널 위치를 AI 수정 패널로 교체하고, 모델 선택 Search Select, 수정 요청 입력, Thinking 스트림 표시를 추가했다.
- AI 수정 요청에 현재 템플릿 메타데이터와 `docker-compose.yaml`, `values.default.yaml`, `values.schema.json`, `README.md` 내용을 함께 전달하도록 연결했다.
- AI가 생성한 수정안을 바로 덮어쓰지 않고 변경 요약으로 먼저 보여주며, 적용 전후 상태를 기준으로 롤백/적용할 수 있게 했다.
- AI 초안 모달의 적용 방식 선택 UI를 제거하고 새 템플릿 초안 생성 전용 흐름으로 정리했다.

## 변경 파일

- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `devlog.md`
- `devlog/2026-05-10/113-template-version-tabs-ai-edit-proposal.md`

## 검증

- `PYTHONDONTWRITEBYTECODE=1 python -m py_compile project/main/src/app/page.templates/api.py project/main/src/model/struct/ai_assistant.py`
- `wiz_project_build(projectName="main", clean=false)` 성공
