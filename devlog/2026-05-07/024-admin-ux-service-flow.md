# 024. 관리자용 UX TODO 반영과 서버/서비스 화면 흐름 개선

## 요청

> 검토 결과 및 내 목적에 따라 분석된 결과를 TODO에 반영하고 보완해줘. 실제 서비스 화면들도 순서대로 작업해줘

## 작업 요약

- `docs/docker-infra-development-todo.md`에 전산 담당자/관리자 기준 UI/UX 원칙과 review finding 보완 조건을 추가했다.
- Cloudflare/Harbor 연동이 꺼져도 도메인/이미지 메뉴를 유지하도록 sidebar 메뉴 정책을 수정했다.
- 설치 화면과 시스템 설정에서 기술 입력값을 기본 화면에서 줄이고 고급 설정으로 이동했다.
- 운영 도구 화면을 raw command runner에서 목적형 진단 버튼 중심으로 재구성했다.
- 서버 화면에 IP/host 중심 등록, 자동 점검, Swarm 연결 버튼, 최근 join job 결과 표시를 추가했다.
- 서비스 화면에 기본 웹 서비스 생성 wizard를 추가하고, 서비스 초안 저장 시 DB row, service domain, Compose file, `.history` snapshot을 생성하는 `struct/services.py`를 추가했다.
- 도메인/이미지 화면에 연동 disabled 상태에서도 수동 관리/로컬 목록 기능이 유지된다는 안내를 추가했다.
- 주요 화면의 `Refresh`, `Loading`, `Enabled`, `Off` 등 개발자용 영문 라벨을 한국어 운영 라벨로 정리했다.

## 변경 파일

- `docs/docker-infra-development-todo.md`
- `src/model/struct.py`
- `src/model/struct/services.py`
- `src/app/component.nav.sidebar/view.ts`
- `src/app/page.access/view.pug`
- `src/app/page.access/view.ts`
- `src/app/page.dashboard/view.pug`
- `src/app/page.domains/view.pug`
- `src/app/page.images/view.pug`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/app/page.templates/view.pug`
- `src/app/page.tools/view.pug`
- `src/app/page.tools/view.ts`

## 검증

- Python source compile 확인 완료.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/api /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract` 통과.
- `git -C /root/docker-infra/project/main diff --check` 통과.
- WIZ MCP `wiz_project_build(clean=false)` 통과.
- Playwright Chromium으로 `/dashboard`, `/servers`, `/services`, `/tools`, `/domains`, `/images`, `/system` 렌더링 확인.
- 실행 중인 `wiz.docker-infra` daemon은 프로젝트 지침에 따라 재시작하지 않았다. 따라서 새로 추가된 `page.services/create_service` app API는 현재 실행 중 daemon에 아직 로드되지 않아 runtime create smoke는 보류했다.
