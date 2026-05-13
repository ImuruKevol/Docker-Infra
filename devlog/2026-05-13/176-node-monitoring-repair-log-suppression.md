# 서버 자원 수집 자동 점검 로그 제거

- **ID**: 176
- **날짜**: 2026-05-13
- **유형**: 버그 수정

## 작업 요약
대시보드 조회 시 백그라운드로 실행되는 서버 자원 수집 systemd timer 점검이 매번 작업 로그를 생성하지 않도록 변경했다.
점검과 누락 시 재구성 결과는 내부 반환값과 마지막 실행 결과로만 유지하고, `/operations`에 불필요한 자동 점검 로그가 추가되지 않게 했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업해줘.

## 리뷰 요약

- 리뷰 ID: vostjwcnykexbvfqigripporrfexyitj
- 제목: 서버 자원 수집 작업 로그
- 요청 링크: https://infra-dev.nanoha.kr/operations
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

- 리뷰 ID: vostjwcnykexbvfqigripporrfexyitj
- 제목: 서버 자원 수집 작업 로그
- 상태: open
- 우선순위: normal
- 분류: ux
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/operations
- 화면: 1440x900
- 캡처 방식: reviewops-sdk-dom-snapshot
- 스크린샷 첨부: yes
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

서버 자원 수집 systemd timer를 점검하고 누락 시 재구성했습니다.
라는 로그가 계속 찍히고 있는데, 이 로그는 굳이 필요 없는 로그인 것으로 보임. 삭제 요망.

## 첨부 파일

-

## 콘솔 로그 요약

-

## 네트워크 로그 요약

- GET https://infra-dev.nanoha.kr/main.js 200
- GET https://infra-dev.nanoha.kr/api/system/appearance 200
- GET https://infra-dev.nanoha.kr/api/system/appearance 200
- GET https://infra-dev.nanoha.kr/assets/lang/en.json 200
- GET https://infra-dev.nanoha.kr/assets/lang/ko.json 200
- GET https://infra-dev.nanoha.kr/assets/lang/en.json 200
- GET https://infra-dev.nanoha.kr/assets/lang/ko.json 200
- POST https://infra-dev.nanoha.kr/auth/check 200
- GET https://infra-dev.nanoha.kr/auth/check 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Bold.woff2 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-SemiBold.woff2 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/assets/font/SUIT/SUIT-Medium.woff2 200
- GET https://infra-dev.nanoha.kr/media/fa-solid-900.woff2 200
- POST https://infra-dev.nanoha.kr/wiz/api/page.operations/load 200
- GET https://infra-dev.nanoha.kr/wiz/api/page.operations/load 200
- POST https://infra-dev.nanoha.kr/wiz/api/page.operations/detail 200
- GET https://infra-dev.nanoha.kr/wiz/api/page.operations/detail 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200
- GET https://infra-dev.nanoha.kr/api/system/assets/logo 200

## 환경 로그 요약

- reviewops-sdk: SDK 0.1.7 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.7 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.7
- iframe-fingerprint: restricted / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.7
- browser-fingerprint: MacIntel / ko-KR / 2560x1440
- iframe-fingerprint: restricted / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.7 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.7 / https://infra-dev.nanoha.kr
- reviewops-sdk: SDK 0.1.7 / https://infra-dev.nanoha.kr
```

## 변경 파일 목록
- `src/model/struct/nodes_monitoring.py`: `ensure_collectors_if_needed()`의 `operations.create()` 호출을 제거해 자동 점검/복구 작업 로그 생성을 중단.
- `tests/api/test_node_reporter.py`: 서버 자원 수집 자동 점검 로그 타입과 문구가 모니터링 모델에 남지 않는지 확인하도록 정적 계약 테스트 갱신.
- `devlog.md`, `devlog/2026-05-13/176-node-monitoring-repair-log-suppression.md`: 작업 이력 기록.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/nodes_monitoring.py` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter` 성공. `Ran 2 tests`, `OK (skipped=1)`.
- `wiz_project_build(projectName="main", clean=false)` 성공.

## 남은 리스크
- 기존 DB에 이미 저장된 동일 작업 로그 행은 삭제하지 않았으므로, 과거 로그를 즉시 숨기려면 별도 정리 작업이 필요하다.
