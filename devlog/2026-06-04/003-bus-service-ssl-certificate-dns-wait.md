# bus 서비스 SSL 인증서 발급과 DNS 전파 대기 보강

- 날짜: 2026-06-04
- 리뷰 ID: jitgzhzglftjixxnrjncnmkctyuttjzr
- 요청: "bus" 서비스의 SSL 인증서가 정상적으로 발급되지 않았어.

## 변경 파일

- `src/model/struct/service_nginx.py`
- `tests/api/test_certificate_wildcard_match.py`
- `devlog.md`
- `devlog/2026-06-04/003-bus-service-ssl-certificate-dns-wait.md`

## 운영 반영

- `/etc/nginx/sites-available/docker-infra-bus.sub.nanoha.kr.conf`와 sites-enabled symlink를 생성하고 SSL server block을 적용했다.
- `certbot certonly --nginx -d bus.sub.nanoha.kr`로 Let's Encrypt 인증서를 발급했다.
- `service_domains`의 `nginx_ssl_mode`, nginx config path metadata와 `services.status`를 실제 적용 상태에 맞게 갱신했다.

## 작업 내용

- 원인 확인: 기존 배포 작업에서 DDNS 등록 직후 Certbot이 바로 실행되어 Let's Encrypt 검증 시점에는 `bus.sub.nanoha.kr`가 NXDOMAIN으로 조회됐고, 실패 후 nginx 설정이 롤백되어 HTTPS server block도 남지 않았다.
- 서비스 nginx 적용 흐름에 Certbot 실행 전 DNS 전파 대기를 추가했다.
- DDNS/공인 IP 기대값이 있으면 실제 해석된 A/AAAA 주소와 일치할 때까지 재시도하고, 전파되지 않으면 Certbot 실행 전에 명확한 오류를 남기도록 했다.
- self-signed 테스트 모드에서는 외부 DNS 대기를 건너뛰도록 했다.

## 확인 결과

- `certbot certificates -d bus.sub.nanoha.kr`에서 인증서가 `VALID`이며 만료일이 2026-09-02임을 확인했다.
- `openssl s_client -servername bus.sub.nanoha.kr -connect bus.sub.nanoha.kr:443 -brief`에서 peer certificate CN이 `bus.sub.nanoha.kr`이고 검증이 OK임을 확인했다.
- `curl -I http://bus.sub.nanoha.kr`는 HTTPS 301 리다이렉트, `curl -I https://bus.sub.nanoha.kr`는 HTTP 200을 반환했다.
- `nginx -t`와 `nginx -s reload` 성공.
- DB에서 bus 서비스 상태가 `deployed`, 도메인의 `nginx_ssl_mode`가 `certbot`으로 갱신된 것을 확인했다.
- `docker service ls --filter name=bus_f7b72d`에서 app/db 모두 `1/1` 상태를 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/service_nginx.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_certificate_wildcard_match.py` 통과.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `git diff --check` 통과.
- `season-wiz-project=main; season-wiz-devmode=true` 쿠키로 `/services`와 해당 서비스 상세 URL HTTP 200 확인. 상세 WIZ API 직접 호출은 인증 세션 부재로 401 `AUTHENTICATION_REQUIRED`가 반환됐다.
