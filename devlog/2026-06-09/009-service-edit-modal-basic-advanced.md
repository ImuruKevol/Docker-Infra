# 서비스 수정 모달 기본/고급 분리와 빠른 기본 저장 경로 추가

- 날짜: 2026-06-09
- ID: 009
- 리뷰 ID: zsrwyfbkctvcgdzkpqnohoqnsknjuibh

## 사용자 요청

- 현재 서비스 수정 모달에 AI 기능이 들어가있는데 제거할 것.
- 서비스 수정 모달에서 단순히 이름, 설명만 바꿨는데 draft 상태로 바뀌는 등 상태 변경 시에 대한 로직이 개판임. 그리고 저장도 굉장히 오래걸리는데, 단순히 이름 설명만 바꾸는데 오래걸릴 이유가 없음.
- 서비스 수정 모달의 수정 난이도가 너무 높음. 생성 시 입력했던 정도의 난이도로 낮추고, 현재 수준은 고급 수정 모드같은걸로 분리해줘.

## 변경 파일

- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services/api.py`
- `src/model/struct/services_update.py`
- `devlog.md`
- `devlog/2026-06-09/009-service-edit-modal-basic-advanced.md`

## 작업 내용

- 서비스 수정 모달의 AI 수정안 UI와 관련 TypeScript 경로를 제거했다.
- 수정 모달 기본 화면을 이름, 설명, DDNS 도메인 설정 중심으로 단순화하고, 구성/도메인 대상 포트/환경변수/볼륨 수정은 `고급 수정` 버튼 뒤로 분리했다.
- 기본 모달 열기에서 source 상세 강제 로드를 제거하고, 고급 수정 진입 시에만 compose/components 정보를 지연 로드하도록 변경했다.
- `update_service_basic` API와 `services.update_basic()` 모델 경로를 추가해 이름/설명 저장 시 compose 렌더링, preflight, 파일 쓰기, `status = 'draft'` 변경을 수행하지 않도록 했다.
- 기본 저장 후에는 전체 목록/상세 재조회 대신 lightweight 응답을 현재 목록과 상세에 반영하도록 조정했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- `python -m py_compile project/main/src/app/page.services/api.py project/main/src/model/struct/services_update.py` 성공.
- `python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_edit_wizard_contract_is_wired` 성공.
- `rg`로 수정 모달 전용 `editAi`, `AI 수정안`, `editSection() === 'ai'` 참조가 제거됐는지 확인했다.
- 지정 쿠키 `season-wiz-project=main`, `season-wiz-devmode=true`를 붙여 로컬 WIZ 서버 `http://127.0.0.1:3001/access`, `http://127.0.0.1:3001/services`가 200 응답하는 것을 확인했다.

## 남은 리스크

- 실제 서비스 데이터에 대한 `update_service_basic` 호출은 운영 서비스 ID와 로그인 세션이 필요해 직접 저장 플로우까지는 실행하지 못했다.
- 기본 모드의 도메인 변경은 DB 설정 저장과 서버 적용이 분리되어 있으며, 런타임 nginx 반영은 `저장 후 적용` 경로에서 확인해야 한다.
