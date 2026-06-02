# AI Agent 채팅 응답 Markdown 렌더링 적용

- **ID**: 018
- **날짜**: 2026-05-29
- **유형**: 버그 수정

## 작업 요약
AI Agent 채팅 메시지를 단순 텍스트 출력에서 기본 Markdown 렌더링으로 변경했다.
응답 본문은 HTML 이스케이프 후 문단, 번호/불릿 목록, 굵게/기울임, 링크, 인라인 코드, 코드 블록, 간단한 제목을 HTML로 변환해 표시한다.

## 원문 요청사항
```text
결과가 아래와 같이 나왔는데, 기본적으로 마크다운 문법 형태로 나오는 것으로 보여. 채팅창 응답으로 보여줄 때 기본적인 마크다운 문법은 적용을 해서 보여주어야 해.

---
AI Agent
현재 local-master 서버에서 식별된 미사용(Unused) 이미지 중 정리 가능한 대상 목록입니다. 특히 대용량 이미지 위주로 정리하시면 많은 디스크 공간을 확보할 수 있습니다:

1. **registry.nanoha.kr/kwon3286/docker-infra:dev** (24.5 GB) - 미사용 상태이며 가장 많은 용량을 차지하고 있습니다.
2. **registry.nanoha.kr/kwon3286/wiz-base:2.5.1** (5.49 GB) - 미사용
3. **requarks/wiki:2** (1 GB) - 미사용
4. **127.0.0.1:5000/keycloak_ee269a/keycloak:latest-20260519013544** (749 MB) - 미사용
5. **quay.io/keycloak/keycloak:latest** (749 MB) - 미사용
6. **mariadb:12.2** (468 MB) - 미사용
7. **127.0.0.1:5000/reviewops-snap-local-master-20260514163704/snapshot-web:20260514073729** (6.76 MB) - 미사용

이 이미지들은 현재 실행 중이거나 연결된 컨테이너가 없는 상태이므로 안심하고 삭제하셔도 무방합니다.
```

## 변경 파일 목록
- `src/angular/app/app.component.pug`: 채팅 메시지 본문을 `innerHTML` 기반 Markdown 렌더링 영역으로 변경.
- `src/angular/app/app.component.ts`: 안전한 기본 Markdown 변환 헬퍼 추가.
- `src/angular/app/app.component.scss`: Markdown 문단, 목록, 링크, 코드, 제목 스타일과 다크 모드 스타일 추가.
- `devlog.md`, `devlog/2026-05-29/018-ai-agent-markdown-rendering.md`: 작업 이력 기록.

## 검증 결과
- `wiz_project_build(clean=false)` 성공.
- 실제 브라우저에서 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `/images/local` 화면 접속 후 AI Agent 응답 확인.
- 브라우저 DOM 기준 `strong` 2개, `ol li` 2개가 렌더링되고 `**` 마크다운 원문은 노출되지 않음을 확인.
