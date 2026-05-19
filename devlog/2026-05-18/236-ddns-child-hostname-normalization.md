# 236. DDNS 서비스 도메인을 wildcard suffix 하위 hostname으로 보정

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 그리고 현재 적용된걸 보니까 도메인이 ddns 서브도메인으로 되어있지 않고 그냥 서브도메인으로만 되어있어. 수정해줘.
> 현재 wiki_service가 sub.nanoha.kr로 연결이 되어있는데, ddns가 sub.nanoha.kr로 등록이 되어있는거고, 실제 도메인은 wiki.sub.nanoha.kr 이런 식으로 앞에 하나가 더 붙어야 해.

## 변경 요약

- AI 프롬프트와 DDNS repair suggestion에서 wildcard suffix 자체를 서비스 hostname으로 쓰지 않도록 했다.
- 사용자가 `sub.nanoha.kr`처럼 DDNS suffix만 입력하거나 AI가 suffix만 반환해도 서비스 prefix를 붙여 `wiki.sub.nanoha.kr` 형태로 보정하도록 했다.
- 서비스 생성/수정 저장 경로에서 DDNS suffix 단독 도메인을 저장 전에 child hostname으로 정규화하도록 했다.
- DDNS 등록 시점에 기존 service domain row가 suffix 단독이면 서비스 namespace/name 기반 prefix를 붙여 row를 보정한 뒤 등록 API를 호출하도록 했다.
- 서비스 생성/수정 UI에서도 DDNS zone 선택 후 prefix가 비어 있으면 서비스 이름 기반 prefix를 자동 채워 preview와 저장값이 suffix 단독이 되지 않게 했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `src/model/struct/domains_ddns.py`
- `src/model/struct/services_update.py`
- `src/model/struct/services_wizard.py`
- `src/app/page.services.create/view.ts`
- `src/app/page.services/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-18/236-ddns-child-hostname-normalization.md`

## 확인한 내용

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/domains_ddns.py src/model/struct/services_update.py src/model/struct/services_wizard.py tools/docker_infra_mcp.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight tests.api.test_domain_management_ui`: 18개 테스트 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `git diff --check`: 통과

## 남은 리스크

- 이미 외부 DDNS 관리 서버에 잘못 등록된 `sub.nanoha.kr` 레코드는 별도 삭제 API가 없는 한 외부 시스템에 남아 있을 수 있다.
- 기존 잘못된 service domain row는 다음 서비스 수정 저장 또는 DDNS 등록 API 호출 시점에 보정된다.
