# 239. DDNS API 실패 응답 판정과 POST redirect 처리 수정

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> DDNS API를 호출했다고는 뜨는데 DDNS 서비스에서 확인해보니 로그도 안찍혀있고 클라우드플레어 DNS에도 등록이 되어있지 않아. 여기 문제인지 DDNS 서비스 문제인지 확인해줘

## 확인 결과

- Docker Infra DB의 `wiki.sub.nanoha.kr` DDNS registration metadata에 `{"code": 405, "data": {"message": "POST method is required."}}` 응답이 저장되어 있는데도 로컬 상태가 `registered`로 표시되는 것을 확인했다.
- 이후 `domain.ddns.register_service` operation은 같은 IP라며 `public_ip_unchanged`로 실제 API 호출을 건너뛰고 있었다.
- 등록된 API URL `http://ddns.nanoha.kr/api/ddns/update`는 308 redirect를 반환했고, HTTPS URL로 직접 POST하면 DDNS 서비스가 `code: 200`, `action: updated`, Cloudflare record id를 반환했다.
- 결론적으로 DDNS 서비스 자체는 정상이고, Docker Infra가 POST redirect와 실패 payload를 잘못 처리한 것이 원인이었다.

## 변경 요약

- DDNS API 응답 payload의 `success`, `ok`, `status`, `code/status_code`, nested `data/response/body`를 검사해 실패 응답을 성공으로 저장하지 않도록 했다.
- HTTP 200이어도 `code: 405` 같은 API 레벨 오류나 HTML redirect/error body는 실패로 처리한다.
- 기존 registration metadata에 실패 응답이 남아 있으면 `public_ip_unchanged` skip을 하지 않고 실제 DDNS API를 다시 호출하게 했다.
- 수동 DDNS API 호출 실패 시 `ddns_registrations`와 `service_domains.metadata.ddns_status`가 `failed`로 갱신되게 했다.
- `http -> https` 308 redirect에서도 POST method/body/header가 유지되도록 DDNS 서버 호출부와 NetworkManager dispatcher agent에 redirect handler를 추가했다.
- AI 수정 결과 문구는 실제 API 호출/생략 여부에 맞춰 표시되도록 수정했다.

## 변경 파일

- `src/model/struct/domains_ddns.py`
- `src/model/struct/ai_assistant.py`
- `src/model/struct/local_command_scripts.py`
- `tests/api/test_domain_management_ui.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-18/239-ddns-api-response-validation.md`

## 확인한 내용

- 현재 DB 상태에서 과거 DDNS 응답이 `code: 405`였는데도 `registered`로 저장된 것을 확인했다.
- `curl`로 HTTP endpoint 호출 시 308 redirect를 확인했다.
- HTTPS endpoint 직접 POST로 DDNS 서비스가 `code: 200`, `action: created/updated`를 반환하고 Cloudflare record id를 내려주는 것을 확인했다.
- 수정된 `_request()` 경로로 HTTP endpoint를 호출했을 때 308 이후 HTTPS로 POST가 유지되고 `code: 200`, `action: updated`가 반환되는 것을 확인했다.
- `_response_failure()` 직접 검사로 `code: 405`, nested `response.code: 405`, non-JSON body를 실패로 판정하는 것을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/domains_ddns.py src/model/struct/ai_assistant.py src/model/struct/local_command_scripts.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_services_preflight`: 18개 테스트 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `git diff --check`: 통과

## 남은 리스크

- 이미 설치된 `/usr/local/bin/docker-infra-ddns-update` dispatcher script는 재등록 전까지 이전 코드일 수 있다.
- 현재 DB의 과거 registration metadata에는 이전 `code: 405` 응답이 남아 있으며, 다음 등록/수동 호출 시 새 로직으로 갱신된다.
