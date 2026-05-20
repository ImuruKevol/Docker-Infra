# 대시보드 서비스 목록 카드와 실행 경고 표시 추가

- **ID**: 272
- **날짜**: 2026-05-20
- **유형**: 기능 추가

## 작업 요약
대시보드의 Servers 카드와 등록된 도메인 카드 사이에 서비스 목록 카드를 추가했다.
서버와 서비스 목록에는 컨테이너/작업 실행 수가 기대 수보다 적거나 오류 상태일 때 확인 필요 경고 뱃지를 표시하도록 했다.

## 원문 요청사항
```text
작업 진행해줘.

대시보드에 Servers, 등록된 도메인 카드 사이에 서비스 목록 카드 추가 필요.
Servers와 서비스 목록에는 간단한 경고 기능 추가 필요. 예를 들어 해당 서버에 컨테이너가 총 7개가 동작 중인데, 그 중에 4개만 실행 중이며 3개는 중지 상태이다 하면 확인 필요 경고 아이콘을 표시한다던지 등. 서비스에도 비슷한 느낌으로 추가 필요.
```

## 변경 파일 목록
- `src/app/page.dashboard/api.py`: 대시보드 서비스 카드용 `services` API 함수 추가.
- `src/app/page.dashboard/view.ts`: 서비스 카드 로딩, 서비스/서버 경고 계산, 런타임 요약 표시 helper 추가.
- `src/app/page.dashboard/view.pug`: Servers와 등록된 도메인 카드 사이에 서비스 목록 카드 추가, 서버/서비스 경고 뱃지 표시.
- `src/model/struct/infra_catalog_registry.py`: 대시보드용 서비스 목록과 runtime summary, warning summary 조회 추가.
- `devlog.md`, `devlog/2026-05-20/272-dashboard-service-alert-card.md`: 작업 이력 기록.

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/model/struct/infra_catalog_registry.py project/main/src/app/page.dashboard/api.py` 성공.
- WIZ clean build 성공 (`wiz_project_build`, `clean=true`).
- 최종 WIZ normal build 성공 (`wiz_project_build`, `clean=false`).
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 포함해 `/wiz/api/page.dashboard/services` 호출 시 HTTP 200 JSON 응답 확인. 인증 세션이 없어 payload code는 401로 반환됨.
