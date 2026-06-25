# Storage 메뉴와 읽기 전용 개요 페이지 추가

- **ID**: 001
- **날짜**: 2026-06-24
- **유형**: 기능 추가

## 작업 요약
Docker Infra 사이드바 고급 메뉴에 `스토리지` 항목을 추가하고 `/storage` 페이지를 신규 생성했다.
초기 범위는 읽기 전용 개요로 제한했으며, Ceph cluster 미구성 상태, health placeholder, raw/usable/recommended 용량, daemon 개수, warning 목록을 page API에서 반환하도록 구성했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: uypgjyaxamdklizmexfvwraqxzxdvcth
- 제목: Storage 메뉴와 읽기 전용 개요 페이지 추가
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

- 리뷰 ID: uypgjyaxamdklizmexfvwraqxzxdvcth
- 제목: Storage 메뉴와 읽기 전용 개요 페이지 추가
- 상태: open
- 우선순위: high
- 분류: design
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/access
- 화면: 1440x900
- 캡처 방식: reviewops-sdk-dom-snapshot
- 스크린샷 첨부: no
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

Docker Infra 사이드바에 `스토리지` 메뉴를 추가하고 `/storage` 페이지 골격을 만든다. 초기 범위는 읽기 전용이다. cluster 미구성 상태, health placeholder, raw/usable/recommended 용량, daemon 개수, warning 목록을 표시한다. 새 app은 `src/app/page.storage/*`로 만들고 API는 우선 page `api.py`에서 시작한다. 기존 기능에는 영향이 없어야 한다.

참고:
- `docs/ceph-storage-application-plan.md` §4, §5.1, §14, §23 Phase 1
- `docs/backup-volume-layered-storage-design.md` §5, §13.1, §16

## 첨부 파일

-

## 콘솔 로그 요약

-

## 네트워크 로그 요약

- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-ExtraBold.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Medium.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-ExtraLight.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Heavy.woff2 200
- GET https://infra-dev.nanoha.kr/media/fa-solid-900.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Regular.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Light.woff2 200
- GET https://infra-dev.nanoha.kr/media/fa-regular-400.ttf 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Bold.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Thin.woff2 200
- GET https://infra-dev.nanoha.kr/media/fa-regular-400.ttf 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-ExtraLight.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Regular.woff2 200
- GET https://infra-dev.nanoha.kr/media/fa-solid-900.ttf 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Light.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Thin.woff2 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/assets/bg-login.optimized.webp 200
- GET https://infra-dev.nanoha.kr/assets/bg-login.optimized.webp 200

## 환경 로그 요약

- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10
- iframe-fingerprint: restricted / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- browser-fingerprint: MacIntel / ko-KR / 2560x1440
- iframe-fingerprint: restricted / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.10 / https://infra-dev.nanoha.kr
```

## 변경 파일 목록

### Source App
- `src/app/page.storage/app.json`: `/storage` 라우트, `layout.sidebar`, `user` controller 설정.
- `src/app/page.storage/view.ts`: 읽기 전용 Storage 개요 상태 로딩, 표시 헬퍼, 용량/daemon/warning 표시 로직 추가.
- `src/app/page.storage/view.pug`: Storage 상태, health placeholder, 용량 카드, daemon 요약, warning 목록, 서버 구분 UI 추가.
- `src/app/page.storage/view.scss`: page host 높이 설정 추가.
- `src/app/page.storage/api.py`: `load` page API 추가.

### Model
- `src/model/struct/storage.py`: Storage 개요 skeleton과 cluster 미구성 placeholder payload 추가.
- `src/model/struct/storage_health.py`: health placeholder, warning 계산, overview payload 조립 추가.

### Navigation / i18n
- `src/app/component.nav.sidebar/view.ts`: 고급 메뉴의 서버 아래에 `/storage` 메뉴 추가.
- `src/assets/lang/ko.json`: `nav.storage` 번역 추가.
- `src/assets/lang/en.json`: `nav.storage` 번역 추가.

### Devlog
- `devlog.md`: 작업 요약 행 추가.
- `devlog/2026-06-24/001-storage-readonly-overview.md`: 상세 devlog 추가.

## 확인 결과
- `python3 -m py_compile src/model/struct/storage.py src/model/struct/storage_health.py src/app/page.storage/api.py` 통과.
- `python3 -m json.tool`로 ko/en lang JSON과 `page.storage/app.json` 검증 통과.
- `wiz_project_build(clean=True)` 성공.
- dev 쿠키 `season-wiz-project=main; season-wiz-devmode=true`를 포함해 `https://infra-dev.nanoha.kr/storage` 요청 시 200 HTML 응답 확인.
- 동일 dev 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.storage/load` 요청 시 인증 컨트롤러의 401 JSON 응답 확인.
- 빌드 산출물에서 `page.storage`, `/storage`, `wiz-page-storage`, `page.storage/load` 관련 파일과 라우팅 포함 확인.

## 남은 리스크
- 실제 Ceph cluster/daemon/capacity 조회는 아직 연결하지 않은 placeholder 상태다.
- 인증 세션이 없어 원격 브라우저에서 로그인 후 UI 시각 검증은 수행하지 못했다.
- 빌드 로그에 기존 npm audit 취약점이 표시되었지만 이번 변경 범위와 직접 관련된 의존성 변경은 없다.
