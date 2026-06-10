# 서비스 수정 구성 탭 연결 포트 컬럼 여백 축소

- 날짜: 2026-06-10
- 리뷰 ID: zsrwyfbkctvcgdzkpqnohoqnsknjuibh
- 요청: 서비스 수정 모달의 구성 탭에서 연결 포트 컬럼 오른쪽에 불필요한 공간이 많이 남는 문제를 개선.

## 변경 파일

- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-06-10/014-service-edit-components-port-column-width.md`

## 변경 내용

- 구성 탭 표의 최소 폭을 줄이고, 연결 포트 컬럼 폭을 300px에서 220px로 축소했다.
- 구성/버전 컬럼 폭도 함께 줄여 이미지 컬럼이 남는 폭을 자연스럽게 가져가도록 조정했다.
- 포트 입력 칩의 내부 간격과 입력 폭을 줄이고, 포트가 없는 상태의 별도 텍스트를 제거해 오른쪽 여백이 과하게 보이지 않도록 했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- `python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_edit_wizard_contract_is_wired` 성공.
- `curl -I`에 `season-wiz-project=main; season-wiz-devmode=true` 쿠키를 포함해 `/access`, `/services` 경로 모두 `200 OK` 확인.
