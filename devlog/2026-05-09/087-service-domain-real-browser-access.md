# 087. oo.tmpi.kr 실제 브라우저 접속을 위한 DNS 자동 등록과 인증서 적용 보강

## 사용자 요청

로컬 resolve 테스트가 아니라 실제 브라우저에서 들어갈 수 있어야 해. 안들어가지는데 확인해줘.

## 원인

- `oo.tmpi.kr` 서비스는 nginx와 컨테이너 upstream은 정상 동작했지만, Cloudflare DNS에 실제 A 레코드가 없어 공용 DNS에서 도메인이 해석되지 않았다.
- DNS 레코드를 추가한 뒤에도 nginx가 OpenSSL 테스트용 자체 서명 인증서를 계속 사용하고 있어 브라우저가 신뢰할 수 없는 인증서로 차단했다.
- 서버에 `certbot`과 nginx 플러그인이 설치되어 있지 않아 기존 자동 인증서 발급 경로가 실제 운영 인증서로 이어질 수 없었다.

## 변경 사항

- 서비스 도메인 배포 시 Cloudflare zone 설정을 찾아 `A` 또는 `AAAA` 레코드를 자동 생성/갱신하는 `ensure_service_dns_record`를 추가했다.
- nginx 적용 흐름에서 certbot 발급 전에 서비스 도메인의 DNS 레코드를 먼저 보정하도록 연결했다.
- OpenSSL 자체 서명 테스트 인증서는 테스트 모드가 켜진 경우에만 유효 인증서 후보로 사용하도록 제한했다.
- `oo.tmpi.kr` Cloudflare A 레코드를 실제 공개 주소로 생성하고 DNS 캐시를 동기화했다.
- Ubuntu 서버에 `certbot`, `python3-certbot-nginx`를 설치하고 `oo.tmpi.kr` Let's Encrypt 인증서를 발급했다.
- `/etc/nginx/sites-available/docker-infra-oo.tmpi.kr.conf`가 Let's Encrypt 인증서 경로를 사용하도록 반영하고 nginx를 reload했다.
- 서비스 도메인 DB metadata의 nginx SSL 상태를 `certbot`으로 동기화했다.
- 서비스 preflight 정적 테스트에 DNS 자동 등록 계약 검증을 추가했다.

## 변경 파일

- `src/model/struct/domains.py`
- `src/model/struct/service_nginx.py`
- `src/model/struct/service_nginx_certificates.py`
- `tests/api/test_services_preflight.py`
- `/etc/nginx/sites-available/docker-infra-oo.tmpi.kr.conf`

## 검증

- `dig +short oo.tmpi.kr A @1.1.1.1` 결과 `---.---.---.---` 응답을 확인했다.
- `certbot certonly --nginx -d oo.tmpi.kr`로 Let's Encrypt 인증서 발급을 완료했다.
- `nginx -t` 통과 후 nginx reload를 완료했다.
- `curl -I https://oo.tmpi.kr/ --max-time 12`에서 인증서 검증 포함 HTTP/2 303 응답을 확인했다.
- `curl -L https://oo.tmpi.kr/ --max-time 20`에서 최종 HTTP 200 응답을 확인했다.
- Playwright Chromium으로 `https://oo.tmpi.kr/`에 접속해 최종 URL `https://oo.tmpi.kr/web/database/selector`, title `Odoo`, status `200`을 확인했다.
- `python -m compileall -q src/model/struct/domains.py src/model/struct/service_nginx.py src/model/struct/service_nginx_certificates.py` 통과.
- `python -m unittest tests.api.test_services_preflight` 통과: 9 tests OK.
- `wiz_project_build(projectName="main", clean=false)` 통과.
