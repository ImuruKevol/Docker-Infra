# AI Agent 설정 버튼 좌측 정렬

- 날짜: 2026-05-29
- 리뷰 ID: zqedfbguxpwwfmqiouspvybeelnfvedm
- 요청: Codex의 최신 확인/업그레이드 버튼을 오른쪽 정렬하지 않고 줄바꿈 후 왼쪽에 배치. 브라우저 로그인/상태 확인 버튼을 왼쪽 정렬하고 안내 문구와 실행 테스트 버튼 제거. Claude Code와 헤르메스도 같은 느낌으로 정리.

## 변경 요약

- Codex 버전 문단 아래 최신 확인/업그레이드 버튼을 별도 줄의 좌측 정렬 버튼 그룹으로 변경했다.
- Codex 하단 버튼 그룹을 좌측 정렬하고 실행 테스트 버튼과 관련 결과 문구를 화면에서 제거했다.
- Claude Code/헤르메스 Agent 영역의 하단 버튼 그룹도 좌측 정렬하고 실행 테스트 버튼과 결과 문구를 제거했다.
- 시스템 설정 정적 계약 테스트에 제거된 문구와 실행 테스트 버튼이 다시 노출되지 않도록 검증을 추가했다.

## 변경 파일

- `src/app/page.system/view.pug`
- `tests/api/test_system_settings_dynamic_menu.py`
- `devlog.md`
- `devlog/2026-05-29/002-ai-agent-button-left-alignment.md`

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/model/struct/ai_assistant.py src/app/page.system/api.py`: 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_system_settings_dynamic_menu.SystemSettingsStaticContractTest`: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' http://127.0.0.1:3001/system`: HTTP 200 확인
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' -X POST http://127.0.0.1:3001/wiz/api/page.system/load`: HTTP 200 wrapper와 인증 필요 응답 확인

## 남은 리스크

- 인증 세션이 없는 환경이라 실제 로그인 이후의 브라우저 상호작용은 검증하지 못했다.
