# 서비스 플로우 구성도 좌표계 통합과 화살표 정렬 수정

- 날짜: 2026-05-09
- 작업 번호: 092

## 사용자 요청

서비스 플로우 구성도의 화살표 위치가 많이 꼬여 있고, 각 요소의 width/height가 제대로 잡히지 않는 문제를 수정해달라는 요청. 필요하면 직접 플로우 엔진을 개발하거나 적절한 npm 라이브러리를 적용해도 된다는 의견을 전달받았다.

## 원인 및 판단

- 기존 구현은 노드는 HTML absolute 좌표로 배치하고, 연결선은 별도 SVG `viewBox`로 그렸다.
- SVG가 실제 컨테이너 폭에 맞춰 스케일되는 동안 HTML 노드는 고정 px 좌표를 유지해, 같은 데이터 좌표라도 선과 노드가 서로 다른 위치에 렌더링됐다.
- npm 라이브러리도 확인했지만, Angular 전용 그래프 라이브러리는 현재 프로젝트 Angular 버전과 peer dependency가 맞지 않거나, 단순 시스템 구성도에는 과한 편이었다.
- 이 문제는 레이아웃 알고리즘보다 좌표계 분리가 핵심이므로, 노드와 연결선을 같은 SVG 좌표계에서 렌더링하는 방식이 더 안정적이라고 판단했다.

## 변경 내용

- 서비스 플로우 캔버스의 노드와 연결선을 모두 하나의 SVG 안에서 렌더링하도록 변경했다.
- 노드는 SVG `foreignObject`로 렌더링해 기존 카드 스타일과 아이콘 표현은 유지하면서, 연결선과 동일 좌표계로 맞췄다.
- SVG `preserveAspectRatio="xMidYMid meet"`를 사용해 화면 폭이 달라져도 노드와 화살표가 함께 스케일되도록 했다.
- 노드별 width/height를 엔진 좌표에 명시해 최소 크기가 안정적으로 유지되도록 했다.
- 캔버스 레이어, 범례, 배경 그리드도 SVG 내부로 옮겨 구성도 전체가 하나의 도면처럼 움직이도록 했다.

## 변경 파일

- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `devlog.md`

## 검증

- `python -m compileall project/main/src/model/struct/services_flow.py project/main/src/app/page.services/api.py` 통과.
- `python -m unittest project/main/tests/api/test_services_preflight.py` 통과.
- WIZ 프로젝트 빌드 성공.
- `wiz.docker-infra.service` 재시작 후 active 확인.
- Playwright로 실제 `/services` 화면에서 Wiki.js 상세를 열고 SVG 캔버스, 노드 5개, 연결선 5개가 렌더링되는 것을 확인했다.
- Playwright에서 1440px 화면 기준 문서 가로 스크롤이 발생하지 않고, 노드 최소 폭/높이가 정상 범위로 잡히는 것을 확인했다.
