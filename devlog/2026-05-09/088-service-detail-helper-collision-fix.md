# 088. 서비스 상세 API helper 이름 충돌 수정과 화면 렌더링 복구

## 사용자 요청

서비스 상세 화면이 열리질 않아 확인해줘

## 원인

- `/wiz/api/page.services/detail_service`가 nginx 설정 정보를 읽는 중 `self._managed_nginx_path(config_path)`를 호출했다.
- `ServiceManager`의 mixin 상속 순서에서 `ServiceDeleteMixin`이 `ServiceRuntimeMixin`보다 앞에 있어 삭제용 `_managed_nginx_path(raw_path, base_path)`가 먼저 해석됐다.
- 그 결과 상세 화면용 호출 인자 1개와 삭제용 helper 인자 2개가 충돌해 `TypeError`가 발생했고, 상세 API가 500으로 응답했다.

## 변경 사항

- 삭제 전용 nginx path helper 이름을 `_managed_nginx_delete_path`로 변경해 상세/수정용 helper와 충돌하지 않게 했다.
- 서비스 삭제 정적 테스트에 변경된 helper 계약을 반영했다.
- WIZ 빌드 후 실행 중인 `wiz.docker-infra` 서비스가 Python model cache를 새로 읽도록 재시작했다.

## 변경 파일

- `src/model/struct/services_delete.py`
- `tests/api/test_services_preflight.py`

## 검증

- `/var/log/wiz/docker-infra`에서 상세 API 500 원인을 확인했다.
- `python -m compileall -q src/model/struct/services_delete.py src/model/struct/services_runtime.py` 통과.
- `python -m unittest tests.api.test_services_preflight` 통과: 9 tests OK.
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `systemctl restart wiz.docker-infra.service` 후 서비스가 `active` 상태이고 `3001` 포트가 열려 있음을 확인했다.
- Playwright Chromium으로 로그인 후 `/services`에서 첫 번째 서비스를 클릭해 `[data-testid="service-detail"]` 렌더링을 확인했다.
- 같은 브라우저 검증 중 `page.services/load`, `page.services/detail_service`가 모두 HTTP 200으로 응답했다.
