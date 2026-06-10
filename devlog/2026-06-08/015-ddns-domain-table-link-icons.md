# DDNS 도메인 표 정렬과 링크 아이콘 UI 보강

- 날짜: 2026-06-08
- 작업 ID: 015
- 리뷰 ID: wmidmxmacideroaomknwjpmugxraddqf
- 프로젝트: main

## 사용자 요청

- DDNS 관리 서버 표의 등록 컬럼 th/td를 가운데 정렬로 변경.
- DDNS 관리 서버 표의 작업 컬럼에서 삭제 버튼이 줄바꿈되지 않도록 수정.
- 등록된 DDNS 레코드의 Hostname 값을 새 창에서 여는 a 태그로 변경.
- 연결 서비스와 연결 대상에 각 상세 화면으로 이동하는 링크 버튼을 추가하되, 텍스트 없이 border 없는 아이콘만 표시.

## 변경 파일

- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `tests/api/test_domain_management_ui.py`
- `devlog.md`
- `devlog/2026-06-08/015-ddns-domain-table-link-icons.md`

## 작업 내용

- DDNS 관리 서버 표의 등록 컬럼 헤더와 본문을 `text-center`/`items-center`로 변경.
- 작업 컬럼 폭을 늘리고 버튼 그룹에 `whitespace-nowrap`를 적용해 삭제 버튼 줄바꿈을 방지.
- DDNS 레코드 Hostname을 `https://{hostname}` 새 창 링크로 변경.
- 연결 서비스는 서비스 상세(`/services/{service_id}`), 연결 대상은 서버 상세(`/servers/{proxy_node_id}`)로 이동하는 border 없는 아이콘 링크로 변경.
- 정적 계약 테스트에 정렬, nowrap, hostname 링크, 서비스/서버 아이콘 링크 기준을 추가.

## 검증 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui` 통과.
- `git diff --check -- src/app/page.domains/view.pug src/app/page.domains/view.ts tests/api/test_domain_management_ui.py` 통과.
- `wiz_project_build(projectName="main", clean=false)` 통과.
- 쿠키 `season-wiz-project=main; season-wiz-devmode=true`로 `https://infra-dev.nanoha.kr/domains` 200 응답 확인.
- 같은 쿠키로 `/wiz/api/page.domains/load` POST는 엔드포인트 도달 후 로그인 세션 부재로 `AUTHENTICATION_REQUIRED` 응답 확인.

## 남은 리스크

- 연결 대상 아이콘은 `service_domains.metadata.proxy_node_id`가 있는 레코드에서만 표시된다.
- 원격 실제 데이터 렌더링은 로그인 세션 없이 확인하지 못했다.
