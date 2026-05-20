# 284. 서비스 관리와 생성 화면 초기 로딩 경량화

## 요청

> 서비스 관리 화면에 처음 진입했을 때 로딩 속도가 처참할정도로 너무 느려. 그냥 서비스 목록 먼저 불러와서 바로 목록 보여주고, 첫 번째 서비스의 기본 정보들만 가져와서 갱신하고, 나머지 상세 정보는 그 후에 가져오거나 따로따로 가져오도록 하면 되는데, 지금은 최적화가 안되어있어서 너무 느려.
> 그리고 새 서비스 만들기 시에도 템플릿을 가져오는 기능 때문인지 너무 느려. 이 부분도 최적화를 진행해줘.

## 변경 파일

- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services.create/api.py`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/model/struct/services_runtime.py`
- `src/model/struct/templates.py`
- `tests/api/test_service_migration.py`
- `devlog.md`
- `devlog/2026-05-20/284-service-management-fast-load.md`

## 변경 내용

- 서비스 관리 초기 `load` API에서 서버 목록 조회를 분리하고, 마이그레이션/생성 모달에서 필요할 때 `support_options`로 불러오도록 변경했다.
- 서비스 상세 최초 선택 시 `detail_service`를 lightweight 모드로 호출해 기본 정보와 런타임 상태를 먼저 렌더링하고, certbot 인증서 같은 느린 부가 정보는 이후 백그라운드로 갱신하도록 했다.
- 서비스 생성 초기 `load` API는 템플릿 요약만 반환하도록 줄이고, 템플릿 상세/AI 모델/도메인 인증서 목록은 화면 렌더 후 또는 해당 단계 진입 시점에 가져오도록 분리했다.
- 도메인 옵션 생성 시 인증서 목록을 도메인별로 반복 조회하지 않고 한 번만 읽어 요약하도록 정리했다.
- 템플릿 모델에 목록 전용 `load_summaries` 경로를 추가해 생성 화면 최초 진입 시 모든 템플릿 schema/default/files를 읽지 않도록 했다.
- 마이그레이션 정적 계약 테스트를 서버 목록 지연 로딩 구조에 맞춰 갱신했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/app/page.services/api.py project/main/src/app/page.services.create/api.py project/main/src/model/struct/services_runtime.py project/main/src/model/struct/templates.py`
- `wiz_project_build(projectName="main", clean=false)` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight tests.api.test_service_migration tests.api.test_images_templates_catalog.ImagesStaticContractTest`
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣고 `https://infra-dev.nanoha.kr/services/create` HEAD 요청 200 확인
- 같은 쿠키로 `page.services/load`, `page.services.create/load` POST 요청은 로그인 세션이 없어 401 `AUTHENTICATION_REQUIRED` 응답 확인

## 남은 리스크

- 인증 세션이 없어 실제 브라우저에서 서비스 목록 최초 렌더 시간과 생성 화면 템플릿 상세 지연 로딩 체감은 직접 확인하지 못했다.
