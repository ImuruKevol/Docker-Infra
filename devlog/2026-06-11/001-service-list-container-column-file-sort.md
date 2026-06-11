# 001 서비스 목록 컨테이너 컬럼과 컨테이너 파일 탭 정렬 적용

- 날짜: 2026-06-11
- 리뷰 ID: jixfjvppxospvmmzezycshfkjramxlkr

## 사용자 원 요청

- 목록에서 버전 컬럼 삭제 및 컨테이너 컬럼 추가. 컨테이너 컬럼에는 해당 서비스의 컨테이너 목록과 외부로 오픈되는 포트들을 리스팅할 것.
- 상세 화면에서 컨테이너 파일 탭에 컨테이너 목록은 컨테이너 이름 순으로 정렬할 것.

## 변경 파일

- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-06-11/001-service-list-container-column-file-sort.md`

## 변경 내용

- 서비스 목록 테이블에서 `버전` 컬럼을 제거하고 `컨테이너` 컬럼을 추가했다.
- 목록 컨테이너 컬럼에 서비스 런타임 상태의 컨테이너 이름과 외부 공개 포트만 표시하도록 헬퍼를 추가했다.
- 컨테이너 내부 파일 탭의 컨테이너 선택 목록을 컨테이너 표시 이름 기준으로 정렬했다.
- 변경 계약을 확인하는 정적 테스트를 추가했다.

## 검증 결과

- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_list_container_column_and_file_sort_are_wired`
- 성공: WIZ project build `main`
- 제한 확인: Playwright Chromium 1440x900에서 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가해 `https://infra-dev.nanoha.kr/dashboard`에 접근했다. 테스트 비밀번호가 없어 `/access`로 리다이렉트됐고 콘솔 오류는 0건이었다.
