# AI 템플릿 생성 공개 포트 매핑 규칙 보강

- 날짜: 2026-06-08
- ID: 012
- 리뷰 ID: nntedxverghioecrhsgmmcirynlzpgfq

## 사용자 원 요청

현재 템플릿을 AI로 생성 시 밖으로 publish하는 포트가 제대로 설정이 되지 않고 있음.
compose yaml 설정에 ports가 설정되어야 하는 서비스는 반드시 ports를 제대로 설정하도록 보완해줘.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `src/model/struct/template_ai.py`
- `src/app/page.templates/view.ts`
- `tests/api/test_services_preflight.py`

## 변경 내용

- 템플릿 AI 계약과 실제 생성 프롬프트에 공개 서비스 port 규칙을 추가했다.
- 브라우저/API/외부 접속용 서비스는 `expose`가 아니라 `services.<name>.ports`에 published-to-target 매핑을 명시하도록 했다.
- `metadata.public_endpoint`가 있는 AI 템플릿은 endpoint service/port가 Compose `ports`와 일치하는지 검증하게 했다.
- 공개 목적 요청인데 명시적인 published port 매핑이 없으면 AI output repair 루프로 되돌아가도록 검증 오류를 추가했다.
- 템플릿 편집 화면의 Compose 표준 안내에 공개 포트 기준을 추가했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/src/model/struct/template_ai.py project/main/src/app/page.templates/api.py`: 통과
- AI 템플릿 공개 포트 검증 단위 스크립트: `expose`만 있는 공개 endpoint는 실패, `{{ service_port }}:3000` 매핑은 통과 확인
- `wiz_project_build(projectName=main, clean=false)`: 통과
- `curl` DEV 확인: `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `https://infra-dev.nanoha.kr/dashboard` HTTP 200 확인
- `/opt/conda/envs/docker-infra/bin/python -m unittest project/main/tests/api/test_services_preflight.py`: 실패. 이번 변경과 무관한 기존 정적 기대값(`deploy_service_background`, `this.creationMode() === 'template'`) 불일치로 실패했다.
