# 095. 미등록 컨테이너 목록 제거와 서비스 고급 관리 Monaco/컨테이너 액션 적용

## 요청

서버 관리 화면에서 미등록 컨테이너를 리스팅하는 기능은 아예 삭제해줘. 그리고 서비스 상세로 가는 버튼과 서비스 관리 등 화면들에서 다른 화면으로 이동할 때 그냥 a 태그의 href로 이동하는데, angular의 routerLink 기능을 이용해서 로딩 없이 바로 이동하도록 수정해줘.

그리고 서비스 상세에서 고급 탭의 UI/UX가 너무 불편해. 레이아웃도 영 아니야. 개선을 한 후 각 컨테이너별 액션(실행, 중지, 재시작, 삭제)를 각각 할 수 있어야 해. 그리고 Compose, nginx 설정 원문 수정은 monaco editor를 사용하도록 해줘. 에디터는 두개나 배치하지 말고 1개만 배치해서 내용만 갈아끼도록 하고.

## 변경 파일

- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.services.create/view.ts`
- `src/model/struct/services_update.py`
- `tests/api/test_services_preflight.py`
- `tests/e2e/specs/servers.spec.ts`

## 작업 내용

- 서버 관리 개요에서 미등록 컨테이너 목록과 Compose 등록 진입 UI를 제거하고 등록된 서비스 중심 표만 남겼다.
- 서버 관리의 서비스 상세 이동을 `routerLink`와 `queryParams`로 전환했고 서비스 생성 화면의 완료/취소 이동도 `service.href()` 기반 Angular 라우팅으로 바꿨다.
- 서비스 상세 고급 탭을 원문 설정 목록, 단일 Monaco 편집기, 실행 구성요소 패널, 버전 이력 구조로 재배치했다.
- Compose 원문 저장 API와 서비스 상세 컨테이너별 실행/중지/재시작/삭제 API를 추가했다.
- 서비스 상세 컨테이너 액션 버튼과 단일 Monaco 편집기의 Compose/nginx 내용 전환 및 저장 흐름을 연결했다.
- 변경된 화면 계약에 맞춰 정적 API/UI 테스트와 E2E 기대값을 갱신했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.services/api.py src/model/struct/services_update.py` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight` 성공.
- `npm run e2e -- --list tests/e2e/specs/servers.spec.ts` 성공.
