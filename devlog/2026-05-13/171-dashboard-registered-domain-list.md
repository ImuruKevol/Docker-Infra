# 대시보드 등록 도메인 목록 표시 기준 단순화

- **ID**: 171
- **날짜**: 2026-05-13
- **유형**: 버그 수정 / UX 개선

## 작업 요약
대시보드 도메인 카드를 복잡한 사용/미등록 판정 대신 Docker Infra에 등록된 도메인 목록 기준으로 단순화했습니다.
Cloudflare 도메인 설정이 있으면 `cloudflare_zones` 전체를 보여주고, 각 도메인에 연결된 서비스 수를 함께 계산합니다.
등록 도메인 설정이 없는 환경에서는 서비스에 직접 등록된 `service_domains` 목록으로 fallback해 빈 카드가 나오지 않도록 했습니다.

## 원문 요청사항
```text
도메인 목록이 여전히 보이지 않아. 그냥 Docker Infra에 등록된 도메인 목록을 보여주고, 각 도메인별로 연결 서비스 갯수를 표시해줘.
```

## 변경 파일 목록
- `src/model/struct/infra_catalog_registry.py`: 대시보드 도메인 사용 현황 조회를 등록 도메인 우선 목록으로 단순화하고 서비스 연결 수/서비스명 집계 추가.
- `src/app/page.dashboard/view.pug`: 도메인 카드 문구와 요약 지표를 등록 도메인/연결 서비스 기준으로 변경.
- `src/app/page.dashboard/view.ts`: 도메인별 연결 서비스 요약 텍스트 helper 추가.
- `devlog.md`, `devlog/2026-05-13/171-dashboard-registered-domain-list.md`: 작업 이력 기록.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/infra_catalog_registry.py src/app/page.dashboard/api.py` 성공.
- 로컬 DB에서 대시보드 도메인 조회 SQL 실행 성공(`zone_rows=3`, `service_domain_rows=1`).
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest` 성공.
- `git diff --check` 성공.

## 남은 리스크
- 실제 ReviewOps 브라우저 화면에서 도메인 카드 렌더링까지 직접 확인하지는 못했습니다.
