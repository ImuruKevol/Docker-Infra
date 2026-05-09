# 082. 서버 Compose 가져오기 wizard 통합과 서비스 상세 운영 요약 보강

- 날짜: 2026-05-09
- 요청: "서비스 관리 관련해서 남은 작업들을 이어서 진행해줘."

## 변경 요약

- 서버 관리 화면의 Compose 파일 선택 흐름을 즉시 서비스 등록 API 호출에서 `/services/create` 생성 wizard 이동으로 변경했다.
- 서비스 생성 화면에서 `import_node_id`, `import_path`, `import_name` query를 받아 서버의 Compose 파일을 읽고, wizard 구성요소와 사전 점검 흐름으로 이어지도록 `load_import` API와 `services_wizard.prepare_import`를 추가했다.
- 가져온 Compose의 `container_name`, `hostname`은 wizard 렌더링 과정에서 제거해 Docker Infra가 컨테이너 이름을 자동 관리하도록 했다.
- 서비스 상세 상단에 실행 서버와 인증서 적용 상태를 직접 표시했다.
- 컨테이너 목록은 기본 화면에서 운영 상태 중심 카드로 재구성하고, ID/이미지/raw 상태는 고급 정보 영역으로 이동했다.
- 문제 상태는 raw error 대신 원인 요약과 `상태 다시 확인`, `처리 로그 보기`, `다시 적용` 조치 버튼으로 표시하도록 했다.
- 남은 TODO 문서에서 P6/P6-1 완료 항목을 갱신했다.

## 변경 파일

- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.services.create/api.py`
- `src/app/page.services.create/view.ts`
- `src/app/page.services.create/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `src/model/struct/services_wizard.py`
- `tests/api/test_services_preflight.py`
- `docs/docker-infra-remaining-todo.md`
- `docs/docker-infra-development-todo.md`

## 검증

- `python -m py_compile src/app/page.services.create/api.py src/model/struct/services_wizard.py tests/api/test_services_preflight.py`
- `python -m unittest tests.api.test_services_preflight`
- `python -m unittest tests.api.test_images_templates_catalog`
- `wiz_project_build(projectName="main", clean=false)`

모두 통과했다.
