# 083. P7 nginx 고급 원문 편집과 도메인 인증서 검증·적용 서비스 표시 완료

- 날짜: 2026-05-09
- 요청: "P7에서 남은 작업들을 진행해줘"

## 변경 요약

- 서비스 상세의 고급 정보 영역에 Docker Infra가 관리하는 nginx 설정 원문을 표시하고, 고급 모드에서만 수정할 수 있도록 연결했다.
- nginx 원문 저장 시 `nginx -t`와 reload를 실행하고 실패하면 이전 설정으로 되돌리도록 했다.
- 도메인 인증서 업로드에서 선택형 chain/CA bundle 파일을 지원하고, 선택 시 `fullchain.pem`으로 합쳐 nginx가 사용하도록 했다.
- private key 파일 권한을 `0600`으로 저장하고, 기존 인증서 분석에서도 key 권한과 cert-key 매칭 여부를 검증하도록 했다.
- 도메인 관리 화면에서 인증서 상태에 key 권한/매칭 결과를 표시하고, 해당 도메인 또는 하위 도메인에 인증서가 적용된 서비스를 보여주도록 했다.
- P7 남은 TODO를 완료 처리했다.

## 변경 파일

- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.domains/view.ts`
- `src/app/page.domains/view.pug`
- `src/model/struct/services_runtime.py`
- `src/model/struct/domains.py`
- `src/model/struct/webserver.py`
- `src/model/struct/service_nginx_certificates.py`
- `src/route/api-domain-certificates/controller.py`
- `tests/api/test_services_preflight.py`
- `docs/docker-infra-remaining-todo.md`
- `docs/docker-infra-development-todo.md`

## 검증

- `python -m py_compile src/model/struct/webserver.py src/model/struct/domains.py src/model/struct/service_nginx_certificates.py src/model/struct/services_runtime.py src/app/page.services/api.py src/route/api-domain-certificates/controller.py tests/api/test_services_preflight.py`
- `python -m unittest tests.api.test_services_preflight`
- `python -m unittest tests.api.test_images_templates_catalog`
- `wiz_project_build(projectName="main", clean=false)`

모두 통과했다.
