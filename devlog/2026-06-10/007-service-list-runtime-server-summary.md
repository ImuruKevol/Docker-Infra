# 서비스 목록 실행 서버 정보 표시

- 날짜: 2026-06-10
- ID: 007
- 리뷰 ID: cosqunlsyfejjbsfpanuxkflknqpkptl

## 사용자 요청

서비스 관리 목록 화면에 각 서비스가 어떤 서버에 띄워져있는지 정보도 표시해줘.

## 변경 파일

- `src/model/struct/infra_catalog_registry.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.dashboard/view.pug`
- `src/app/page.dashboard/view.ts`
- `devlog.md`
- `devlog/2026-06-10/007-service-list-runtime-server-summary.md`

## 변경 내용

- 서비스 목록/대시보드 서비스 카드 API 응답에 `runtime_servers`, `runtime_server_names`, `runtime_server_summary`를 추가했다.
- 실행 중인 컨테이너와 Swarm task의 등록 서버를 우선 표시하고, 정보가 없으면 서비스 배치 정책의 대상 서버로 보완하도록 했다.
- 서비스 관리 목록 테이블에 `실행 서버` 컬럼을 추가하고, 대시보드 서비스 목록에도 서버 배지를 표시했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/infra_catalog_registry.py` 통과.
- `wiz_project_build(projectName=main, clean=false)` 통과.
- Playwright로 `https://infra-dev.nanoha.kr/dashboard`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 설정해 접근했으나 인증 화면(`/access`)으로 리다이렉트되어 실제 목록 DOM은 확인하지 못했다.
