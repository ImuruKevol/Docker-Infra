# 서비스 컨테이너 웹 터미널 exec 기능 추가

- **ID**: 001
- **날짜**: 2026-05-22
- **유형**: 기능 추가

## 작업 요약
서비스 상세 구성 탭의 컨테이너별 액션 메뉴에 터미널 접속 액션을 추가했습니다.
선택한 서비스 컨테이너에 대해 Docker exec 기반 웹 터미널을 열고, bash 우선 접속 후 sh fallback 및 shell 미존재 오류를 처리하도록 구현했습니다.

## 원문 요청사항
```text
작업 진행해줘.
기능은 서비스 상세에 구성에서 각 컨테이너별 액션 컨텍스트 메뉴에 추가하면 돼.

각 서비스 컨테이너에 bash 또는 sh도 접속할 수 있는 웹 터미널 기능을 만들고 싶어.
기본으로는 bash를 사용하고, bash가 없는 컨테이너는 sh로, 그것도 없으면 에러 메세지를 띄우도록.
```

## 변경 파일 목록
- `src/app/page.services/view.pug`: 컨테이너 액션 메뉴에 터미널 액션을 추가하고, xterm 기반 컨테이너 터미널 모달을 추가.
- `src/app/page.services/view.ts`: xterm/socket 연결 상태, 컨테이너 터미널 연결/해제/리사이즈/출력 처리 로직 추가.
- `src/app/page.services/socket.py`: 서비스 컨테이너 범위 검증 후 컨테이너 터미널 세션을 생성하는 Socket.IO 핸들러 추가.
- `src/model/struct/nodes_terminal.py`: Docker exec 컨테이너 PTY 세션 생성, bash 우선/sh fallback, shell 미존재 오류 처리 추가.
- `devlog.md`, `devlog/2026-05-22/001-service-container-terminal-exec.md`: 작업 이력 기록.

## 검증 결과
- `python -m py_compile project/main/src/model/struct/nodes_terminal.py project/main/src/app/page.services/socket.py` 통과.
- `wiz_project_build(projectName=main, clean=false)` 성공.
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' http://127.0.0.1:3001/services` 응답 200 확인.
- `curl -b 'season-wiz-project=main; season-wiz-devmode=true' http://127.0.0.1:3001/wiz/api/page.services/load` HTTP 200 wrapper와 인증 필요 응답 확인.
