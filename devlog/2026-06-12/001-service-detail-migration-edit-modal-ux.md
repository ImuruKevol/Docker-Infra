# 서비스 상세 마이그레이션/수정 모달 UX 보정

## 요청

- 리뷰 ID: `rwckyzwrnxhehtpkgyujeowghxhklfjx`
- 제목: 서비스 관리 화면 상세 수정
- 원 요청:
  - "마이그레이션 버튼을 버전 이력 탭으로 이동해줘."
  - "마이그레이션 모달에서 이동할 서버 목록 select가 overflow hidden되어서 잘렸어. 수정 후 브라우저 화면에서 확인해줘. PW: [REDACTED]"
  - "마이그레이션 모달에서 컨테이너 일시 정지 후 스냅샷은 굳이 표시하지 말고 기본적으로 그냥 일시정지 후 스냅샷을 뜨도록 해줘."
  - "수정 모달에서 고급 수정을 누른 다음 다시 기본 간편 수정 모드로 돌아갈 수 있는 버튼이 없어."
  - 후속 요청: "마이그레이션 모달을 제대로 확인해줘. 첨부한 스크린샷과 같이 나오고 있어. PW: [REDACTED]"

## 변경 사항

- 서비스 상세 헤더의 `마이그레이션` 버튼을 제거하고 `버전 이력` 탭 액션 영역으로 이동했다.
- 마이그레이션 모달의 서버 선택 UI를 공통 검색 select에서 네이티브 `select`로 교체해 모달 내부에서 잘림 없이 표시되도록 했다.
- 마이그레이션 모달의 `컨테이너 일시 정지 후 스냅샷` 체크 옵션을 제거하고 API 요청은 항상 `pause: true`로 보낸다.
- 수정 모달 고급 수정 상태에서 `간편 수정` 버튼을 표시하고, 누르면 기본 수정 모드로 돌아가도록 했다.
- 관련 정적 계약 테스트를 변경된 UX 기준으로 갱신했다.

## 변경 파일

- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `tests/api/test_service_migration.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-06-12/001-service-detail-migration-edit-modal-ux.md`

## 검증

- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `python -m unittest tests.api.test_service_migration -q`
- 성공: `python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_release_contract_is_wired tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_edit_wizard_contract_is_wired -q`
- 성공: Playwright 브라우저 검증
  - `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키와 제공된 검증 비밀번호로 로컬 WIZ 서버 로그인.
  - `/services/65f94590-edba-4279-9aec-5c481ac05439/versions`에서 `마이그레이션` 버튼이 버전 이력 탭에 표시됨 확인.
  - 마이그레이션 모달에서 서버 선택 네이티브 `select`가 모달 내부에 정상 배치되고 공통 검색 select가 남아 있지 않음 확인.
  - 마이그레이션 모달에서 `컨테이너 일시 정지 후 스냅샷` 옵션 미표시 확인.
  - 브라우저 측정: `selectWithinModal=true`, `hasCustomSearchSelect=false`, `hasPauseOption=false`. 스크린샷: `.runtime/reviewops-migration-modal-native-select.png`
  - 수정 모달에서 `고급 수정` 후 `간편 수정` 버튼 표시와 기본 수정 모드 복귀 확인. 스크린샷: `.runtime/reviewops-edit-basic-return.png`
- 참고: `python -m unittest tests.api.test_services_preflight -q` 전체 실행은 기존 `page.services.create` 템플릿 변수 문구 기대값 불일치로 실패했다.
