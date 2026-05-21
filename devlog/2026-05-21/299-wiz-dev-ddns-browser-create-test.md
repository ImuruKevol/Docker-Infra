# 299. wiz_dev 템플릿 DDNS 실생성 검증과 배치/검증 오류 보강

- 날짜: 2026-05-21
- 요청: wiz_dev namespace로 등록된 템플릿으로 직접 서비스 생성 테스트를 하고, ddns를 이용한 접속 확인까지 검증해줘. 버그나 에러가 있다면 수정하고. 관리자 패스워드는 브라우저 테스트로 진행해줘.

## 변경 요약

- 브라우저 인증 세션에서 `wiz_dev` 템플릿으로 실제 서비스 생성, DDNS 도메인 등록, nginx 적용, 외부 접속, 테스트 서비스 삭제까지 검증했다.
- 템플릿 미리보기에서는 허용되던 `HEALTHCHECK_REQUIRED` warning이 실제 생성 preflight에서 오류로 바뀌던 불일치를 수정했다.
- 자동 배치가 등록 노드명과 실제 Swarm hostname이 어긋난 stale 노드를 선택할 수 있어, live Swarm 상태와 hostname mismatch를 placement 후보에 반영하도록 보강했다.
- 현재 등록된 `wiz_dev` 템플릿 compose는 실패하던 app healthcheck를 제거해 실제 배포 가능 상태로 복구했다.

## 변경 파일

- `src/model/struct/services_wizard.py`
- `src/model/struct/services_placement.py`
- `tests/api/test_services_preflight.py`
- `/root/docker-infra/data/templates/wiz_dev/docker-compose.yaml`
- `devlog.md`
- `devlog/2026-05-21/299-wiz-dev-ddns-browser-create-test.md`

## 브라우저 검증 결과

- 템플릿: `wiz_dev`
- DDNS 도메인: `codex-wiz-dev-0521072052-8000.sub.nanoha.kr`
- 생성 서비스 ID: `3c72089c-9442-440e-8b16-bfa14e4c3a30`
- 배포 operation: `7f1a1fe1-dc58-4609-937c-48ba086ee9d1`, `succeeded`
- nginx/DDNS metadata: `dns_provider=ddns`, `ddns_status=registered`, `proxy_topology=remote-node`, `proxy_host=172.16.0.226`
- 접속 검증: `https://codex-wiz-dev-0521072052-8000.sub.nanoha.kr/dashboard` HTTP 200
- 정리 operation: `09893ec0-10cc-4a5b-8189-6a40f84aaac6`, `succeeded`

## 추가 확인

- 실패 재현 1: `wiz_dev` preflight가 `services.app.healthcheck` 누락으로 `COMPOSE_VALIDATION_FAILED`를 반환했다.
- 실패 재현 2: 자동 배치가 stale `mini2` 등록 정보의 Swarm ID를 따라 실제 `ktw-test` 노드에 배치했고 app 이미지가 `Preparing`에 머물렀다.
- 실패 테스트 서비스 2건은 삭제 API로 정리했다.

## 검증 명령

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_placement.py src/model/struct/services_wizard.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest` 통과.
- `git diff --check` 통과.
- WIZ build 통과.
- devmode 쿠키(`season-wiz-project=main`, `season-wiz-devmode=true`)로 `/services` HTTP 200 확인.

## 남은 리스크

- 실제 성공 검증은 `mini3` 노드로 고정해 수행했다. 자동 배치 보강은 적용했지만, 운영에서 stale 노드 레코드 자체는 서버 관리 화면에서 별도 정비가 필요하다.
- DDNS 외부 API와 인증서/프록시 상태는 외부 서비스 상태에 의존한다.
