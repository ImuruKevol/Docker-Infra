# 시스템 설정 실적용, Harbor/GitLab 연결 테스트, Cloudflare 도메인 관리 화면과 DNS 캐시 구조 추가

- 날짜: 2026-05-07
- ID: 044

## 사용자 요청

- "시스템 설정 화면을 대대적으로 개선해줘. 일단 고급 설정 기능은 필요 없고 전부 보여야 해."
- "General에 있는 설정들이 실제로는 적용이 되지 않고 있어. Favicon, Logo는 이미지를 업로드하는 것도 지원해야해."
- "Harbor, GitLab의 경우엔 정보 입력 후 연결 테스트 버튼을 추가해줘."
- "CloudFlare 설정같은 경우엔 시스템 설정이 아니라 도메인 관리 화면에서 관리가 되어야 해."

## 변경 파일

- `config/docker_infra.py`
- `docs/docker-infra-design.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-runtime.md`
- `src/app/component.nav.sidebar/view.pug`
- `src/app/component.nav.sidebar/view.ts`
- `src/app/page.access/view.pug`
- `src/app/page.access/view.ts`
- `src/app/page.domains/api.py`
- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `src/app/page.system/api.py`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/model/db/migrations/006_cloudflare_dns_cache.sql`
- `src/model/db/migrations/006_cloudflare_dns_cache.down.sql`
- `src/model/struct.py`
- `src/model/struct/appearance.py`
- `src/model/struct/domains.py`
- `src/model/struct/domains_cloudflare.py`
- `src/model/struct/domains_shared.py`
- `src/model/struct/infra_catalog.py`
- `src/model/struct/integrations.py`
- `src/model/struct/settings.py`
- `src/portal/season/libs/src/auth.ts`
- `src/portal/season/route/auth/controller.py`
- `src/route/api-system-assets/app.json`
- `src/route/api-system-assets/controller.py`
- `src/route/api-system-assets-path/app.json`
- `src/route/api-system-assets-path/controller.py`
- `tests/api/test_migration_schema.py`
- `tests/api/test_system_settings_dynamic_menu.py`

## 작업 내용

- `/system` 화면에서 고급 설정 토글을 제거하고 일반 설정과 Harbor/GitLab 설정을 항상 보이도록 다시 구성했다.
- `general.browser_title`, `general.favicon_url`, `general.logo_url`를 `/auth/check`의 `appearance` payload와 브라우저 localStorage에 연결해 로그인 화면, sidebar, 브라우저 title/favicon에 실제로 반영되도록 수정했다.
- favicon/logo 업로드 라우트를 추가하고 업로드 파일을 WIZ workspace `data/system-assets/` 아래에 저장하도록 분리했다.
- Harbor/GitLab 설정 저장소를 dedicated integration model로 정리하고, `/system` 화면에서 secret 보기/숨기기와 연결 테스트를 지원하도록 추가했다.
- Cloudflare 전역 설정을 `/system`에서 제거하고 `/domains` 화면을 zone 목록 + 상세 + DNS record CRUD 구조로 재작성했다.
- `cloudflare_dns_records` 캐시 테이블과 zone별 `last_sync_at`, `last_sync_status`, `record_count`를 추가해 sync 결과를 DB에 보관하도록 migration `006`을 추가하고 실제 DB에도 적용했다.
- `infra_catalog`와 dashboard/images 연동 요약이 Harbor/GitLab dedicated table과 Cloudflare zone summary를 읽도록 맞췄다.
- 문서와 정적 테스트를 새 구조 기준으로 갱신했다.

## 검증

- `python -m compileall src/app src/model src/route src/portal/season/route/auth config`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `/opt/conda/envs/docker-infra/bin/python project/main/scripts/docker_infra_migrate.py up`: `006` 적용 완료
- `systemctl restart wiz.docker-infra` 후 `curl http://127.0.0.1:3001/api/system/health`: 응답 확인, DB schema version `006`
- `PYTHONPATH=. DOCKER_INFRA_TEST_PASSWORD='____' /opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract tests.api.test_migration_schema tests.api.test_system_settings_dynamic_menu`: 통과
- live smoke:
  - `/auth/check`에 `appearance` payload 포함 확인
  - `/wiz/api/page.system/load`에 Harbor/GitLab integration payload 확인
  - `/wiz/api/page.domains/load` 200 응답 및 summary payload 확인
  - `/api/system/assets` 업로드 + GET 조회 확인 후 임시 파일 정리
- `git diff --check`: 통과
