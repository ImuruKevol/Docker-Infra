# 서비스 수정 고급 모드 탭 레이아웃 정리

- 날짜: 2026-06-10
- 리뷰 ID: zsrwyfbkctvcgdzkpqnohoqnsknjuibh
- 요청: 고급 모드 모달에서 기본 정보 탭 외 구성, 도메인, 고급 탭의 레이아웃과 디자인이 난잡하고, 특히 컨테이너가 많아졌을 때 고급 탭이 확장되기 어려운 구조를 개선.

## 변경 파일

- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `devlog.md`
- `devlog/2026-06-10/010-service-edit-advanced-layout-polish.md`

## 변경 내용

- 서비스 수정 고급 모달 폭을 넓히고 좌측 탭 내비게이션 폭을 줄여 편집 영역 가용 폭을 늘렸다.
- 구성 탭을 카드 그리드에서 표 기반 레이아웃으로 바꿔 이미지, 버전, 포트 편집을 한 줄 단위로 비교 가능하게 정리했다.
- 도메인 탭을 공개 주소, 연결 대상, 미리보기 순서의 단일 흐름으로 재배치하고 포트 후보를 표 형태로 정리했다.
- 고급 탭은 모든 컨테이너를 동시에 펼치지 않고, 왼쪽 구성 목록에서 하나를 선택해 오른쪽 패널에서 환경변수와 볼륨을 편집하도록 변경했다.
- 선택된 구성 상태와 요약 표시용 TypeScript 헬퍼를 추가하고, 선택 대상이 없을 때도 편집 함수가 안전하게 동작하도록 방어 처리를 보강했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- `python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_edit_wizard_contract_is_wired` 성공.
- `curl -I`에 `season-wiz-project=main; season-wiz-devmode=true` 쿠키를 포함해 `/access`, `/services` 경로 모두 `200 OK` 확인.
