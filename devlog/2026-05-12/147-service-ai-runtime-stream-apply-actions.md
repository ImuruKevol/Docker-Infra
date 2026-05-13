# 147. 서비스 AI 수정 코멘트와 런타임 스트리밍 적용/컨테이너 조치 실행 보강

- 날짜: 2026-05-12
- 리뷰 ID: zjcknbgqlnbbrsgddfrzcrdgivrbcbyq

## 원 요청

오른쪽 위 헤더 부분 수정 버튼을 눌러서 뜨는 서비스 수정 쪽에도 추가 코멘트를 작성할 수 있어야 해.
그리고 AI 검사 및 수정 실행 시 실제 설정 수정 및 반영은 안하는 것 같아. 컨테이너 중지/삭제 등 동작도 실제로 안하는 것 같고.
그리고 검사 및 수정 중에 AI의 생각 과정을 보여줘야해. 중간에 에러도 뜨고 있고.

## 변경 파일

- `src/app/page.services/api.py`
  - 런타임 AI 검사/수정 스트리밍 엔드포인트 `stream_runtime_ai_repair`를 추가했다.
- `src/app/page.services/view.ts`
  - 서비스 수정 모달의 추가 코멘트 상태를 추가하고 저장/AI 요청 payload에 포함했다.
  - 런타임 AI 검사/수정 스트림을 새 엔드포인트로 호출하고 판단 요약 라벨을 표시하도록 정리했다.
- `src/app/page.services/view.pug`
  - 서비스 수정 기본 정보 섹션에 추가 코멘트 textarea를 추가했다.
  - 런타임 AI 진행 영역을 AI 진행 및 판단 요약으로 표시하도록 변경했다.
- `src/model/struct/ai_assistant.py`
  - 스트리밍 런타임 수정 플로우가 AI 응답 검증, 설정 저장, 재배포 요청까지 수행하도록 추가했다.
  - AI가 반환한 `runtime_actions`를 허용된 문제 컨테이너 범위에서 검증한 뒤 stop/restart/remove 터미널 명령으로 실행하도록 보강했다.
  - 서비스 수정 AI 컨텍스트에 `operator_comment`를 포함했다.
- `src/model/struct/services_update.py`
  - 서비스 수정 추가 코멘트를 서비스 metadata에 저장/삭제하도록 반영했다.
- `tests/api/test_services_preflight.py`
  - 스트리밍 런타임 수정, 추가 코멘트, 컨테이너 조치 실행 계약 토큰을 정적 테스트에 추가했다.
- `devlog.md`
- `devlog/2026-05-12/147-service-ai-runtime-stream-apply-actions.md`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py tools/docker_infra_mcp.py src/app/page.services/api.py src/model/struct/services_update.py tests/api/test_services_preflight.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 11개 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 운영 AI 모델 호출과 실제 컨테이너 stop/remove는 대상 장애 서비스에서 수행하지 않았다.
