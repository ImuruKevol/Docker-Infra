# DDNS/일반 도메인과 노드 토폴로지별 nginx 자동 생성 보강

- **ID**: 294
- **날짜**: 2026-05-21
- **유형**: 기능 개선

## 작업 요약

nginx 자동 생성 시 도메인의 DNS 제공 방식과 서비스가 배치된 노드 토폴로지를 구분하도록 보강했다.
DDNS 도메인은 DDNS 관리 모드로, 일반 도메인은 관리형 DNS 모드로 profile을 남기며, 로컬 마스터 노드의 서비스는 loopback upstream을 사용하고 원격/일반 노드는 private host 또는 swarm 주소를 우선 사용하도록 했다.

## 원문 요청사항

```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

ddns 도메인을 적용할 때와 일반 도메인을 사용할 때 nginx 설정이 달라야 해. 그리고 서버가 공인 IP가 적용된 마스터 노드일 때와 일반 노드일 때 설정도 다를 것 같고.
모든 경우를 생각해서 nginx 설정 자동 생성 부분을 보완해줘.

## 리뷰 요약

- 리뷰 ID: mlmvfhzjkgkstxxnmwfewflidojpggod
- 제목: 서비스 상세 기능 개선
- 요청 링크: https://infra-dev.nanoha.kr/services
- 프로젝트 루트: /root/docker-infra
```

## 변경 파일 목록

- `src/model/struct/service_nginx.py`
  - 서비스 도메인 row를 DNS provider, DNS mode, proxy topology, proxy upstream profile로 정규화하는 helper를 추가했다.
  - nginx 렌더링 header에 DDNS/일반 도메인, DDNS endpoint, proxy topology, upstream 정보를 기록하도록 했다.
  - 로컬 마스터는 `127.0.0.1`, 원격 노드는 등록된 private host 또는 swarm addr을 우선 upstream으로 사용하도록 했다.
  - DDNS 등록 중 보강된 endpoint metadata가 nginx mark 단계에서 빈 값으로 덮이지 않도록 했다.
- `src/model/struct/services_deploy_targets.py`
  - Swarm task가 실행 중인 노드를 등록 노드 metadata와 매칭해 local-master, remote-node, swarm-node profile을 저장하도록 했다.
  - 로컬 마스터는 loopback upstream, 원격 노드는 private host upstream으로 metadata를 기록하도록 했다.
  - public IP, private host, swarm addr, host source를 함께 기록해 nginx 생성기가 상황별로 재해석할 수 있게 했다.
- `tests/api/test_services_preflight.py`
  - DDNS/일반 도메인 profile과 노드 토폴로지별 nginx 생성 계약을 정적 테스트에 추가했다.
- `devlog.md`
- `devlog/2026-05-21/294-nginx-domain-node-topology.md`

## 검증 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/service_nginx.py src/model/struct/services_deploy_targets.py` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest` 성공
- `wiz_project_build(projectName="main", clean=false)` 성공
- `git diff --check` 성공
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `https://infra-dev.nanoha.kr/services` HEAD 요청 200 확인
- 같은 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.services/load` POST 요청 시 HTTP 200, WIZ 응답 `401 AUTHENTICATION_REQUIRED` 확인

## 남은 리스크

- 로그인 세션이 없어 실제 인증 후 서비스 상세 화면에서 생성된 nginx 원문을 브라우저로 직접 확인하지 못했다.
- 운영 Docker stack/nginx reload를 직접 실행하지 않았으므로 실제 배치 노드별 upstream 연결은 다음 배포 실행 시 runtime 로그로 확인이 필요하다.
