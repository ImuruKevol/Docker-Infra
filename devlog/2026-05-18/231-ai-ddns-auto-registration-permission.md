# 231. AI DDNS 자동 등록 권한과 경고 처리 보강

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> AI로 DDNS를 이용해서 서비스 생성/수정 시 "사용자가 요청한 추가 DDNS 서브도메인은 등록 정보가 없어 연결되지 않았습니다." 라는 문구가 계속 뜨고 있어. AI를 이용할 때 등록된 DDNS 서버가 있으면 자동으로 API를 호출해서 DDNS 서비스를 등록하도록 하는 기능을 포함해야 해. 지금은 DDNS 관리 서버가 하나 등록이 되어있음에도 불구하고 AI에 해당 권한이 없거나 명시를 하지 않아서 계속 헛돌고 있는 것으로 보여.

## 변경 요약

- 서비스 AI 초안/검사 보정 권한에서 `can_register_ddns_records_via_deploy`를 활성화했다.
- DDNS 서버가 등록되어 있으면 Docker Infra backend가 배포/재배포 단계에서 DDNS 관리 API를 자동 호출한다는 흐름을 AI 컨텍스트에 명시했다.
- DDNS endpoint, wildcard suffix, 자동 API 호출 방식, AI가 반환해야 할 도메인 row 형식을 `ddns_registration_flow`로 전달하도록 했다.
- 매칭되는 DDNS wildcard가 있는데도 AI가 “등록 정보 없음/연결되지 않음”류 경고를 만들면 결과 경고에서 제거하도록 했다.
- 관련 정적 계약 테스트를 보강했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-18/231-ai-ddns-auto-registration-permission.md`

## 확인한 내용

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/model/struct/services_update.py tools/docker_infra_mcp.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight tests.api.test_domain_management_ui`: 17개 테스트 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_local_executor tests.api.test_migration_schema`: 17개 테스트 통과, 2개 skip
- `git diff --check`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 DDNS API 호출 성공 여부는 배포 시점의 외부 DDNS 관리 서버 응답과 현재 공인 IP 조회 결과에 의존한다.
- AI가 완전히 다른 표현으로 유사한 경고를 생성하면 추가 필터 패턴이 필요할 수 있다.
