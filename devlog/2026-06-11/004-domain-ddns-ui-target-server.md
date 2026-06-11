# 004 DDNS 도메인 관리 UI 컬럼과 등록 레코드 서버 표시 보정

- 날짜: 2026-06-11
- 리뷰 ID: khvtwhgjufkbcnrbmrsllinvegkajgtn

## 사용자 원 요청

- DDNS 관리 서버 카드와 상단 헤더에 중복된 추가 버튼이 있으므로 카드의 추가 버튼을 삭제하고 헤더의 추가 버튼을 그 자리로 이동할 것.
- IP 컬럼의 말줄임표를 제거할 수 있도록 width를 늘릴 것.
- Host 컬럼에는 wildcard suffix만 표시할 것. 예: `*.sub.nanoha.kr`
- 등록된 DDNS 레코드의 연결 서비스 컬럼 width를 늘릴 것.
- 연결 대상 컬럼은 포트 정보 없이 어떤 서버에 떠있는지 표시하고, `bus.sub.nanoha.kr` 명함 관리 서비스의 서버 매핑도 확인할 것.

## 변경 파일

- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `src/model/struct/domains_ddns.py`
- `tests/api/test_domain_management_ui.py`
- `devlog.md`
- `devlog/2026-06-11/004-domain-ddns-ui-target-server.md`

## 변경 내용

- 상단 헤더의 DDNS 서버 추가 버튼을 제거하고, DDNS 관리 서버 카드 액션 영역에 단일 기본 버튼으로 배치했다.
- DDNS 관리 서버 테이블에서 중복 wildcard suffix 컬럼을 정리하고 Host 컬럼에 `*.{domain_suffix}`만 표시하도록 변경했다.
- IP 컬럼 폭을 늘리고 `truncate`를 제거해 말줄임표가 생기지 않도록 조정했다.
- 등록된 DDNS 레코드 테이블의 연결 서비스 컬럼 폭을 늘렸다.
- 연결 대상 컬럼은 서버명과 서버 host만 표시하도록 정리하고, 포트/compose/topology 문구를 제거했다.
- DDNS 등록 조회 쿼리에 `nodes` 매핑 fallback을 추가해 서비스 도메인 metadata가 비어 있어도 runtime status와 target node policy로 실행 서버를 계산한다.

## 검증 결과

- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_domain_management_ui.py`
- 성공: WIZ project build `main`
- 성공: DB 조회 기준 `bus.sub.nanoha.kr`는 `mini3` 서버로 매핑됨을 확인했다.
- 제한 확인: `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가해 `https://infra-dev.nanoha.kr/domains`에 접근했으나 인증 세션이 없어 `/access`로 리다이렉트됐다. 콘솔 오류는 없었다.
