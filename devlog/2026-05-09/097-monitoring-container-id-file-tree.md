# 097. 서버 모니터링 백그라운드 수집과 컨테이너 ID 액션·공통 파일 트리 적용

## 사용자 원 요청

각 서버에 node_exporter같은걸 배포하는 로직도 필요해. 서버별 리소스 기록은 백그라운드에서 돌아가야해.

그리고 이것과 별개로 서비스 상세의 고급 탭에서 각 컨테이너별 중지, 실행, 삭제 등 액션에 중대한 버그가 있어. 지금은 아마 컨테이너 이름같은걸로 액션을 실행하는 것 같은데, docker 컨테이너의 실제 id값을 기준으로 실행해야해. wiki 서비스쪽을 보면 web 컨테이너가 두개가 떠있는데 하나를 중지하니까 둘다 꺼지고, 하나만 삭제가 에러가 떴었어.
그리고 Compose 원문, nginx 설정 선택 토글 버튼들은 모나코 에디터 위쪽으로 이동하고, 실행 구성요소는 모나코 에디터 아래쪽으로 레이아웃을 수정해줘.
그리고 파일 트리 모달에서는 파일 및 폴더 업로드도 할 수 있어야 해. 서비스 상세 화면 뿐만 아니라, 템플릿 관리, 이미지 관리에서도 각 화면의 성격에 맞는 파일 및 폴더를 업로드할 수 있어야 해.
서버 상세에서도 파일 트리 탭을 추가해서 해당 서버의 파일 및 폴더를 확인할 수 있으면 좋겠어.
필요한 경우 업로드 뿐만 아니라 이름 변경, 삭제, 드래그&드랍을 통한 이동 등 기능을 지원하면 좋을 것 같아.
이러면 사실 파일 트리에 대한 기능을 공통 컴포넌트로 만들어서 각 화면들에 적용을 하는게 어떨까 싶기는 해.

## 변경 내용

- 서버별 `node_exporter` 계열 컨테이너(`docker-infra-node-exporter`)를 구성하는 로직과 서버 화면 API/버튼을 추가했다.
- 서버 metric 수집을 `nodes_monitoring.tick()` 백그라운드 thread로 실행하도록 추가하고, dashboard/servers/services 진입 시 짧게 트리거되도록 연결했다.
- Docker 컨테이너 목록 수집을 `docker ps -a --no-trunc` 기준으로 변경해 실제 컨테이너 ID를 사용하도록 했다.
- 서비스 runtime 상태가 모든 등록 서버의 컨테이너를 집계하고 각 컨테이너에 `node_id`, `node_name`, `node_host`를 포함하도록 수정했다.
- 서비스 상세 컨테이너 액션 API가 local master가 아니라 해당 컨테이너가 실제 존재하는 서버에서 ID 기준으로 실행되도록 수정했다.
- 서버 단일 컨테이너 액션도 실행 직전 해당 서버의 실제 컨테이너 ID 존재 여부를 다시 확인하도록 보강했다.
- 서비스 상세 고급 탭에서 Compose/nginx 선택 버튼을 Monaco 위로 이동하고, 실행 구성요소 목록을 Monaco 아래쪽으로 재배치했다.
- 공통 파일 트리 컴포넌트와 `/api/file-tree`, `/api/file-tree/upload` route를 추가해 파일/폴더 업로드, 이름 변경, 삭제, 드래그 앤 드랍 이동, 읽기를 지원했다.
- 공통 파일 트리를 서비스 상세, 서버 상세 파일 탭, 템플릿 관리, 이미지 관리에 적용했다.
- 관련 정적 계약 테스트를 보강했다.

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/file_tree.py`
- `src/model/struct/nodes_monitoring.py`
- `src/model/struct/nodes_runtime_files.py`
- `src/model/struct/nodes_runtime.py`
- `src/model/struct/nodes_registry.py`
- `src/model/struct/services_status.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct.py`
- `src/app/component.file.tree/app.json`
- `src/app/component.file.tree/view.ts`
- `src/app/component.file.tree/view.html`
- `src/route/api-file-tree/app.json`
- `src/route/api-file-tree/controller.py`
- `src/route/api-file-tree-upload/app.json`
- `src/route/api-file-tree-upload/controller.py`
- `src/app/page.dashboard/api.py`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.services.create/api.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.templates/view.ts`
- `src/app/page.templates/view.pug`
- `src/app/page.images/view.ts`
- `src/app/page.images/view.pug`
- `tests/api/test_node_reporter.py`
- `tests/api/test_services_preflight.py`
- `tests/api/test_images_templates_catalog.py`
- `devlog.md`
- `devlog/2026-05-09/097-monitoring-container-id-file-tree.md`

## 검증 결과

- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/file_tree.py src/model/struct/nodes_monitoring.py src/model/struct/nodes_runtime_files.py src/model/struct/nodes_runtime.py src/model/struct/services_status.py src/model/struct/local_command_catalog.py src/model/struct.py src/app/page.services/api.py src/app/page.servers/api.py src/app/page.dashboard/api.py src/app/page.services.create/api.py src/route/api-file-tree/controller.py src/route/api-file-tree-upload/controller.py config/docker_infra.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter tests.api.test_services_preflight tests.api.test_images_templates_catalog`
  - 결과: `Ran 16 tests in 0.019s OK (skipped=5)`
- 성공: WIZ build (`wiz_project_build`, `clean=false`)
  - 출력 위치: `/root/docker-infra/project/main/build/dist/build`
