# 서비스 상세 컨테이너 메뉴 상위 stacking context 보강

## 사용자 요청

아직도 아래로 깔리고 있잖아.

PW: `[redacted]`

리뷰 ID: `izgjrjysinbngnjrkguhscmgsdtqcvgq`

## 변경 파일

- `src/app/page.services/view.pug`
  - 외부 오픈/내부 전용 컨테이너 그룹에 `service-runtime-container-group` class를 추가했다.
  - 각 컨테이너 카드에 `service-runtime-container-card` class를 추가했다.
- `src/app/page.services/view.scss`
  - 열린 메뉴를 가진 그룹과 카드에 `:has(.service-runtime-container-menu[open])` 기반 z-index를 추가했다.
  - 메뉴와 패널 z-index를 90으로 올려 카드/그룹 stacking context 위에 렌더링되도록 했다.
- `tests/api/test_services_preflight.py`
  - 컨테이너 그룹/카드 stacking context class와 스타일 계약을 추가했다.

## 확인 결과

- Playwright로 `https://infra-dev.nanoha.kr/services/51137111-cbff-4480-aba6-8815c39b5cdc`에서 로그인 후 재현했다.
  - 수정 전 같은 좌표의 최상단 요소가 아래 `db` 카드였음을 확인했다.
  - 수정 후 같은 좌표의 최상단 요소가 메뉴 패널 내부 `삭제` 버튼으로 확인됐다.
  - 확인된 computed style: panel/menu `z-index: 90`, card `z-index: 80`, group `z-index: 70`.
- `wiz_project_build(projectName=main, clean=false)` 통과.
- 컨테이너 메뉴 레이어 관련 정적 토큰 검사 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_detail_operator_runtime_summary_is_wired`는 현재 작업트리의 비관련 문구 계약 불일치(`Compose 원문 및 Nginx 설정` 누락)로 실패했다.
