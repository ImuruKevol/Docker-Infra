# 서비스 상세 탭 API 분리와 지연 로딩 적용

- **ID**: 183
- **날짜**: 2026-05-13
- **유형**: 성능 개선

## 작업 요약
서비스 관리 화면의 상세 초기 호출이 모든 탭 데이터를 함께 가져오던 구조를 overview/logs/backups/advanced 단위로 분리했다.
초기 선택 시에는 구성도와 상태 요약에 필요한 데이터만 받고, 로그/백업/고급 탭은 진입 시 별도 API로 지연 로딩하도록 변경했다.

## 원문 요청사항
```text
작업 시작해줘.

서비스 관리 화면에서 상세 화면의 모든 탭 정보를 한 API로 불러오고 있는데, 적절히 나누어서 초기 로딩 속도를 빠르게 해줘.
```

## 변경 파일 목록
- `src/model/struct/services_runtime.py`
  - 서비스 상세 조회를 overview/logs/backups/advanced 섹션 메서드로 분리
  - 초기 overview에서는 최근 작업 5건을 output 없이 조회하고, 백업/버전/nginx 원문은 제외
- `src/app/page.services/api.py`
  - `detail_service`를 overview 전용 응답으로 경량화
  - `detail_service_logs`, `detail_service_backups`, `detail_service_advanced` API 추가
  - 섹션 로딩 상태 추적용 `detail_sections` 플래그 추가
- `src/app/page.services/view.ts`
  - 탭 진입 시 필요한 섹션 API를 지연 호출하도록 변경
  - 부분 응답을 기존 상세 상태에 병합해 이미 로드한 섹션을 보존
  - 수정 모달과 AI 런타임 검사 전 필요한 상세 섹션을 보강 로딩
- `src/app/page.services/view.pug`
  - 탭 섹션 로딩 표시 추가
  - 로그/백업/고급 탭은 로딩 완료 후 본문을 렌더링하도록 조정

## 확인한 내용
- `python3 -m py_compile project/main/src/app/page.services/api.py project/main/src/model/struct/services_runtime.py` 통과
- 새 API 함수가 추가되어 `wiz_project_build(clean=true)` 수행, 빌드 성공

## 남은 리스크
- 실제 운영 데이터에서 탭별 응답 시간이 얼마나 줄었는지는 브라우저 네트워크 패널 또는 APM으로 확인이 필요하다.
