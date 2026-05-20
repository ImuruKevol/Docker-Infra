# 282. 새 템플릿 작성 방식 선택과 clone 기반 생성 UX 추가

## 요청

> 새 Compose 템플릿 추가 시 AI로 초안을 작성할건지 선택할 수 있게 하고, 선택하면 초안 작성 카드가 나오고 직접 작성을 누르면 각 항목들을 직접 입력할 수 있게 분리해줘. 지금은 AI 초안 카드와 직접 작성 부분이 한 번에 보여서 정신사나워.
>
> 그리고 AI와 직접 작성 모두 기존 템플릿을 기반으로 clone을 뜬 후 수정하여 새 템플릿을 만들 수 있는 기능을 추가해줘.

## 변경 파일

- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-20/282-template-create-mode-clone-flow.md`

## 변경 내용

- 새 템플릿 버튼 클릭 시 바로 편집 폼을 열지 않고 `AI로 초안 작성`과 `직접 작성` 중 하나를 선택하는 시작 화면을 추가했다.
- AI 선택 시 AI 초안 카드만 표시하고, 직접 작성 폼은 AI 초안 생성 후에만 보이도록 분리했다.
- 직접 작성 선택 시 기본 표준 파일 또는 선택한 기반 템플릿 clone을 편집하는 화면만 보이도록 분리했다.
- 신규 작성 시작 화면, AI 초안 카드, 직접 작성 카드에 `기반 템플릿` 선택을 추가했다.
- 기존 템플릿을 clone할 때 기존 파일/기본값/태그를 복사하되 새 namespace와 이름으로 새 템플릿을 만들도록 처리했다.
- AI clone 기반 생성 시 AI 응답 namespace가 기존 템플릿 namespace로 되돌아가 기존 템플릿을 덮어쓰지 않도록 현재 새 namespace를 유지했다.
- 저장 버튼은 작성 방식 선택 단계나 clone 로딩 중에는 비활성화되도록 보강했다.
- 정적 계약 테스트를 새 작성 방식 선택, clone 옵션, 편집 폼 분리 조건 기준으로 갱신했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.templates/api.py src/model/struct/templates.py src/model/struct/templates_seed.py src/model/struct/ai_assistant.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`
- `curl`로 `http://127.0.0.1:3001/api/system/health` 200 확인
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣고 Playwright로 로컬/실도메인 `/templates` 접근을 시도했으나 둘 다 `/access`로 리다이렉트됨. console/page error는 없었다.

## 남은 리스크

- 인증 비밀번호 환경변수가 없어 인증 후 실제 `/templates` 화면에서 새 작성/clone 플로우를 브라우저로 직접 확인하지 못했다.
- 실제 AI 초안 생성 호출은 비용과 시간이 큰 작업이라 수행하지 않았다.
