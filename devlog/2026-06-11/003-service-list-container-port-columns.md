# 003 서비스 목록 컨테이너/포트 컬럼 분리

- 날짜: 2026-06-11
- 리뷰 ID: jixfjvppxospvmmzezycshfkjramxlkr

## 사용자 원 요청

- 컨테이너 컬럼을 두 개로 나누는 것이 나을 것 같다.
- 기존 컨테이너 컬럼에는 컨테이너 이름 목록만 리스팅한다.
- 사용 포트는 포트 컬럼을 만들어 `app: 22 -> 22/tcp`, `app: 3001 -> 3000/tcp`처럼 기존 포트 뱃지 앞에 컨테이너명을 추가한다.

## 변경 파일

- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-06-11/002-service-list-container-port-columns.md`

## 변경 내용

- 서비스 목록 테이블을 `컨테이너`와 `포트` 컬럼으로 분리했다.
- 컨테이너 컬럼은 컨테이너 이름 목록만 표시하도록 정리했다.
- 포트 컬럼은 외부 공개 포트 뱃지에 컨테이너명을 접두어로 붙여 표시하도록 `serviceListPortBadges` 헬퍼를 추가했다.
- 정적 테스트를 새 컬럼 구조 기준으로 갱신했다.

## 검증 결과

- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_list_container_and_port_columns_are_wired`
- 성공: `git diff --check`
- 성공: WIZ project build `main`
- 제한 확인: Playwright Chromium 1440x900에서 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가해 `https://infra-dev.nanoha.kr/dashboard`에 접근했다. 테스트 비밀번호가 없어 `/access`로 리다이렉트됐고 콘솔 오류는 0건이었다.
