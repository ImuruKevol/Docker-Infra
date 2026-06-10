# 파일 트리 compact 아이콘 모드와 컨테이너 전환 race 보정

- 날짜: 2026-06-10
- 리뷰 ID: qklfbvdopgfyvgupflfuolyislfknevd
- 요청자: 권태욱

## 사용자 원문

compact 모드는 유지를 하되, compact 모드는 버튼들의 텍스트는 숨김처리하고 아이콘만 남기는 느낌으로 해줘. 그 상태로 Compose/Nginx 탭에 적용을 하면 될 것 같아. width는 500px로 유지하고.
그리고 컨테이너 파일 탭에서 파일 목록의 response가 오기 전에 다른 컨테이너를 클릭하는 등 동작을 하면 에러가 나면서 무한루프같은 느낌으로 에러가 발생하고 있어.

## 변경 파일

- `src/app/component.file.tree/view.html`
- `src/app/component.file.tree/view.ts`
- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-06-10/015-file-tree-compact-icons-container-switch-race.md`

## 작업 내용

- 파일 트리 compact 모드에서 업로드, 폴더 업로드, 새 폴더, 숨김 파일, 새로고침 버튼을 아이콘 전용으로 표시하고 텍스트는 `sr-only`로 숨기도록 변경했다.
- compact 모드에서도 다운로드, 이름 변경, 삭제 행 액션을 아이콘 버튼으로 유지했다.
- Compose/Nginx 탭의 서비스 디렉터리 파일 트리에 `density="compact"`를 다시 적용하고 좌측 패널 500px 폭은 유지했다.
- 파일 트리 context 변경 시 `contextKey`를 reload 전에 먼저 갱신하고, 오래된 list 응답은 serial/key 검사로 무시하도록 보강해 컨테이너 빠른 전환 중 stale response가 화면을 덮거나 에러 루프를 만들지 않게 했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- Playwright로 `https://infra-dev.nanoha.kr/access` 로그인 후 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣고 서비스 상세 화면을 확인했다.
- Compose/Nginx 탭에서 서비스 디렉터리 compact 버튼들이 텍스트 없이 아이콘 버튼으로 표시되는 것을 확인했다.
- 컨테이너 파일 탭에서 `app`/`db` 컨테이너를 파일 목록 응답 전후로 반복 전환했을 때 `/api/file-tree` 4xx 응답, page error, console error가 없고 최종 목록이 정상 표시되는 것을 확인했다.

## 남은 리스크

- 실제 사용자 환경의 네트워크 지연이 더 큰 경우까지 장시간 부하 테스트는 수행하지 않았다.
