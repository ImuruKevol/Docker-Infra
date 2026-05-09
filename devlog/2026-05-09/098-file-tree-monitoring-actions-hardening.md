# 098. 파일 트리 홈 기본 경로·보호 경로와 모니터링/컨테이너/이미지 액션 보강

## 요청 원문

파일 트리는 기본적으로 홈 디렉토리를 표시하도록 하고, .으로 시작하는 숨김 파일/폴더를 보이기/숨기기 하는 토글 버튼도 추가해줘. 그리고 input을 경로 버튼들 오른족에 추가해서 경로를 입력 후 엔터를 누르면 바로 해당 경로로 가도록 해줘. 그리고 /, /etc 등 주요 시스템 디렉토리들에 대해서는 절대로 이름을 바꾸거나 이동, 삭제 등 동작이 안되도록 막아야 해. 주요 시스템 디렉토리는 Ubuntu 24.04 기준으로 알아서 blacklist를 판단해줘.
그리고 현재 파일 목록 불러오는 API가 너무 느려. 더 빠르게 해줘.

그리고 현재 local-master 서버는 공인 IP로 저장이 되어있는데, 표시는 그렇게 해도 되는데 실제 ssh 터미널 연결이나 파일 목록 불러오기 등 로직은 127.0.0.1을 활용하도록 하는게 더 빠르고 최적화가 될 것 같아.

모니터링 에이전트를 배포했다고 하는데 진짜 배포가 된건지 구분이 안가. 수집 중인 서버에 대해서는 깜빡이는 파란색 인디케이터같은걸 추가해서 정보 수집 중 이라는 표시를 해줘. 그리고 이미 구성이 된 서버는 버튼을 보일 필요가 없어. 그리고 모니터링 에이전트는 각 서버별로 서비스 데몬 식으로 실행되도록 해야해.

자원 즉시 갱신, 컨테이너 갱신 버튼은 삭제해줘.

서비스 관리 상세 - 고급 탭에서 실행 구성 요소에 각 버튼들이 활성화가 되지 않아.

그리고 odoo 로컬 이미지를 사용하지 않을 것 같아서 삭제하려고 했는데 삭제가 안된다고 에러가 떠. 확인해줘.

## 변경 파일

- `src/app/component.file.tree/view.ts`
- `src/app/component.file.tree/view.html`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/model/struct/file_tree.py`
- `src/model/struct/images_local.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/nodes_monitoring.py`
- `src/model/struct/nodes_runtime.py`
- `src/model/struct/nodes_runtime_files.py`
- `src/model/struct/nodes_terminal.py`
- `src/model/struct/nodes_view.py`

## 작업 내용

- 공통 파일 트리의 노드 기본 경로를 홈 디렉토리로 유지하고, 숨김 파일 표시 토글과 직접 경로 입력 이동 UI를 추가했다.
- 로컬/원격 파일 목록 API를 `os.scandir` 기반으로 바꿔 단일 디렉토리 조회 비용을 줄이고, 숨김 파일 필터링을 서버 측에도 적용했다.
- Ubuntu 24.04 기준 주요 시스템 경로(`/`, `/etc`, `/usr`, `/var`, `/proc`, `/sys`, `/dev`, `/run` 등)를 보호 경로로 표시하고 이름 변경, 이동, 삭제를 백엔드에서 차단했다.
- local-master는 role/name 기준으로도 로컬 노드로 판단해 파일 목록, Docker 명령, 웹 터미널, 이미지 명령에서 로컬 실행 경로를 우선 사용하도록 보강했다.
- 모니터링 에이전트 배포를 systemd 서비스(`docker-infra-node-exporter.service`) 방식으로 변경하고, 구성 결과를 노드 metadata에 기록했다.
- 서버 목록/상세에 수집 중 파란색 점멸 인디케이터와 모니터링 구성 완료 배지를 추가하고, 구성된 서버에서는 모니터링 구성 버튼을 숨기도록 했다.
- 서버 상세의 자원 즉시 갱신, 컨테이너 갱신 버튼을 제거했다.
- 서비스 상세 고급 탭의 구성요소 액션 버튼이 cached runtime의 `node_id` 누락 때문에 비활성화되지 않도록 완화하고, API/노드 런타임에서 컨테이너 ID prefix/full ID 매칭을 모두 지원하게 했다.
- 로컬 이미지 삭제 명령을 `docker image rm -f`로 바꿔 사용하지 않는 로컬 이미지, 특히 태그 충돌이나 dangling 참조가 있는 이미지 삭제 성공률을 높였다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/file_tree.py src/model/struct/nodes_runtime_files.py src/model/struct/local_command_catalog.py src/model/struct/nodes_monitoring.py src/app/page.servers/api.py src/app/page.services/api.py src/model/struct/nodes_runtime.py src/model/struct/images_local.py src/model/struct/nodes_view.py src/model/struct/nodes_terminal.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_node_reporter.NodeReporterStaticContractTest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_server_macros.ServerMacrosStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)`

## 비고

- 실제 odoo 이미지 삭제 명령은 운영 Docker 상태에 직접 destructive 실행하지 않고 코드 경로를 보강하는 방식으로 처리했다.
