# AI Agent Enter 요청 전송 비활성화

- **ID**: 001
- **날짜**: 2026-06-17
- **유형**: 버그 수정

## 작업 요약
AI Agent 메시지 입력창에서 Enter 키를 눌렀을 때 즉시 요청이 전송되는 동작을 제거했다.
요청 전송은 입력창 옆 요청하기 버튼 클릭으로만 실행되도록 compose form의 submit 바인딩과 textarea Enter 핸들러를 분리했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: hlsqdttkoenpaeicdqzupzbvqhftqalj
- 제목: agent UX 수정
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 신규
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 포함됨
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 에이전트 작업 지시서

# 에이전트 작업 지시서

## 리뷰 정보

- 리뷰 ID: hlsqdttkoenpaeicdqzupzbvqhftqalj
- 제목: agent UX 수정
- 상태: open
- 우선순위: normal
- 분류: ux
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/access
- 화면: 1440x900
- 캡처 방식: reviewops-sdk-dom-snapshot
- 스크린샷 첨부: no
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

현재 AI Agent에서 메시지 입력 시 엔터를 누르면 바로 요청이 가는데, 그 동작을 제거해줘. 너무 오동작이 많아. 무조건 사용자가 요청하기 버튼을 눌러야 요청이 가도록 수정해줘.

## 첨부 파일

-

## 콘솔 로그 요약

-

## 네트워크 로그 요약

- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Medium.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Thin.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-SemiBold.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Regular.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-ExtraBold.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Bold.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Light.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Thin.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Heavy.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Regular.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-ExtraBold.woff2 200
- GET https://infra-dev.nanoha.kr/media/fa-solid-900.ttf 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Heavy.woff2 200
- GET https://infra-dev.nanoha.kr/media/fa-solid-900.woff2 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/media/fa-solid-900.woff2 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/assets/bg-login.optimized.webp 200
- GET https://infra-dev.nanoha.kr/assets/bg-login.optimized.webp 200

## 환경 로그 요약

- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- iframe-fingerprint: restricted / https://infra-dev.nanoha.kr
- browser-fingerprint: MacIntel / ko-KR / 2560x1440
- iframe-fingerprint: restricted / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
```

## 변경 파일 목록
- `src/angular/app/app.component.pug`: AI Agent compose form의 `(ngSubmit)` 제거, textarea `(keydown.enter)` 제거, 요청 버튼을 `type="button"` + `(click)="sendAgentMessage()"`로 변경.
- `src/angular/app/app.component.ts`: 더 이상 사용하지 않는 `handleAgentEnter()` 제거.
- `devlog.md`: 작업 요약 행 추가.
- `devlog/2026-06-17/001-ai-agent-enter-submit-disable.md`: 작업 상세 기록 추가.

## 검증 결과
- `wiz_project_build(clean=false)` 성공.
- `rg`로 `handleAgentEnter`, Agent 입력창의 Enter 제출 바인딩, Agent 요청 버튼 submit 타입이 남아 있지 않음을 확인.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `https://infra-dev.nanoha.kr/access` 요청 결과 HTTP 200 확인.

## 남은 리스크
- 실제 로그인 세션 기반 브라우저 상호작용으로 Agent 패널에서 Enter 입력과 버튼 클릭을 직접 재현하지는 못했다.
