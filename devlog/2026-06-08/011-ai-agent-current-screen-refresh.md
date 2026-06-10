# AI Agent 실행 후 현재 화면 API 재호출 추가

- 날짜: 2026-06-08
- ID: 011
- 리뷰 ID: hqwekbrhpnlzmzvkuyjvrtgrcvqihbxr

## 사용자 원 요청

작업 시작

리뷰어 요청:

- 예를 들어 "미사용 Compose 템플릿 file_share, gitlab, wikijs_site, wordpress_site 4개를 삭제해줘." 같은 동작을 실행한 뒤 Agent가 현재 화면 데이터를 다시 불러올 수 있게 한다.
- 응답 후 필요 시 현재 창 자체를 새로고침하지 않고 각 화면별 정보를 불러오는 API들만 다시 호출해서 새로고침할 수 있게 한다.

## 변경 파일

- `src/angular/app/app.component.ts`
- `src/app/layout.sidebar/view.pug`
- `src/app/layout.sidebar/view.ts`
- `src/model/struct/ai_assistant.py`
- `tests/api/test_ai_agent_history.py`
- `devlog.md`
- `devlog/2026-06-08/011-ai-agent-current-screen-refresh.md`

## 작업 내용

- AI Agent의 `refresh` 액션이 `location.reload()` 대신 현재 WIZ 화면 새로고침 이벤트를 발행하도록 변경했다.
- Agent가 write/destructive API 액션 또는 app_event 액션을 성공적으로 실행한 뒤 현재 화면 데이터 갱신을 자동 요청하도록 후처리를 추가했다.
- sidebar 레이아웃이 활성 라우트 컴포넌트를 추적하고, 현재 화면의 `load()` 계열 API만 재호출하도록 중계 로직을 추가했다.
- 대시보드, 서비스, 서버, 템플릿, 매크로, 작업 로그 화면은 선택 상태를 보존하는 인자로 재호출하도록 분기했다.
- AI Agent 프롬프트 계약에 `refresh` 액션이 브라우저 전체 새로고침이 아닌 WIZ 페이지 API 재호출임을 명시했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_ai_agent_history`: 통과
- `wiz_project_build(clean=false)`: 통과
- `curl -H 'Cookie: season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/dashboard`: HTTP 200

## 남은 리스크

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract`는 현재 작업 전부터 존재하는 구조 계약 위반들과 `page.domains` 라우트 기대값 불일치로 실패한다.
- 실제 Agent가 삭제 후 새 목록을 반영하는 브라우저 상호작용은 로컬/원격 실행 세션에서 수동 확인이 추가로 필요하다.
