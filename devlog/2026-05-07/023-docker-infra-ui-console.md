# 023. Docker Infra 운영 콘솔 화면 구현

## 요청

> 현재까지 개발된 부분들에 대해 화면을 제대로 구현해줘. 현재 기능은 어느 정도 뭔가 된 흔적이 보이는데 화면은 하나도 구현이 되어있지 않고 디자인도 너무 개발자틱하게 만들어져있는 등 문제가 너무 많아.

## 작업 요약

- Docker Infra 운영자가 첫 화면에서 시스템 상태, 연동 상태, 서버, 서비스, 작업 흐름을 파악할 수 있도록 대시보드 화면을 재구성했다.
- 서버, 서비스, 이미지, 템플릿, 도메인, 시스템, 도구 화면에 DB 기반 데이터 로딩 API와 실제 운영 화면을 구현했다.
- 접근 화면과 사이드바/레이아웃을 운영 콘솔 톤으로 정리하고, 개발용 placeholder 중심 UI를 제거했다.
- 화면 전용 데이터 공급을 `src/model/struct/infra_catalog.py`로 분리해 page API가 직접 DB 쿼리와 화면 가공을 떠안지 않도록 정리했다.
- 서버 관리 화면에 local master ensure, slave 등록, node check, reporter token 발급 액션을 연결했다.
- 도구 화면의 명령 실행은 UI에서 허용한 안전 명령만 실행되도록 제한했다.

## 변경 파일

- `src/model/struct.py`
- `src/model/struct/infra_catalog.py`
- `src/app/component.nav.sidebar/view.pug`
- `src/app/component.nav.sidebar/view.ts`
- `src/app/layout.sidebar/view.pug`
- `src/app/page.access/view.pug`
- `src/app/page.dashboard/api.py`
- `src/app/page.dashboard/view.pug`
- `src/app/page.dashboard/view.ts`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.images/api.py`
- `src/app/page.images/view.pug`
- `src/app/page.images/view.ts`
- `src/app/page.templates/api.py`
- `src/app/page.templates/view.pug`
- `src/app/page.templates/view.ts`
- `src/app/page.domains/api.py`
- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `src/app/page.tools/api.py`
- `src/app/page.tools/view.pug`
- `src/app/page.tools/view.ts`
- `src/app/page.system/api.py`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`

## 검증

- `PYTHONDONTWRITEBYTECODE=1 /opt/conda/envs/docker-infra/bin/python - <<'PY' ...`로 변경 Python 파일 compile 확인 완료.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/api /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract` 통과.
- `git -C /root/docker-infra/project/main diff --check` 통과.
- WIZ MCP `wiz_project_build(clean=false)` 통과.
- `systemctl restart wiz.docker-infra` 후 서비스 active 확인.
- 로그인 세션으로 `page.dashboard`, `page.servers`, `page.services`, `page.images`, `page.templates`, `page.domains`, `page.system`, `page.tools` API smoke 테스트를 수행했고 모두 HTTP 200 / code 200 응답을 확인했다.
- Playwright Chromium으로 desktop 1440x1000에서 `/dashboard`, `/servers`, `/services`, `/images`, `/templates`, `/system`, `/tools` 화면 렌더링을 확인했다.
- Playwright Chromium으로 mobile 390x844에서 `/dashboard`, `/servers`, `/system` 화면 렌더링을 확인했다.
- 화면 확인 스크린샷은 `.runtime/ui-smoke/`, `.runtime/ui-smoke-mobile/` 아래에 생성했다.
