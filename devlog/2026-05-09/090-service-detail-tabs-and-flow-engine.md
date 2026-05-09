# 서비스 상세 탭 분리와 Compose/nginx 기반 접속 흐름 표시 추가

- 날짜: 2026-05-09
- 작업 번호: 090

## 사용자 요청

서비스 상세 화면에 너무 많은 정보와 중복 정보가 한 번에 표시되고 있으므로 적당히 탭으로 나누고, 로그와 백업은 별도 탭으로 분리해달라는 요청. 또한 사용자가 서비스 URL로 접근했을 때 nginx와 컨테이너가 어떻게 연결되는지, Compose와 nginx 설정을 기준으로 자동 표시하는 Docker Infra용 플로우 엔진을 만들어달라는 요청.

## 변경 내용

- 서비스 상세 상단 요약에서 백업/최근 처리 중복 정보를 제거하고 현재 상태, 접속 주소, 서버/인증서, 구성요소 중심으로 줄였다.
- 상세 본문을 `구성`, `로그`, `백업`, `고급` 탭으로 분리했다.
  - `구성`: 접속 흐름과 실행 상태 요약을 표시한다.
  - `로그`: 배포, 되돌리기, 백업 operation 목록과 상세 로그 진입을 표시한다.
  - `백업`: 이미지 백업, 현재 상태 백업, 되돌리기 액션을 분리했다.
  - `고급`: Compose 원문, nginx 원문, 버전 이력, 실행 상세를 모았다.
- `services_flow` struct를 추가해 서비스 상세 응답에 `service_flow`를 포함하도록 했다.
- 플로우 엔진은 Compose의 service, port, expose, depends_on, environment 내부 참조와 서비스 도메인/nginx 메타데이터를 조합한다.
- Wiki.js처럼 외부 접속 대상인 web 컨테이너와 내부 전용 DB 컨테이너가 함께 있는 경우, `사용자 -> 도메인 -> Docker Infra 연결(nginx) -> web -> db` 구조가 화면에 표시되도록 했다.
- 서비스 상세 요청 경합 중 이전 요청이 늦게 끝나면 로딩 표시가 남을 수 있는 문제를 보완했다.
- 중간 폭 화면에서 플로우 카드가 오른쪽으로 넘치지 않도록 각 카드가 줄어들 수 있게 조정했다.

## 변경 파일

- `src/model/struct/services_flow.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `tests/api/test_services_preflight.py`
- `devlog.md`

## 검증

- `python -m compileall project/main/src/model/struct/services_flow.py project/main/src/app/page.services/api.py` 통과.
- `python -m unittest project/main/tests/api/test_services_preflight.py` 통과.
- WIZ 프로젝트 빌드 성공.
- `wiz.docker-infra.service` 재시작 후 active 확인.
- Playwright로 실제 `/services` 화면에 로그인해 Wiki.js 서비스를 열고 `구성`, `로그`, `백업`, `고급` 탭 전환을 확인했다.
- Playwright에서 Wiki.js 상세의 `접속 흐름`, `Docker Infra 연결`, 내부 연결 표시가 렌더링되는 것을 확인했다.
- 1440px 화면 기준 문서 전체 가로 스크롤이 발생하지 않는 것을 확인했다.
