# 303. 서비스 생성 다음 버튼을 생성 방식별 주 동작과 연결

## 원 요청

서비스 생성 시 템플릿 기반에서는 다음 버튼과 템플릿 적용 버튼이 아예 따로 놀고 있어서 다음 버튼이 의미가 없어. AI 자동 구성도 그렇고, 직접 작성도 그래.
다음 버튼이 의미가 있도록 UX를 수정해줘.

## 변경 파일

- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `tests/api/test_services_preflight.py`

## 변경 내용

- 서비스 생성 1단계의 하단 다음 버튼이 현재 생성 방식의 주 동작을 직접 수행하도록 연결했다.
- 템플릿 모드에서는 `템플릿 적용 후 다음`, AI 모드에서는 `AI 생성 후 다음`, 직접 작성 모드에서는 `Compose 적용 후 다음`으로 버튼 문구와 로딩 아이콘을 바꾸도록 했다.
- 기존 템플릿 적용, AI 생성, Compose 적용 함수가 성공 여부를 반환하고 성공 시 다음 단계로 이동하도록 정리했다.
- 1단계 검증 순서를 서비스명 입력 확인 후 초안 확인으로 조정해 버튼 클릭 시 더 자연스러운 오류 메시지가 나오도록 했다.
- 정적 계약 테스트에 다음 버튼 주 동작 연결과 템플릿 바인딩 검증을 추가했다.

## 검증

- `wiz_project_build(projectName=main, clean=false)` 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest` 통과
- `git diff --check -- src/app/page.services.create/view.ts src/app/page.services.create/view.pug tests/api/test_services_preflight.py` 통과
- devmode 쿠키를 붙인 `/services`, `/services/create` HEAD 요청 200 확인
- Playwright 브라우저 검증으로 `/services/create`에서 템플릿, AI, 직접 작성 모드의 하단 버튼 문구 전환 확인
