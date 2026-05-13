# 148. AI 런타임 검사 스트림 완료 검증과 강제 AI 분석 실행 보강

- 날짜: 2026-05-12
- 리뷰 ID: zjcknbgqlnbbrsgddfrzcrdgivrbcbyq

## 원 요청

서비스 상세에서 AI검사/수정  모달에서 AI에 요청을 하지 않고 바로 런타임 수정안을 적용하고 재배포를 시작했다고 뜨고 있어. 문제를 확실하게 파악하고 고쳐줘.

## 변경 파일

- `src/app/page.services/view.ts`
  - AI 스트림에서 `done` 이벤트를 받지 못하면 성공 처리하지 않고 오류로 중단하도록 변경했다.
  - 런타임 AI 검사/수정 모달 실행 시 `force: true`를 보내 사용자가 실행한 검사/수정은 백엔드 AI 분석 경로를 반드시 타도록 했다.
  - 스트림 결과가 없거나 `result`가 없으면 기본 성공 문구를 띄우지 않고 오류로 처리한다.
  - `result.applied`가 true인 경우에만 "적용/재배포 시작" 성공 문구를 띄우고, 적용되지 않은 결과는 warning 문구로 분리했다.
- `tests/api/test_services_preflight.py`
  - 런타임 AI 실행이 `force: true`와 스트림 완료 이벤트 검증을 포함하는지 정적 계약을 추가했다.
- `devlog.md`
- `devlog/2026-05-12/148-service-ai-runtime-stream-completion-guard.md`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tools/docker_infra_mcp.py src/app/page.services/api.py src/model/struct/services_update.py tests/api/test_services_preflight.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 11개 통과
- `git diff --check -- src/app/page.services/view.ts tests/api/test_services_preflight.py`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 운영 AI 모델 호출은 수행하지 않았다.
