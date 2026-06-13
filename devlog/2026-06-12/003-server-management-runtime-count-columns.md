# 서버 관리 목록 런타임 수량 컬럼과 설명 문구 정리

## 요청

- 리뷰 ID: `xoagdttdfmoppjomsakgzevrinkfhcec`
- 제목: 서버 관리 화면 보완
- 원 요청: "작업 시작"
- 리뷰어 요청:
  - 각 서버당 서비스가 몇 개인지, 컨테이너가 몇 개가 띄워져있는지 컬럼 추가
  - Host 컬럼에 마스터 서버의 경우 "사설" 텍스트가 추가되는데 제거
  - 서버 컬럼에 "이 서비스가 실행 중인 서버", "저장된 ~~~~" 텍스트 제거. 상세 화면에서도 제거

## 변경 사항

- 서버 목록 API 응답에 최신 node metric의 컨테이너 스냅샷을 기반으로 `runtime_summary`를 추가했다.
- `runtime_summary`에서 등록 서비스 수는 서비스 매칭 로직 기준 고유 서비스 수로, 실행 컨테이너 수는 running 상태 컨테이너 수로 계산했다.
- 서버 관리 목록에 `서비스`, `실행 컨테이너` 컬럼을 추가하고, 상세 갱신 후 목록 수량도 같이 갱신되도록 했다.
- 마스터 서버 Host 표시에서 `사설` 접두어를 제거했다.
- 서버 목록/상세 헤더의 역할 설명 문구를 제거하고 중심 서버 수정 안내 문구도 간결하게 바꿨다.
- 서버 관리 정적 계약 테스트를 새 컬럼과 제거된 문구 기준으로 갱신했다.

## 변경 파일

- `src/model/struct/nodes.py`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `tests/api/test_nodes_swarm.py`
- `devlog.md`
- `devlog/2026-06-12/003-server-management-runtime-count-columns.md`

## 검증

- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_nodes_swarm.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_node_reporter.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes.py src/app/page.servers/api.py`
- 확인: `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `https://infra-dev.nanoha.kr/servers` 브라우저 접근을 시도했으나 인증 화면(`/access`)으로 리다이렉트되어 실제 서버 목록 화면은 확인하지 못했다. 페이지 오류는 없었다.
- 참고: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_wiz_structure_contract.py`는 기존 구조 계약 불일치와 대형 파일 제한 등 다수의 기존 실패로 통과하지 못했다.
