# 296. 템플릿 생성 도메인/DDNS/nginx 플로우 점검과 DDNS 매칭 실패 보강

- 날짜: 2026-05-21
- 요청: 템플릿으로 서비스 생성 시 nginx 설정, ddns/domain 설정 등 모든 플로우에 대해 로직상 오류가 없는지 확인해줘.

## 변경 요약

- 템플릿 초안 생성부터 서비스 생성, 도메인 저장, 배포 후 nginx/DDNS 적용까지의 호출 흐름을 점검했다.
- DDNS 도메인으로 선택된 서비스가 처리 가능한 DDNS 관리 서버와 매칭되지 않아도 `skipped`로 끝날 수 있던 경로를 배포 차단 오류로 변경했다.
- 서비스 생성 사전 점검에서도 DDNS 요청 도메인에 대응하는 DDNS 관리 서버가 없으면 `domain.ddns.endpoint` 오류를 반환하도록 보강했다.
- 정적 계약 테스트에 DDNS 엔드포인트 누락 차단 계약을 추가했다.

## 변경 파일

- `src/model/struct/domains_ddns.py`
- `src/model/struct/services_preflight.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-21/296-template-domain-nginx-flow-check.md`

## 확인한 플로우

- 템플릿 선택: `page.services.create`에서 `prepare_template_draft` 호출 후 템플릿 compose와 public endpoint 메타데이터로 컴포넌트 목록 생성.
- 생성 payload: 선택한 도메인/zone/DDNS endpoint, prefix, 연결 대상 서비스/포트를 `ServicesWizard.create`로 전달.
- 도메인 정규화: `ServicesWizard._domain_entries`가 DDNS zone이면 하위 도메인과 DDNS metadata를 채우고, 일반 domain zone이면 `zone_id` 기반 metadata를 유지.
- 배포: `services_deploy.deploy`가 compose 공개 포트를 동기화하고 실행 노드 정보를 `service_domains.metadata`에 반영한 뒤 `service_nginx.apply` 호출.
- nginx 생성: `service_nginx`가 DDNS/managed DNS, local-master/remote-node/swarm-node 토폴로지에 맞춰 upstream과 헤더를 생성.
- DNS 적용: 일반 도메인은 managed DNS record를 보장하고, DDNS 도메인은 DDNS 관리 서버 등록을 수행.

## 검증 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/domains_ddns.py src/model/struct/services_preflight.py src/model/struct/service_nginx.py src/model/struct/services_wizard.py src/model/struct/services.py src/model/struct/services_deploy.py src/model/struct/services_deploy_targets.py src/model/struct/services_runtime.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest` 통과.
- `git diff --check` 통과.
- WIZ build 통과.
- devmode 쿠키(`season-wiz-project=main`, `season-wiz-devmode=true`)로 `/services`, `/wiz/api/page.services.create/load`, `/wiz/api/page.services.create/domain_options` HTTP 200 확인.

## 남은 리스크

- 실제 템플릿 서비스 생성/배포는 서버 상태를 변경하므로 수행하지 않았다.
- DDNS 외부 관리 서버의 실등록 성공 여부는 각 endpoint URL/token 및 네트워크 상태에 의존한다.
