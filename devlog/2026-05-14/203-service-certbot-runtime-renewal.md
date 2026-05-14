# 203. 서비스 certbot SSL 적용 타이밍과 갱신 관리 보강

## 원 요청

- 리뷰 ID: `sxjwtolmctsuzvdjcsopsoucgtccigwd`
- 제목: 서비스 생성 시 SSL 인증 타이밍 관련
- 요청: AI 또는 수동 입력으로 서비스를 생성할 때 certbot 무료 인증서는 서비스 컨테이너가 실제로 뜬 뒤 호출되도록 문제를 분석하고 수정한다. 무료 인증서 사용 서비스에는 유효 기간 등 인증서 정보, 수동 갱신 기능, 자동 갱신 주기/상태 표시 및 자동 갱신 기능이 필요하면 추가한다.

## 변경 내용

- 서비스 배포 흐름에서 `docker stack deploy` 직후 nginx/certbot을 바로 실행하지 않고, Docker 작업과 컨테이너 실행/health 상태를 대기한 뒤 nginx와 SSL을 적용하도록 변경했다.
- nginx upstream 대상 동기화도 `preparing/starting` 작업이 아니라 실제 `running` 작업만 사용하도록 조정했다.
- certbot 인증서 조회, 만료일/남은 일수, 자동 갱신 상태, 수동 갱신, 자동 갱신 설정 보장을 위한 서비스 레벨 구조체를 추가했다.
- certbot 자동 갱신은 기존 systemd timer/cron을 감지하고, 없으면 `docker-infra-certbot-renew.timer` 또는 cron fallback을 설정할 수 있게 했다.
- 서비스 상세 구성 탭에 무료 SSL 인증서 섹션을 추가해 certbot 인증서 상태, 만료 정보, 자동 갱신 상태, 자동 설정/수동 갱신 버튼을 노출했다.
- certbot 공식 문서 기준으로 자동 갱신은 `certbot renew`를 systemd timer 또는 cron으로 주기 실행하는 방식이며, 갱신 대상일 때만 실제 갱신을 시도하는 흐름으로 반영했다.

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/service_nginx_certificates.py`
- `src/model/struct/service_nginx.py` (기존 흐름 연동 유지)
- `src/model/struct/services_deploy.py`
- `src/model/struct/services_deploy_targets.py`
- `src/model/struct/services_certbot.py`
- `src/model/struct/services.py`
- `src/model/struct/services_runtime.py`
- `src/model/struct.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-14/203-service-certbot-runtime-renewal.md`

## 검증

- `python -m py_compile project/main/src/model/struct/local_command_catalog.py project/main/src/model/struct/service_nginx_certificates.py project/main/src/model/struct/services_deploy.py project/main/src/model/struct/services_deploy_targets.py project/main/src/model/struct/services_certbot.py project/main/src/model/struct/services_runtime.py project/main/src/model/struct/services.py project/main/src/app/page.services/api.py` 통과.
- `python -m unittest project/main/tests/api/test_services_preflight.py` 통과.
- `wiz_project_build(projectName="main", clean=false)` 통과.
- 참고: `python -m unittest project/main/tests/api/test_wiz_structure_contract.py`는 기존 대형 model 파일 다수와 기존 `src/app/page.servers/api.py:595` 응답 위치 규칙 위반으로 실패했다. 이번 변경으로 새로 추가된 실패는 아니다.

## 남은 리스크

- 실제 Let’s Encrypt 발급/갱신은 운영 서버의 DNS 전파, 80/443 접근성, certbot 설치 방식, systemd/cron 권한에 의존하므로 운영 환경에서 한 번의 실발급 검증이 필요하다.
- 자동 갱신 설정은 기존 certbot timer/cron이 감지되면 존중하며, 없는 경우에만 Docker Infra 전용 timer/cron을 추가한다.
