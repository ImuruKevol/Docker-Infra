# 서비스 디렉터리 전체 조작 UI와 컨테이너 루트 파일 목록 보정

- 날짜: 2026-06-10
- 리뷰 ID: qklfbvdopgfyvgupflfuolyislfknevd
- 요청자: 권태욱

## 사용자 원문

서비스 디렉터리 부분에는 드래그&드랍으로 파일/폴더 업로드, 다운로드, 삭제, 디렉토리 생성 등 동작을 할 수 있어야 해. compact모드로 하지 말고 그냥 왼쪽 패널 크기 자체를 늘려.
---
그리고 컨테이너 파일에서 / 경로에 파일이 없을리가 없어. 니가 잘못 확인한거니까 확실하게 기능을 보완해줘.

## 변경 파일

- `src/app/component.file.tree/view.html`
- `src/app/component.file.tree/view.ts`
- `src/route/api-file-tree/controller.py`
- `src/app/page.services/view.pug`
- `src/model/struct/file_tree.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/nodes_runtime_files.py`
- `config/docker_infra.py`
- `devlog.md`
- `devlog/2026-06-10/012-service-directory-full-file-controls-container-root.md`

## 작업 내용

- Compose/Nginx 탭의 좌측 패널을 500px로 넓히고 서비스 디렉터리 파일 트리를 compact 모드가 아닌 전체 조작 모드로 되돌렸다.
- 서비스 디렉터리 트리에서 파일 업로드, 폴더 업로드, 새 폴더, 숨김 파일, 새로고침, 다운로드, 삭제 액션이 보이도록 복구했다.
- 공용 파일 트리에 외부 파일/폴더 drag-and-drop 업로드를 추가했다. 트리 배경에 드롭하면 현재 경로로, 폴더 행에 드롭하면 해당 폴더로 업로드된다.
- `/api/file-tree`에 `download` 액션을 추가하고 서비스/컨테이너 파일 다운로드를 base64 payload 기반으로 처리하도록 보강했다.
- 컨테이너 파일 목록 스크립트의 `set -f`로 인해 glob이 펼쳐지지 않던 문제를 수정했다.
- 컨테이너 `/` 스캔 시 `//bin`처럼 표시되던 이중 slash 경로를 `/bin` 형태로 정규화했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- Playwright로 `https://infra-dev.nanoha.kr/access` 로그인 후 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣고 서비스 상세 화면을 확인했다.
- Compose/Nginx 탭에서 서비스 디렉터리 영역에 파일 업로드, 폴더 업로드, 새 폴더, 다운로드, 삭제 UI가 노출되는 것을 확인했다.
- 서비스 디렉터리에 임시 파일 `reviewops-service-tree-upload.txt`를 업로드해 목록에 나타나는 것을 확인했고, `/api/file-tree` delete로 즉시 삭제했다.
- 서비스 디렉터리에 임시 파일 `reviewops-service-tree-download-2.txt`를 업로드한 뒤 `/api/file-tree` download 액션으로 받은 base64 payload가 원본 내용과 일치하는 것을 확인했고, 즉시 삭제했다.
- 컨테이너 파일 탭의 `/` 경로에서 `bin`, `dev`, `etc`, `proc`, `usr`, `var`, `workspace` 항목이 표시되는 것을 확인했다.
- 컨테이너 파일 경로 표시가 `//bin`이 아닌 `/bin` 형태로 표시되는 것을 확인했다.

## 남은 리스크

- 브라우저 자동화에서 실제 OS drag-and-drop 이벤트로 폴더를 드롭하는 동작까지는 수행하지 않았다. 동일한 업로드 처리 경로를 쓰는 파일 입력 업로드와 삭제는 확인했다.
