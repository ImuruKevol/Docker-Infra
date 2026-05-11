# 124. 서비스 생성 화면 AI 우선 UX와 자동 보정 컨텍스트 보강

- 날짜: 2026-05-11
- 요청: "새 서비스를 만들 때 기본적으로는 AI를 활용하여 자동 작성하는걸 메인으로 해줘. compose 및 설정 직접 작성에 대해서는 고급 사용자용으로 해야해. AI 활용하여 서비스 자동 구성 시 Docker Infra의 각종 요소(서비스, 도메인 설정 등등)에 맞도록 input, ouput을 신경써야 하고, 템플릿 관리 쪽에 있었던 실패 시 자동 재호출같은 로직도 당연히 신경써야해. 최대한 개발을 거의 모르는 일반 사용자 기준으로 UI/UX를 개선해줘."

## 작업 내용

서비스 만들기 첫 단계를 AI 자동 구성 중심으로 재배치했다. 일반 사용자는 만들고 싶은 서비스를 자연어로 입력하고 예시 버튼을 눌러 초안을 만들 수 있으며, Compose 직접 작성은 접힌 고급 사용자 영역으로 이동했다.

AI 생성 요청에는 Docker Infra가 관리하는 서비스 메타데이터, Compose 구성, 도메인/SSL, 포트, 볼륨, secret, 자동 보정 범위를 함께 전달하도록 보강했다. 서버 측 AI assistant도 이 컨텍스트를 프롬프트와 요청 데이터에 포함하고, 검증 실패 시 재호출 상태에 재시도 횟수를 표시하도록 정리했다.

## 변경 파일

- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `src/model/struct/ai_assistant.py`
- `devlog.md`
- `devlog/2026-05-11/124-service-create-ai-first-ux.md`

## 검증

- `python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/src/app/page.services.create/api.py`
- `wiz_project_build(projectName="main", clean=false)`

두 검증 모두 성공했다.
