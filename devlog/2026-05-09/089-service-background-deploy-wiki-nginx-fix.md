# 서비스 배포 백그라운드 전환과 Wiki.js nginx 배포 오류 수정

- 날짜: 2026-05-09
- 작업 번호: 089

## 사용자 요청

저장 후 배포를 눌렀을 때 너무 오래 걸리므로 배포 작업을 백그라운드에서 돌아가도록 변경하고, Wiki 서비스를 배포할 때 nginx 설정 쪽에서 발생하는 오류를 실제 화면 자동화 테스트로 확인해 수정해달라는 요청.

## 원인 및 판단

- 서비스 생성/수정 후 배포가 하나의 요청 안에서 끝까지 동기 실행되어, Docker stack 배포, nginx 설정 검사/재시작, DNS/인증서 처리까지 UI 요청 시간이 길어졌다.
- Wiki.js 배포 실패 로그의 직접 원인은 nginx 문법 자체가 아니라, 도메인/DNS 처리 결과와 operation payload를 기록하는 과정에서 UUID 등 JSON 직렬화가 불가능한 값이 포함되어 발생한 오류였다.
- 도메인 동기화 결과가 operation output에 저장될 때 민감 필드가 포함될 수 있어, 이후 배포 로그에 남지 않도록 응답 payload를 정리하고 기존 로그/메타데이터의 민감값은 마스킹했다.
- 현재 nginx 버전 기준으로 `listen 443 ssl http2` 형식이 경고를 만들고 있어, 생성 설정과 기존 live 설정을 `listen 443 ssl` 형식으로 정리했다.

## 변경 파일

- `src/model/struct/services_deploy.py`
  - 배포 준비, operation 생성, 백그라운드 worker 실행 흐름을 분리했다.
  - 기존 `deploy()`는 operation id를 받아 실행 중인 백그라운드 작업을 갱신할 수 있도록 보강했다.
- `src/app/page.services.create/api.py`
  - 생성 화면에서 사용할 `deploy_service_background` API를 추가했다.
- `src/app/page.services/api.py`
  - 서비스 상세/목록 화면에서 사용할 `deploy_service_background` API를 추가했다.
- `src/app/page.services.create/view.ts`
  - `저장 후 배포` 클릭 시 서비스 저장 후 배포 operation만 백그라운드로 시작하고 상세 화면으로 이동하도록 변경했다.
- `src/app/page.services/view.ts`
  - 서비스 상세의 재배포 동작을 백그라운드 API로 전환했다.
  - 생성 화면에서 전달되는 `service_id` query param을 받아 바로 해당 서비스를 선택할 수 있도록 보강했다.
- `src/model/struct/operations.py`
  - operation 생성/전환/output 저장 시 JSONB payload를 안전하게 직렬화하도록 수정했다.
- `src/model/struct/domains.py`
  - 도메인 자동 레코드 보장 결과에서 민감 필드가 operation 로그에 저장되지 않도록 제거했다.
- `src/model/struct/service_nginx.py`
  - 생성되는 SSL nginx listen 설정을 현재 nginx 경고가 없는 형식으로 조정했다.
- `tests/api/test_services_preflight.py`
  - 백그라운드 배포 API/프론트 호출, deploy worker, operation JSON 직렬화 회귀 검증을 추가했다.
- `/etc/nginx/sites-available/docker-infra-wiki.imurukevol.com.conf`
  - live nginx 설정의 SSL listen 형식을 정리했다.
- `/etc/nginx/sites-available/docker-infra-oo.tmpi.kr.conf`
  - live nginx 설정의 SSL listen 형식을 정리했다.

## 검증

- Python 컴파일 검증을 통과했다.
- `python -m unittest tests.api.test_services_preflight`가 통과했다.
- WIZ 프로젝트 빌드가 성공했다.
- `wiz.docker-infra.service` 재시작 후 active 상태를 확인했다.
- Playwright로 실제 화면에서 Wiki.js 템플릿을 선택해 `저장 후 배포` 흐름을 실행했고, 배포 operation이 백그라운드로 생성된 뒤 최종 `succeeded` 상태가 되는 것을 확인했다.
- 서비스 상세 화면에서 Wiki.js 서비스를 다시 적용했고, 배포 API 응답이 약 1.5초 내 반환된 뒤 백그라운드 operation이 `succeeded` 상태가 되는 것을 확인했다.
- `https://wiki.imurukevol.com/` 접속이 HTTP 200으로 응답하는 것을 확인했다.
- `nginx -t`가 경고 없이 성공하는 것을 확인했다.
- Wiki.js stack의 Docker service들이 정상 replica 상태로 유지되는 것을 확인했다.
- 기존 operation/service metadata에 남아 있던 민감값은 마스킹했고, 신규 배포 operation output에는 민감 필드가 포함되지 않는 것을 확인했다.
