# 086. 서비스 삭제 기능 추가와 oo.tmpi.kr 배포 실패 원인 수정

## 사용자 요청

일단 서비스를 삭제하는 기능이 없어. 그리고 oo.tmpi.kr로 서비스를 배포해봤는데 에러가 떴어. 로그를 확인하고 문제를 해결해줘.

## 변경 사항

- 서비스 상세 화면에 서비스 삭제 버튼을 추가하고, `delete_service` API와 `ServiceDeleteMixin`을 연결했다.
- `service.stack.remove` 로컬 명령과 allowlist를 추가해 Docker stack 제거, nginx 설정 제거, 서비스 생성 파일 제거, 서비스 DB row 삭제가 한 흐름으로 처리되게 했다.
- `/var/log/wiz/docker-infra`의 배포 실패 원인을 확인해 Swarm task의 짧은 node ID와 inspect의 긴 node ID 매칭 누락을 수정했다.
- nginx upstream host는 노드 이름보다 Swarm inspect의 `Status.Addr`를 우선 사용하도록 바꿨다.
- DB/웹이 함께 있는 서비스는 자동으로 마스터 노드에 placement constraint를 적용해 같은 노드에서 실행되게 했다.
- Odoo/Nextcloud/Wiki.js PostgreSQL 템플릿의 DB 이미지를 `postgres:16`으로 고정하고, 내부 DB/Redis 참조를 스택별 서비스 이름으로 렌더링하도록 바꿨다.
- 현재 `oo.tmpi.kr` 서비스 compose를 `postgres:16`, `HOST=odoo_8b3acf_db`, 마스터 노드 placement로 보정하고 재배포했다.
- 현재 `oo.tmpi.kr` nginx upstream과 DB metadata를 실행 노드 IP 기준으로 동기화했다.

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/services.py`
- `src/model/struct/services_delete.py`
- `src/model/struct/services_deploy.py`
- `src/model/struct/services_deploy_targets.py`
- `src/model/struct/services_wizard.py`
- `src/model/struct/templates_seed_shared.py`
- `src/model/struct/templates_seed_web_stacks.py`
- `src/model/struct/templates_seed_business_stacks.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `tests/api/test_services_preflight.py`
- `.runtime/dev/templates/services/odoo_8b3acf/docker-compose.yaml`
- `/etc/nginx/sites-available/docker-infra-oo.tmpi.kr.conf`

## 검증

- `python -m compileall`로 변경 Python 파일 문법 검사를 통과했다.
- `python -m unittest tests.api.test_services_preflight` 통과: 9 tests OK.
- `wiz_project_build` 통과.
- `nginx -t` 통과.
- `docker stack ps odoo_8b3acf`에서 `odoo_8b3acf_db`, `odoo_8b3acf_web`이 `mini1`에서 Running 상태임을 확인했다.
- `curl -k -I --resolve oo.tmpi.kr:443:127.0.0.1 https://oo.tmpi.kr/ --max-time 10` 결과 HTTP/2 303 응답을 확인했다.
