# 시스템 설정 load API 1초 미만 응답으로 경량화

- 날짜: 2026-06-09
- ID: 008
- 리뷰 ID: hfpghzwqjqivdepiamtcifekwsgcunwt

## 사용자 요청

일부 화면이 로딩 해제까지 3~6초가 걸린다고 하는데, 이건 있을 수없는 일이야.
무조건 모든 응답은 AI 관련 응답같은 예외를 빼면 일반 API들은 최대 1초를 넘지 말아야 해.

## 변경 파일

- `src/app/page.system/api.py`
- `src/app/page.system/view.ts`
- `src/model/struct/ai_settings.py`
- `devlog.md`
- `devlog/2026-06-09/008-system-load-fast-response.md`

## 작업 내용

- `page.system/load`에서 AI 런타임 상태 확인과 백업 scheduler tick을 제거해 일반 설정 load가 설정값만 빠르게 반환하도록 변경했다.
- `page.system/load`가 현재 탭을 받아 Backup 탭일 때만 백업 상태를 포함하도록 분리했다.
- AI 상태 확인은 화면 로딩 해제 후 `ai_codex_status`/`ai_agent_status`로 별도 비동기 호출되도록 프론트 흐름을 조정했다.
- `ai_settings.public_payload()`와 save 계열에 `include_status` 옵션을 추가해 저장 직후에도 불필요한 런타임 상태 조회를 생략할 수 있게 했다.

## 확인 결과

- `wiz_project_build(projectName="main", clean=false)` 성공.
- 수정 전 `page.system/load`는 3회 측정 기준 약 2636-2743ms였다.
- 수정 후 직접 측정 결과:
  - `system.load.general`: 평균 95ms, 최대 99ms
  - `system.load.ai`: 평균 107ms, 최대 151ms
  - `system.load.backup`: 평균 131ms, 최대 166ms
  - `domains.load`: 평균 162ms, 최대 349ms
- 주요 화면 일반 load API 단건 측정에서 `/services`, `/services/create`, `/servers`, `/templates`, `/macros`, `/operations`, `/domains`, `/images`, `/system` 모두 1초 미만 확인.
- `/system/ai/codex` 실제 화면 기준 로딩 문구가 536ms에 해제되고, `page.system/load` 응답은 282ms로 확인했다.

## 남은 리스크

- AI 상태 조회 API는 사용자 요청 기준 예외 범위로 분리했으며, 네트워크/CLI 상태에 따라 별도 시간이 걸릴 수 있다.
- 백업 탭의 `backup_system.status()`는 현재 166ms 이하였지만, 백업 저장소가 느린 외부 mount로 바뀌면 별도 캐시 전략이 필요할 수 있다.
