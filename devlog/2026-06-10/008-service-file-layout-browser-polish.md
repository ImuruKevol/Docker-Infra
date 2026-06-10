# 서비스 파일/컨테이너 파일 탭 브라우저 검증 기반 레이아웃 보정

- 날짜: 2026-06-10
- 리뷰 ID: qklfbvdopgfyvgupflfuolyislfknevd
- 요청자: 권태욱

## 사용자 원문

브라우저에서 직접 확인하고 디자인 및 레이아웃을 확실하게 수정해줘. 지금은 그냥 단순하게 합쳐놔서 정말 개판 그자체야.

## 변경 파일

- `src/app/component.file.tree/app.json`
- `src/app/component.file.tree/view.html`
- `src/app/component.file.tree/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `devlog.md`
- `devlog/2026-06-10/008-service-file-layout-browser-polish.md`

## 작업 내용

- 공용 파일 트리에 `density="compact"` 표시 모드를 추가해 좁은 사이드바에서 전체 업로드/생성 툴바와 긴 경로 메타가 노출되지 않도록 정리했다.
- Compose/Nginx 탭을 왼쪽 파일 탐색/관리 설정, 오른쪽 Monaco 에디터의 고정 2열 작업공간으로 재구성했다.
- Compose/Nginx 탭의 본문 텍스트에서 긴 `/root/docker-infra/...` 절대 경로를 제거하고 파일명 또는 짧은 상대 경로만 표시하도록 변경했다.
- 컨테이너 파일 탭은 컨테이너 선택 패널과 파일 조작 패널을 분리하고, 업로드/새 폴더/숨김 파일/경로 이동 조작은 컨테이너 내부 파일 영역에 유지했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- Playwright로 `https://infra-dev.nanoha.kr/access` 로그인 후 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣고 `https://infra-dev.nanoha.kr/services/51137111-cbff-4480-aba6-8815c39b5cdc`에서 확인했다.
- Compose/Nginx 탭에서 서비스 디렉터리 compact 파일 트리와 에디터가 1440x900 화면에 2열로 표시되는 것을 확인했다.
- Compose/Nginx 탭 본문에서 `/root/docker-infra/project/main/.runtime/dev/templates` 절대 경로가 노출되지 않고, Source 탭 업로드 툴바가 사라진 것을 확인했다.
- 컨테이너 파일 탭에서 `app`, `db` 컨테이너 선택 목록과 파일 업로드/폴더 업로드/새 폴더/숨김 파일/새로고침 조작이 유지되는 것을 확인했다.

## 남은 리스크

- 확인 대상 컨테이너의 `/` 목록은 비어 있어 컨테이너 내부의 깊은 경로 탐색과 업로드 성공까지는 이번 브라우저 검증에서 실행하지 않았다.
