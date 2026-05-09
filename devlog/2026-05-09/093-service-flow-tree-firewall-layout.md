# 서비스 플로우를 nginx 방화벽 중심 트리 구조로 재구성

- 날짜: 2026-05-09
- 작업 번호: 093

## 사용자 요청

서비스 플로우가 단순히 한 줄로 연결되는 형태가 아니라 트리 구조로 표현되길 원한다는 요청. 접속 주소와 Docker Infra는 각각 큰 카드로 그릴 필요 없이 사용자 아이콘 밑에 주소 뱃지를 표시하고, nginx는 세로로 긴 방화벽처럼 보이게 하며, 등록 서버와 컨테이너 구성이 트리 형태로 확실하고 컴팩트하게 보여야 한다는 요청.

## 변경 내용

- 기존 선형 레이어 구조를 제거하고, `사용자/주소 뱃지 -> nginx 방화벽 -> 등록 서버 -> 컨테이너 트리` 구조로 재배치했다.
- 접속 주소는 별도 카드 대신 사용자 아이콘 아래의 작은 뱃지로 표시한다.
- Docker Infra/nginx는 세로로 긴 방화벽 노드로 표현하고, 내부 brick 형태의 시각 요소를 추가했다.
- nginx 뒤에는 실제 proxy target의 등록 서버명을 표시하는 서버 노드를 배치했다.
- 컨테이너는 서버 아래 트리 형태로 배치하고, web 컨테이너에서 db 컨테이너로 내부 연결이 이어지도록 표현했다.
- 연결선은 직선형 elbow path로 변경해 트리 구조의 부모/자식 관계가 더 명확하게 보이도록 했다.
- 범례에 `서버 배치` 항목을 추가해 nginx 이후 서버 배치 흐름을 구분했다.

## 변경 파일

- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `devlog.md`

## 검증

- `python -m compileall project/main/src/model/struct/services_flow.py project/main/src/app/page.services/api.py` 통과.
- `python -m unittest project/main/tests/api/test_services_preflight.py` 통과.
- WIZ 프로젝트 빌드 성공.
- `wiz.docker-infra.service` 재시작 후 active 확인.
- Playwright로 실제 `/services` 화면에서 Wiki.js 상세를 열고 사용자 주소 뱃지, 세로형 nginx, 등록 서버, 서버 배치 범례, 내부 연결이 렌더링되는 것을 확인했다.
- 1440px 화면 기준 문서 전체 가로 스크롤이 발생하지 않는 것을 확인했다.
