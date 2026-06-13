# 매크로 화면 통합 실행 패널과 첨부 다운로드 적용

## 요청

- 리뷰 ID: `xyhcmpuzprdgnwwivtupfxvpvcuxkktc`
- 제목: 매크로 기능 개선
- 원 요청: "작업 시작"
- 리뷰어 요청:
  - 서버 관리 상세에서 매크로 탭 제거
  - 매크로 화면 타이틀을 `전역 매크로`에서 `매크로`로 변경
  - 상단 카드 3개와 매크로 상태값 개념 제거
  - 목록 검색 input 위 `검색` 라벨 제거
  - 매크로 목록/코드 상세/수정 모달을 한 화면의 좌우 패널 구조로 통합
  - 오른쪽 패널 상단에 서버/서비스 실행 대상 토글과 custom search select 추가
  - 오른쪽 패널 하단 코드 표시가 다크모드 테마를 따르게 수정
  - 첨부 파일 클릭 다운로드 지원

## 변경 사항

- `/macros` 화면을 왼쪽 매크로 목록과 오른쪽 상세/실행/편집 패널 구조로 재구성했다.
- 기본 선택 상태를 비워두고, 목록에서 매크로를 클릭하면 오른쪽 패널에 실행 대상 선택, 실행 결과, 첨부 파일, 코드가 표시되도록 했다.
- 매크로 추가/수정을 별도 모달 대신 오른쪽 패널의 인라인 편집 폼으로 통합했다.
- 서버 목록과 실행 중인 서비스 컨테이너 목록을 매크로 화면 load API에 포함하고, 서버/서비스 토글에 custom search select를 연결했다.
- 매크로 실행 API와 operation polling API를 `/macros` 페이지에 추가하고, 서비스 대상 선택 시 해당 컨테이너가 위치한 서버에서 실행되도록 했다.
- 매크로 첨부 파일 다운로드 API와 프론트엔드 blob 다운로드 처리를 추가했다.
- 매크로 enabled 상태는 UI와 실행 차단에서 제거하고, 저장 시 사용 가능 상태로 정규화했다.
- 서버 상세 화면의 매크로 탭 버튼과 탭 본문을 제거했다.
- AI Agent의 서버 상태 매크로 실행 안내와 app event 대상을 `/macros` 기반 `macro.run`으로 갱신했다.
- 관련 정적 계약 테스트를 새 화면 구조와 API 계약에 맞게 갱신했다.

## 변경 파일

- `src/app/page.macros/api.py`
- `src/app/page.macros/view.pug`
- `src/app/page.macros/view.ts`
- `src/app/page.servers/view.pug`
- `src/app/page.servers/view.ts`
- `src/model/struct/ai_assistant.py`
- `src/model/struct/macros.py`
- `src/model/struct/macros_runner.py`
- `src/model/struct/macros_store.py`
- `tests/api/test_ai_agent_history.py`
- `tests/api/test_server_macros.py`
- `devlog.md`
- `devlog/2026-06-12/004-macro-unified-run-panel.md`

## 검증

- 성공: `python -m py_compile src/app/page.macros/api.py src/model/struct/ai_assistant.py src/model/struct/macros.py src/model/struct/macros_store.py src/model/struct/macros_runner.py tests/api/test_server_macros.py tests/api/test_ai_agent_history.py`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest tests.api.test_ai_agent_history.AIAgentHistoryStaticContractTest.test_agent_can_dispatch_page_control_actions`
- 성공: `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키 포함 `http://127.0.0.1:3001/macros`, `/servers` HEAD 요청 200 확인
- 참고: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract.WizStructureContractTest.test_frontend_detail_routes_are_explicit`는 기존 `page.domains`의 `routeZoneId` 구조 계약 불일치로 실패했다.
