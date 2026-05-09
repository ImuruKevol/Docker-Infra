# 서비스 접속 흐름을 캔버스형 시스템 구성도로 전환

- 날짜: 2026-05-09
- 작업 번호: 091

## 사용자 요청

서비스 접속 흐름 표시가 카드가 나열된 형태가 아니라, 제안서에 들어가는 시스템 구성도처럼 캔버스 위에 그려지는 느낌이어야 한다는 요청.

## 변경 내용

- 기존 가로 카드형 흐름 표시를 제거하고, 단일 캔버스 영역 안에 시스템 구성도가 그려지도록 변경했다.
- 캔버스 배경에 그리드 질감을 추가해 도면/구성도 느낌을 강화했다.
- `사용자`, `접속 주소`, `Docker Infra`, `서비스`, `내부 구성` 레이어를 상단에 표시했다.
- SVG 곡선과 화살표를 사용해 사용자 접속, nginx 연결, 내부 연결 관계를 표시했다.
- Compose/nginx/domain/runtime 기반 `service_flow` 데이터는 유지하고, 프론트 렌더링만 캔버스형 다이어그램으로 전환했다.
- 서비스 목록이 함께 보이는 상세 화면에서도 가로 문서 스크롤이 생기지 않도록 캔버스 좌표계와 노드 폭을 압축했다.
- 첫 화면에서 노드가 과도하게 아래로 밀리지 않도록 캔버스 높이와 노드 Y 좌표를 조정했다.

## 변경 파일

- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `devlog.md`

## 검증

- `python -m compileall project/main/src/model/struct/services_flow.py project/main/src/app/page.services/api.py` 통과.
- `python -m unittest project/main/tests/api/test_services_preflight.py` 통과.
- WIZ 프로젝트 빌드 성공.
- `wiz.docker-infra.service` 재시작 후 active 확인.
- Playwright로 실제 `/services` 화면에서 Wiki.js 상세를 열고 캔버스, SVG 연결선, 레이어, 사용자 접속 범례가 렌더링되는 것을 확인했다.
- 1440px 화면 기준 문서 전체 가로 스크롤이 발생하지 않는 것을 확인했다.
