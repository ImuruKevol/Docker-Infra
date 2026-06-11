# 006 DDNS 관리 서버 컬럼 순서와 등록 레코드 필터 UI 보정

- 날짜: 2026-06-11
- 리뷰 ID: khvtwhgjufkbcnrbmrsllinvegkajgtn

## 사용자 원 요청

- DDNS 관리 서버의 Dispatcher 요청 컬럼도 말줄임표 처리되지 않도록 할 것.
- DDNS 관리 서버 컬럼 순서를 `[서버명, 상태, Dispatcher 요청, Host, IP, 등록, DDNS 서버 API, 작업]`으로 바꿀 것.
- 등록된 DDNS 레코드의 연결 서비스, 연결 대상 아이콘 버튼을 텍스트 바로 옆에 붙일 것.
- Hostname 컬럼 링크 방식을 연결 서비스, 연결 대상 컬럼과 같은 방식으로 통일할 것.
- 마지막 갱신 컬럼 값이 줄바꿈되지 않도록 할 것.
- DDNS 관리 서버별로 필터링할 수 있는 토글 버튼 필터를 추가할 것.

## 변경 파일

- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `tests/api/test_domain_management_ui.py`
- `devlog.md`
- `devlog/2026-06-11/006-ddns-column-order-registration-filter.md`

## 변경 내용

- DDNS 관리 서버 테이블 컬럼을 요청 순서대로 재배치하고 Dispatcher 요청 컬럼 폭과 nowrap 처리를 보강했다.
- 등록된 DDNS 레코드의 Hostname, 연결 서비스, 연결 대상 링크 아이콘을 텍스트 바로 옆의 작은 아이콘 버튼 형태로 통일했다.
- 마지막 갱신 컬럼 header와 value에 nowrap을 적용했다.
- DDNS 관리 서버별 등록 레코드 토글 필터와 필터 적용 pagination/count 처리를 추가했다.
- 정적 계약 테스트에 컬럼 순서, 필터, nowrap, 링크 배치 검증을 보강했다.

## 검증 결과

- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_domain_management_ui.py`
- 성공: WIZ project build `main`
- 성공: `git diff --check`
- 제한 확인: `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가해 `https://infra-dev.nanoha.kr/domains`에 접근했으나 인증 세션이 없어 `/access`로 리다이렉트됐다. 콘솔 오류는 없었다.
