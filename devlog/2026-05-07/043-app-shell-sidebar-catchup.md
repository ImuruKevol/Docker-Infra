# 운영 콘솔 앱 셸 브랜딩/사이드바 정리와 누락 devlog 보강

- 날짜: 2026-05-07
- ID: 043

## 사용자 요청

- 쌓여있는 변경사항들을 요약해서 커밋 메세지를 작성하고 커밋해달라는 의미였어.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-07/043-app-shell-sidebar-catchup.md`
- `src/angular/index.pug`
- `src/app/component.nav.sidebar/view.pug`

## 작업 내용

- 현재 워크트리에 남아 있던 운영 콘솔 앱 셸 관련 변경을 점검하고, 누락된 devlog를 catch-up 형식으로 보강했다.
- `src/angular/index.pug`에서 문서 title을 `Docker Infra` 기준으로 맞추고, manifest link 상태와 ReviewOps SDK bootstrap script 구성을 현재 앱 셸 기준으로 정리했다.
- `src/app/component.nav.sidebar/view.pug`에서는 좌측 사이드바 상단의 중복 Access 요약 카드를 제거해 운영자 메뉴 집중도를 높였다.
- 이 변경들은 이전 작업 흐름에서 소스만 남고 devlog가 직접 연결되지 않아, 이번 커밋 전에 별도 기록으로 정리했다.

## 검증

- `cd /root/docker-infra/project/main && git diff --check -- src/angular/index.pug src/app/component.nav.sidebar/view.pug devlog.md devlog/2026-05-07/043-app-shell-sidebar-catchup.md`: 통과
- 최종 커밋 전 `git diff --stat`, `git status --short`로 누적 변경 범위 확인
