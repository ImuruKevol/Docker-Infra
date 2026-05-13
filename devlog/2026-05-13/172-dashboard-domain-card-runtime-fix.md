# 대시보드 도메인 카드 조회 SQL 확정과 서비스 재시작 반영

- **ID**: 172
- **날짜**: 2026-05-13
- **유형**: 버그 수정 / 운영 반영

## 작업 요약
대시보드 등록 도메인 카드가 빈 목록으로 보이지 않도록 등록 도메인 조회를 `cloudflare_zones` 기준의 LATERAL 집계로 다시 단순화했습니다.
등록 도메인은 항상 `cloudflare_zones` 목록에서 가져오고, 각 도메인에 매칭되는 `service_domains`/`services` 연결 수와 서비스명을 별도 집계합니다.
등록 도메인에 매칭되지 않는 서비스 도메인은 보조 목록으로 추가해 카드가 비는 경우를 줄였습니다.
변경 후 빌드 산출물과 bundle 산출물 반영을 확인하고 `wiz.docker-infra.service`를 재시작했습니다.

## 원문 요청사항
```text
똑바로 안할래? 대시보드에 등록된 도메인 카드에 하나도 안보이잖아. 등록된 도메인 카드에 목록이 보여야 해. 다시 확실하게 확인해줘.
```

## 변경 파일 목록
- `src/model/struct/infra_catalog_registry.py`: 등록 도메인 카드 조회를 `cloudflare_zones` 기준으로 고정하고 연결 서비스 집계 LATERAL 쿼리 및 unmatched service domain fallback 추가.
- `devlog.md`, `devlog/2026-05-13/172-dashboard-domain-card-runtime-fix.md`: 작업 이력 기록.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/infra_catalog_registry.py src/app/page.dashboard/api.py` 성공.
- 로컬 DB에서 카드용 SQL 직접 실행 성공(`registered=3`, `unmatched_service_domains=0`).
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest` 성공.
- `build/src`와 `bundle/src` 모두 변경된 도메인 조회 코드 포함 확인.
- `systemctl restart wiz.docker-infra.service` 실행 후 서비스 active 및 신규 프로세스 기동 확인.
- `https://infra-dev.nanoha.kr/dashboard`의 `Last-Modified`가 최신 빌드 시각으로 갱신됨 확인.
- `journalctl -u wiz.docker-infra.service -n 20 --no-pager`에서 재시작 후 Flask 기동 로그 확인.
- `git diff --check` 성공.

## 남은 리스크
- 인증 세션이 없어 운영 `/wiz/api/page.dashboard/overview`의 실제 응답 본문은 직접 확인하지 못했습니다.
