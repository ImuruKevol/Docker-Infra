# 서비스 생성 배포 시 AI 검증 자동 시작 제거

- 날짜: 2026-05-13
- 리뷰 ID: eagmfkotirfxmsmreeesotzsltdqnohi
- 요청: "서비스를 ai로 생성을 하니까 백그라운드 점검을 하라고 하지도 않았는데 자동으로 시작되고 점검도 제대로 동작하지 않고 있어. 확인해줘."

## 변경 파일

- `src/app/page.services.create/view.ts`
- `src/app/page.services/view.ts`
- `src/model/struct/ai_assistant.py`
- `tests/api/test_services_preflight.py`
- `docs/service-ai-codex-agent-design.md`
- `docs/docker-infra-remaining-todo.md`
- `docs/docker-infra-development-todo.md`
- `devlog.md`
- `devlog/2026-05-13/155-service-ai-verification-explicit-start.md`

## 작업 내용

- 서비스 생성 화면과 서비스 상세 화면의 일반 배포 요청에서 `start_ai_verification: true`를 제거했다.
- 배포 완료 안내 문구에서 AI 검증 자동 시작 표현을 제거했다.
- AI 검증은 사용자가 서비스 상세의 `AI 검사/수정`을 명시적으로 실행할 때만 `service.ai.verify` 백그라운드 operation으로 시작되도록 정리했다.
- AI 검증 결과가 자동 수정이 필요하지 않다고 판단한 경우 수정/재배포 루프로 넘어가지 않고 검증 실패/확인 필요 상태로 종료하도록 보강했다.
- 문서와 정적 계약 테스트를 명시 시작 기준에 맞게 갱신했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest project/main/tests/api/test_services_preflight.py` 통과, 11개 테스트
- `start_ai_verification: true`가 서비스 생성/상세 UI 코드와 문서에 남아 있지 않음을 확인
- WIZ project build 통과

## 남은 리스크

- 기존에 이미 생성된 `service.ai.verify` operation은 이 변경으로 자동 취소하지 않는다. 진행 중인 기존 작업 정리 UI/API가 필요하면 별도 작업이 필요하다.
- 수동 AI 검사 자체의 실제 환경 동작은 AI provider, DNS, 배포 대상 서비스 상태가 연결된 환경에서 추가 확인이 필요하다.
