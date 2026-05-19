# 237. AI 검사 로그 중복 억제와 DDNS 직접 보정 경로 추가

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 일단 AI 검사/수정 동작 요청 후 처리 로그 모달이 자동으로 뜨는데, 백그라운드 실행이 성공했다는 모달도 같이 뜨고 있어. 성공 모달은 굳이 안띄워도 돼.
> 그리고 처리 로그에서 재배포 작업 상태: running 로그가 계속 반복되고 있는데, 같은 로그는 생략해줘.
> 그리고 아직도 Codex 검증 호출이 실패해 등록된 DDNS 서버 정보를 기준으로 자동 수정 단계로 전환합니다. Codex 수정 호출이 실패해 등록된 DDNS 서버와 추천 도메인으로 서비스 도메인을 보정했습니다. DDNS 등록 API 호출을 실행했습니다. 이런 에러 로그가 찍히고 있어. 제대로 좀 분석하고 수정해줘.
> wiki_service 서비스에 "ddns 도메인을 적용해줘" 라는 수정 요청을 했으니, 이런 요청에 대해 직접 성공을 할때까지 수정하고 개선해줘.

## 변경 요약

- 실제 operation metadata를 확인해 Codex 실패 원인이 MCP가 아니라 `Codex ran out of room in the model's context window`였음을 확인했다.
- DDNS 도메인 적용처럼 등록된 DDNS endpoint만 있으면 결정 가능한 요청은 Codex 호출 없이 직접 검증/수정 데이터를 만들어 저장 및 DDNS 등록 API 경로로 이어지게 했다.
- Codex를 쓰는 다른 런타임 검증/수정 경로도 context window 초과를 줄이도록 runtime status, client issues, recent operations, operation output을 compact하게 축약했다.
- AI 검사/수정 시작 후 처리 로그 모달만 열고 별도 성공 alert는 띄우지 않도록 했다.
- 재배포 대기 로그는 같은 status가 반복되면 생략 카운트로 기록하고, 기존 출력도 UI에서 연속 중복 로그를 접어서 표시하도록 했다.
- Docker Swarm의 과거 shutdown 실패 task가 현재 배포 실패로 오인되지 않도록 `task_errors`는 DesiredState가 running인 task 오류만 집계하게 했다.
- DDNS prefix가 `wiki_service_af4f85` 같은 namespace 기반 값으로 만들어졌던 경우 서비스명 기반 `wiki`로 정규화되도록 보강했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `src/model/struct/services_status.py`
- `src/model/struct/domains_ddns.py`
- `src/app/page.services/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-18/237-ai-ddns-direct-repair-and-log-dedupe.md`

## 확인한 내용

- 최신 `service.ai.verify` operation metadata에서 기존 실패 원인이 context window 초과였음을 확인했다.
- 최신 `service.deploy` operation에서 과거 MariaDB shutdown task 오류가 `task_errors`로 집계되어 nginx/SSL 적용이 중단되던 흐름을 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/services_status.py src/model/struct/services_deploy.py src/model/struct/domains_ddns.py src/model/struct/services_update.py src/model/struct/services_wizard.py src/model/struct/codex_runtime.py tools/docker_infra_mcp.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight tests.api.test_domain_management_ui`: 18개 테스트 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `git diff --check`: 통과

## 남은 리스크

- 이미 실행 중이던 백그라운드 operation은 이전 코드로 시작된 작업이라 새 중복 억제/직접 DDNS 보정 로직이 적용되지 않을 수 있다.
- 외부 DDNS 서버에 이미 잘못 등록된 예전 hostname은 별도 삭제 API가 없으면 남을 수 있다.
