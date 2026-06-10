# 서비스 상세 컨테이너 컨텍스트 메뉴 레이어 보정

## 사용자 요청

작업 시작

리뷰 ID: `izgjrjysinbngnjrkguhscmgsdtqcvgq`

리뷰 내용:
- 첨부한 스크린샷과 같이 컨테이너 컨텍스트 메뉴가 아래로 깔리는 버그가 있어.

## 변경 파일

- `src/app/page.services/view.pug`
  - 서비스 상세 실행 상태 영역의 외부 오픈/내부 전용 컨테이너 메뉴에 `service-runtime-container-menu`와 `service-runtime-container-menu-panel` class hook을 추가했다.
- `src/app/page.services/view.scss`
  - 열린 컨테이너 메뉴와 메뉴 패널의 `z-index`를 60으로 올려 다음 컨테이너 카드/섹션보다 위에 렌더링되도록 했다.
- `tests/api/test_services_preflight.py`
  - 컨테이너 메뉴 레이어 보정 class와 스타일 계약을 서비스 상세 정적 테스트에 추가했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_detail_operator_runtime_summary_is_wired` 통과.
- `wiz_project_build(projectName=main, clean=false)` 통과.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 포함한 `curl -I https://infra-dev.nanoha.kr/dashboard`가 `200 OK`로 응답함을 확인했다.
- 빌드 산출물 `build/dist/build/main.js`에 `service-runtime-container-menu`, `service-runtime-container-menu-panel`, `z-index: 60` 포함을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight` 전체 실행은 기존 작업트리 상태의 비관련 계약 불일치로 실패했다. 실패 범위는 `page.services.create/view.ts`의 `deploy_service_background`, `this.creationMode() === 'template'` 기대값 누락 2건이다.
- 로그인 기반 Playwright E2E는 `DOCKER_INFRA_TEST_PASSWORD` 환경 변수가 없어 실행하지 못했다.
