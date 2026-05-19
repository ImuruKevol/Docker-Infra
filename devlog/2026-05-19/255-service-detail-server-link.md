# 서비스 상세 서버 요약에서 서버 상세 링크 추가

- 날짜: 2026-05-19
- ID: 255
- 리뷰 ID: widvtkqcznlhrydxkmjmhvvzehukysny

## 사용자 요청

서비스 상세의 "서버 / 인증서" 영역에서 표시되는 서버 옆에 링크 아이콘을 추가하고, `routerLink`로 서버 상세 화면으로 바로 이동할 수 있게 해달라는 요청.

## 변경 파일

- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.servers/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-19/255-service-detail-server-link.md`

## 작업 내용

- 서비스 상세 서버 요약 옆에 링크 아이콘 버튼을 추가하고 `/servers?node_id=...` routerLink/queryParams로 연결.
- 런타임 컨테이너, 도메인, 스택 작업의 등록 서버 ID를 모아 첫 번째 등록 서버 상세로 이동하도록 보강.
- 서버 관리 화면이 `node_id` 또는 `selected_node_id` query string을 읽어 해당 서버를 선택해 로드하도록 추가.
- 정적 계약 테스트에 서버 상세 링크 경로와 query string 선택 로직을 추가.

## 검증

- `PYTHONDONTWRITEBYTECODE=1 /opt/conda/envs/docker-infra/bin/python -m unittest project/main/tests/api/test_services_preflight.py`
- `wiz_project_build(projectName="main", clean=false)`
- `curl -I` with `season-wiz-project=main` and `season-wiz-devmode=true` cookies against `https://infra-dev.nanoha.kr/services`

결과: 모두 성공.
