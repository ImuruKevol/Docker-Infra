# DDNS 도메인 관리 표 컬럼과 서비스 연결 정보 개선

- 날짜: 2026-06-08
- 작업 ID: 013
- 리뷰 ID: wmidmxmacideroaomknwjpmugxraddqf
- 프로젝트: main

## 사용자 요청

- DDNS 관리 서버 표에서 한 컬럼에 여러 정보가 모여 있으므로 컬럼을 나눠 1920 width에 최적화.
- DDNS 레코드 목록에서 hostname이 어떤 서비스에 연결되어 있는지가 먼저 보이도록 컬럼 순서를 수정.
- 연결된 서비스에서 서비스 상세 화면으로 이동할 수 있는 링크 버튼 추가.
- 대상 컬럼은 공인 IP/포트 대신 Docker Infra의 어떤 서버와 포트에 연결되는지 표시.

## 변경 파일

- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `src/model/struct/domains_ddns.py`
- `tests/api/test_domain_management_ui.py`
- `devlog.md`
- `devlog/2026-06-08/013-ddns-domain-table-service-link.md`

## 작업 내용

- DDNS 관리 서버 표를 서버명, 상태, wildcard suffix, API, dispatcher 요청/IP/Host, 등록 수, 작업 컬럼으로 분리.
- DDNS 레코드 목록을 Hostname, 연결 서비스, 연결 대상, DDNS 서버, 상태, 마지막 갱신 순서로 재배치.
- 연결 서비스 컬럼에 `/services/{service_id}` 상세 화면으로 이동하는 링크 버튼 추가.
- DDNS 등록 조회에 `service_domains.metadata`와 포트 정보를 포함해 Docker Infra 배포 노드/프록시 호스트/서비스 포트 표시가 가능하도록 확장.
- 정적 계약 테스트를 새 컬럼 구조와 서비스 상세 링크 기준으로 갱신.

## 검증 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/domains_ddns.py src/app/page.domains/api.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui` 통과.
- `git diff --check -- src/app/page.domains/view.pug src/app/page.domains/view.ts src/model/struct/domains_ddns.py tests/api/test_domain_management_ui.py` 통과.
- `wiz_project_build(projectName="main", clean=false)` 통과.
- 쿠키 `season-wiz-project=main; season-wiz-devmode=true`로 `https://infra-dev.nanoha.kr/domains` 200 응답 확인.
- 같은 쿠키로 `/wiz/api/page.domains/load` POST는 엔드포인트 도달 후 로그인 세션 부재로 `AUTHENTICATION_REQUIRED` 응답 확인.

## 남은 리스크

- 실제 운영 데이터의 `service_domains.metadata`에 배포 노드 정보가 없는 과거 레코드는 연결 대상이 포트 중심 폴백으로 표시될 수 있다.
- 원격 API는 로그인 세션 없이 호출해 인증 이후 실제 데이터 렌더링은 확인하지 못했다.
