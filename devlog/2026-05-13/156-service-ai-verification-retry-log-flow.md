# AI 검증 로그 압축과 실패 후 재시도 플로우 보강

- 날짜: 2026-05-13
- 리뷰 ID: eagmfkotirfxmsmreeesotzsltdqnohi
- 요청: AI 백그라운드 검증 로그가 초반에 같은 runtime wait를 반복 출력하고, 재배포 실패 후 정해진 횟수만큼 재시도하지 않고 멈추는 문제를 확인해달라는 요청이었다. 실제 화면 확인을 위해 관리자 비밀번호가 제공되었지만 devlog에는 기록하지 않는다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `tests/api/test_services_preflight.py`
- `docs/service-ai-codex-agent-design.md`
- `devlog.md`
- `devlog/2026-05-13/156-service-ai-verification-retry-log-flow.md`

## 작업 내용

- runtime wait 단계에서 동일한 stack/container/domain snapshot이 반복될 때 매번 로그를 쓰지 않고 생략 횟수만 기록하도록 변경했다.
- 같은 실패 상태가 일정 횟수 유지되면 전체 대기 시간을 끝까지 소비하지 않고 AI 분석 단계로 넘어가도록 했다.
- AI 검증 호출 실패, AI 수정 호출 실패, 재배포 실패가 발생해도 최대 검증 시도 횟수 전에는 다음 시도로 계속 이어가도록 했다.
- 재배포 실패가 최종 시도까지 반복될 때만 최종 실패로 operation을 종료하도록 정리했다.
- 정적 계약 테스트와 설계 문서에 로그 압축 및 재시도 흐름을 반영했다.

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/tests/api/test_services_preflight.py` 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest project/main/tests/api/test_services_preflight.py` 통과, 11개 테스트
- Playwright로 `https://infra-dev.nanoha.kr`에 접속해 로그인, `/services`, `/services/create` 화면 접근 확인
- Playwright API 확인 결과 서비스 2개가 조회되었고, 기존 `bbb` 서비스에는 실패한 `service.ai.verify` 이력이 남아 있음을 확인
- WIZ project build 통과

## 남은 리스크

- 이번 확인은 기존 실패 이력과 화면/API 접근 확인 기준이다. 수정된 재시도 루프가 실제 AI provider 호출과 재배포까지 성공하는지는 새 수동 AI 검사 실행으로 별도 확인이 필요하다.
- 기존에 남아 있는 실패 operation은 이 변경으로 자동 정리하지 않는다.
