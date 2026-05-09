# 서비스 관리 UX 검수 TODO와 생성/목록 자동화 보강

## 사용자 요청

서비스 관리 화면을 전체적으로 전수조사해서 사용자의 수준에 맞게 UI/UX가 최적화되어있는지, 자동화가 되어있는지 검수하고, 검수 내용을 이유와 기준까지 포함한 별도 TODO 문서로 작성한 뒤 작업들을 순서대로 진행해달라고 요청했다.

## 변경 파일

- `docs/service-management-audit-todo.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services.create/api.py`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/model/struct/services_wizard.py`
- `src/model/struct/templates_seed_shared.py`
- `src/model/struct/templates_seed_web_stacks.py`
- `src/model/struct/templates_seed_business_stacks.py`

## 작업 내용

- 서비스 관리 전용 검수 TODO 문서를 추가하고, 검수 기준, 이유, 완료 기준, 실행 순서를 정리했다.
- `/services` 목록 진입 시 첫 서비스 상세를 기다리지 않도록 분리하고, 상세 응답 race 방지 token을 추가했다.
- 목록 API에서 편집용 option 로딩을 제거하고, 서비스 수정 모달을 열 때 도메인 option을 지연 로드하도록 분리했다.
- `/services/create` 일반 생성 흐름에서 템플릿 선택을 필수화하고 기본 `nginx:alpine` fallback을 제거했다.
- 생성 API에서도 템플릿 또는 Compose import source가 없으면 preflight/create를 차단하도록 검증을 추가했다.
- 기본 템플릿 metadata에 공개 endpoint, 사용자용 구성요소 라벨, 자동 생성 secret 필드를 추가했다.
- 서비스 생성용 템플릿 detail API에서 DB/app secret 값을 생성 시점마다 랜덤으로 반영한 Compose preview를 반환하도록 했다.
- 생성 화면 2단계의 일반 영역에서는 이미지/포트 직접 입력을 제거하고, 직접 조정은 고급 설정 안으로 옮겼다.
- 도메인 연결 포트 선택에서 공개 endpoint를 추천 대상으로 우선 노출하도록 했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest` 통과
- `wiz_project_build(projectName="main", clean=false)` 통과
