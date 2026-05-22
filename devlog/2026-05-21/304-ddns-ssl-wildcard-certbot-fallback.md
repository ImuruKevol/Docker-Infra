# DDNS SSL 와일드카드 매칭과 certbot fallback 보강

## 사용자 요청

- 리뷰 ID: `ulnqudqvuxeshwyimxlbfatnvvhkzefh`
- 요청: notion 서비스의 DDNS 도메인과 유료 와일드카드 SSL 인증서 조합에서 `notion.sub.nanoha.kr` 같은 두 단계 서브도메인에 인증서가 제대로 적용되지 않는 문제를 nginx/DDNS 설정 기준으로 확인하고, certbot 필요 여부를 포함해 서비스 배포 시 DDNS 적용 로직에 반영.

## 변경 파일

- `src/model/struct/webserver.py`
  - 와일드카드 인증서 매칭을 실제 TLS 규칙에 맞게 하위 라벨 1개만 허용하도록 수정.
  - 런타임 인증서 조회가 `zone_id` 일치만으로 인증서를 적용하지 않고 실제 인증서 도메인/SAN 매칭을 요구하도록 수정.
- `src/model/struct/service_nginx.py`
  - DDNS 도메인이 기존 인증서 모드로 저장되어 있어도 실제 매칭 인증서가 없으면 배포 단계에서 certbot exact 인증서 발급 대상으로 처리하도록 fallback 추가.
- `src/app/page.services/api.py`
  - 서비스 화면 도메인 옵션의 와일드카드 매칭 규칙을 동일하게 보정.
- `src/app/page.services.create/api.py`
  - 서비스 생성 화면 도메인 옵션의 와일드카드 매칭 규칙을 동일하게 보정.
- `tests/api/test_certificate_wildcard_match.py`
  - `*.nanoha.kr`이 `notion.sub.nanoha.kr`에 매칭되지 않고, `*.sub.nanoha.kr` 또는 exact 인증서만 매칭되는 회귀 테스트 추가.
  - DDNS 기존 SSL 모드 fallback 계약 테스트 추가.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_certificate_wildcard_match.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_services_preflight.py tests/api/test_domain_management_ui.py` 통과.
- `wiz_project_build(projectName=main, clean=false)` 성공.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `https://infra-dev.nanoha.kr/dashboard` 요청 결과 HTTP 200 확인.

## 남은 리스크

- 실제 `notion.sub.nanoha.kr` certbot 발급은 DNS/DDNS 전파, 80/443 포트 접근성, certbot 설치 상태에 의존하므로 운영 배포 시점의 operation 로그로 최종 확인이 필요하다.
