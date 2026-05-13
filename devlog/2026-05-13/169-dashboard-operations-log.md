# 대시보드 카드 정리와 작업 로그 조회 화면 추가

- **ID**: 169
- **날짜**: 2026-05-13
- **유형**: 기능 추가

## 작업 요약
대시보드 상단 통계 카드와 Runtime/Integrations 카드를 제거하고, 서비스 백업 사용 여부를 헤더 뱃지로 이동했습니다.
도메인별 연결 서비스 수 카드와 상세 최근 작업 표시를 추가했으며, 사이드바에서 접근 가능한 작업 로그 조회 페이지를 신설했습니다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 진행해줘.

## 리뷰 요약

- 리뷰 ID: mjucofxibwalmvyfznorgbvegljbycmd
- 제목: 대시보드 수정
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

- 리뷰 ID: mjucofxibwalmvyfznorgbvegljbycmd
- 제목: 대시보드 수정
- 상태: open
- 우선순위: normal
- 분류: ux
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/dashboard
- 화면: 1440x900
- 캡처 방식: reviewops-sdk-screenshot-unavailable
- 스크린샷 첨부: yes
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

맨 상단 카드 4개 삭제해줘. 그리고 Runtime, Integrations 카드 삭제해줘. 대신 서비스 백업 시스템  사용 여부는 헤더 부분 OK 뱃지 왼쪽에 간단하게 뱃지 형태로 표시해줘.
사용 중인 도메인 목록과 각 도메인별 연결된 서비스 갯수를 표시하는 카드를 추가해줘.
최근 작업 카드는 정보를 조금 더 상세하게 표시해줘. 어떤 서버에서 작업을 실행했고, 작업 내용이 뭐였는지 등등. 그리고 이 최근 작업 로그에 대해서는 별도로 왼쪽에 메뉴를 추가해서 로그를 조회할 수 있어야 해. 현재는 볼 수 있는 방법이 없어.
```

## 변경 파일 목록
- `src/app/page.dashboard/view.pug`: 상단 4개 통계 카드와 Runtime/Integrations 카드 제거, 백업 상태 뱃지와 도메인 사용 현황 카드, 상세 최근 작업 카드 추가.
- `src/app/page.dashboard/view.ts`: 백업 상태, 도메인 사용 현황, 작업 로그 표시용 helper 추가.
- `src/model/struct/infra_catalog_registry.py`: 대시보드용 백업 상태/도메인 사용 현황/정규화된 작업 로그 데이터 제공 로직 추가.
- `src/app/component.nav.sidebar/view.ts`: `/operations` 작업 로그 메뉴 추가.
- `src/app/page.operations/app.json`: 작업 로그 페이지 라우트 설정 추가.
- `src/app/page.operations/api.py`: 작업 로그 목록/상세 조회 API 추가.
- `src/app/page.operations/view.pug`: 작업 로그 목록, 필터, 상세 로그 모달 UI 추가.
- `src/app/page.operations/view.ts`: 작업 로그 조회, 상태 필터, 상세 모달 및 실행 중 자동 갱신 로직 추가.
- `devlog.md`, `devlog/2026-05-13/169-dashboard-operations-log.md`: 작업 이력 기록.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/infra_catalog_registry.py src/app/page.operations/api.py src/app/page.dashboard/api.py` 성공.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_node_reporter.NodeReporterStaticContractTest` 성공.

## 남은 리스크
- 실제 운영 데이터로 `/dashboard` 및 `/operations` 화면을 브라우저에서 직접 클릭 검증하지는 못했습니다.
- 작업 로그의 서버 표시는 기존 operation metadata/output에 서버 정보가 기록된 경우 우선적으로 표시되며, 과거 로그 중 관련 정보가 없는 항목은 `서버 미기록`으로 보일 수 있습니다.
