# 서비스 파일 트리와 컨테이너 내부 파일 관리 통합

## 사용자 요청

ReviewOps 리뷰 ID `qklfbvdopgfyvgupflfuolyislfknevd`의 "서비스 관리 화면 개선" 요청.

- 기존 서비스 파일 탭에 표시되던 서비스 디렉토리 파일 트리를 Compose/Nginx 탭과 통합
- 통합 화면은 왼쪽 파일 트리, 오른쪽 파일 에디터 형태로 구성
- 서비스 파일 탭은 컨테이너 내부 파일 조회, 업로드, 파일 트리 제어가 가능하도록 변경

## 변경 파일

- `config/docker_infra.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/nodes_runtime_files.py`
- `src/model/struct/file_tree.py`
- `src/app/component.file.tree/app.json`
- `src/app/component.file.tree/view.html`
- `src/app/component.file.tree/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`

## 변경 내용

- `component.file.tree`에 선택 모드, 임베디드 표시, 선택 파일 highlight, `fileSelect` 출력 이벤트를 추가했다.
- 서비스 상세의 `Compose/Nginx` 탭을 좌측 관리 설정/서비스 디렉토리 파일 트리와 우측 Monaco 에디터 레이아웃으로 재구성했다.
- 서비스 디렉토리 파일 선택 시 일반 파일은 에디터에서 직접 저장할 수 있고, Compose 파일은 기존 검사 후 저장/다시 적용 흐름을 유지하도록 연결했다.
- `files` 탭 라벨과 내용을 컨테이너 내부 파일 관리로 바꾸고, 실행 컨테이너 선택 후 `/api/file-tree`의 `container` scope를 사용하도록 구성했다.
- `/api/file-tree` 모델에 `container` scope와 `write` 액션을 추가했다.
- 로컬/원격 노드의 컨테이너 내부 파일 list/read/write/mkdir/rename/delete/move 명령을 추가하고, 로컬 마스터 allowlist 기본값에 컨테이너 파일 변경 명령을 반영했다.

## 검증

- `python -m py_compile project/main/config/docker_infra.py project/main/src/model/struct/local_command_catalog.py project/main/src/model/struct/nodes_runtime_files.py project/main/src/model/struct/file_tree.py` 통과
- `wiz_project_build(projectName="main", clean=false)` 성공
- `https://infra-dev.nanoha.kr/dashboard`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키 포함 요청 시 HTTP 200 확인
- `/api/file-tree`에 동일 쿠키로 요청 시 로그인 세션 부재로 `401 AUTHENTICATION_REQUIRED` 반환 확인. 라우트는 응답했지만 실제 컨테이너 파일 기능은 로그인된 브라우저 세션에서 추가 확인이 필요하다.
