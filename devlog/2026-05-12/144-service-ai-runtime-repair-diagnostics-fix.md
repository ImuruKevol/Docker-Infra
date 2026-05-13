# 144. 서비스 AI 런타임 검사/수정 진단 조건 불일치 수정

- 날짜: 2026-05-12
- 리뷰 ID: zjcknbgqlnbbrsgddfrzcrdgivrbcbyq

## 원 요청

버그를 수정해줘

## 변경 파일

- `src/model/struct/ai_assistant.py`
  - UI의 `AI 검사/수정` 버튼 활성화 조건과 백엔드 `repair_runtime` 진단 조건을 맞췄다.
  - 서비스 실패/취소 상태, 최근 실패 작업, stack desired/running 불일치, task error, stopped/unhealthy/unknown 컨테이너를 `signals`로 수집해 AI 복구 흐름이 건너뛰지 않도록 했다.
- `src/app/page.services/api.py`
  - AI 런타임 복구 중 `ServiceError`가 발생하면 실제 `error_code`와 `extra` 정보를 응답에 보존하도록 했다.
- `tests/api/test_services_preflight.py`
  - 런타임 복구 진단 신호가 정적 계약에 포함되도록 보강했다.
- `devlog.md`
- `devlog/2026-05-12/144-service-ai-runtime-repair-diagnostics-fix.md`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tools/docker_infra_mcp.py src/app/page.services/api.py tests/api/test_services_preflight.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 11개 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 운영 AI 모델 호출과 실제 장애 서비스 자동 복구는 토큰/대상 장애 서비스 없이 수행하지 않았다.
