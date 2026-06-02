# AI Agent 도킹 중 서버 화면 레이아웃과 상세 탭 라우팅 재사용 개선

- **ID**: 011
- **날짜**: 2026-06-01
- **유형**: 버그 수정

## 작업 요약

AI Agent 도킹 패널이 열린 상태에서 서버 관리 화면의 좌우 상세 그리드가 viewport 기준 `xl` breakpoint에 고정되어 좁은 콘텐츠 영역에서도 2단으로 남던 문제를 컨테이너 폭 기준 레이아웃으로 바꿨다.
상세 alias 라우트를 동일 child route matcher에서 함께 처리하고 주요 상세 화면에 `NavigationEnd` 구독을 추가해 서비스/서버/작업 로그/시스템 설정 탭 이동 시 컴포넌트 전체 재생성을 피하도록 했다.

## 원문 요청사항

```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: odfnkzqhonscokpkkqpgvdkanhkfvvck
- 제목: 레이아웃 버그 수정 및 상세 탭 이동 동작 최적화
- 요청 링크: https://infra-dev.nanoha.kr/dashboard
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

- 리뷰 ID: odfnkzqhonscokpkkqpgvdkanhkfvvck
- 제목: 레이아웃 버그 수정 및 상세 탭 이동 동작 최적화
- 상태: open
- 우선순위: normal
- 분류: performance
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/dashboard
- 화면: 1440x900
- 캡처 방식: reviewops-sdk-screenshot-unavailable
- 스크린샷 첨부: no
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

- AI Agent 사이드바가 열려있는 상태에서 서버 관리 화면의 레이아웃이 깨지고 있음. 수정 필요.
- 현재 서비스 관리, 서버 관리, 작업 로그, 시스템 설정 화면들에서 각각의 탭 이동 시 화면 전체가 다시 불러와지고 있는 최적화 쪽의 문제가 있음. 개선 필요.

## 첨부 파일

-

## 콘솔 로그 요약

-

## 네트워크 로그 요약

- GET https://infra-dev.nanoha.kr/wiz/api/page.dashboard/resources 200
- GET https://infra-dev.nanoha.kr/api/ai-agent/status 200
- GET https://infra-dev.nanoha.kr/api/ai-agent/status 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/dashboard 200
- GET https://infra-dev.nanoha.kr/dashboard 200
- GET https://infra-dev.nanoha.kr/dashboard 200
- GET https://infra-dev.nanoha.kr/dashboard 200
- GET https://infra-dev.nanoha.kr/dashboard 200
- GET https://infra-dev.nanoha.kr/dashboard 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 0
- GET https://infra-dev.nanoha.kr/dashboard 200
- GET https://infra-dev.nanoha.kr/dashboard 200
- GET https://infra-dev.nanoha.kr/dashboard 200
- GET https://infra-dev.nanoha.kr/dashboard 200
- GET https://infra-dev.nanoha.kr/dashboard 200

## 환경 로그 요약

- reviewops-sdk: SDK 0.1.9 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.9 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.9
- iframe-fingerprint: restricted / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.9
- iframe-fingerprint: restricted / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.9 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.9 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.9 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.9
```

## 변경 파일 목록

- `src/angular/app/app-routing.module.ts`
  - 상세 alias를 별도 child route로 추가하지 않고 기본 path와 같은 matcher에서 순회하도록 변경해 alias 간 이동 시 Angular 컴포넌트 재생성을 줄였다.
  - `/services/create`처럼 다른 child의 기본 경로가 alias보다 우선되어야 하는 경우를 보존하도록 alias 매칭 전에 구체 경로 충돌을 검사했다.
- `src/app/page.services/view.ts`
  - `NavigationEnd` 구독으로 URL 상세 탭/선택 서비스 변경을 현재 컴포넌트 안에서 반영하도록 했다.
- `src/app/page.servers/view.ts`
  - `NavigationEnd` 구독으로 URL 상세 탭/선택 서버 변경을 현재 컴포넌트 안에서 반영하도록 했다.
- `src/app/page.operations/view.ts`
  - `NavigationEnd` 구독으로 작업 상세 URL 열기/닫기를 현재 컴포넌트 안에서 반영하도록 했다.
- `src/app/page.system/view.ts`
  - `NavigationEnd` 구독으로 시스템 설정 상위 탭과 AI 하위 탭 URL 변경을 현재 컴포넌트 안에서 반영하도록 했다.
- `src/app/page.servers/view.pug`
  - 서버 관리 상세 레이아웃 wrapper를 컨테이너 기반 class로 교체하고 좁은 폭에서 자식 영역이 줄어들 수 있도록 `min-w-0`을 추가했다.
- `src/app/page.servers/view.scss`
  - 서버 화면 전용 container query를 추가해 AI Agent 도킹으로 콘텐츠 영역이 좁아지면 1단으로 접히도록 했다.
- `tests/api/test_wiz_structure_contract.py`
  - alias route matcher 재사용, 주요 화면 `NavigationEnd` 구독, 서버 화면 container query 계약을 추가했다.
- `devlog.md`, `devlog/2026-06-01/011-layout-route-reuse.md`
  - 작업 이력을 기록했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_wiz_structure_contract.WizStructureContractTest.test_frontend_detail_routes_are_explicit tests.api.test_wiz_structure_contract.WizStructureContractTest.test_servers_layout_uses_container_width_for_agent_dock` 성공.
- `git diff --check -- src/angular/app/app-routing.module.ts src/app/page.services/view.ts src/app/page.servers/view.ts src/app/page.operations/view.ts src/app/page.system/view.ts src/app/page.servers/view.pug src/app/page.servers/view.scss tests/api/test_wiz_structure_contract.py` 성공.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 다음 URL HTTP 200 확인:
  - `https://infra-dev.nanoha.kr/services/create`
  - `https://infra-dev.nanoha.kr/services/test-service/logs`
  - `https://infra-dev.nanoha.kr/servers/test-node/terminal`
  - `https://infra-dev.nanoha.kr/operations/test-operation`
  - `https://infra-dev.nanoha.kr/system/ai/hermes`

## 남은 리스크

- 인증된 실제 데이터 세션에서 AI Agent 패널을 열고 탭을 직접 클릭하는 브라우저 시각 검증은 수행하지 못했다.
