# 서비스 상세 구성 탭 AI 검사/수정 버튼 제거

- **ID**: 021
- **날짜**: 2026-06-22
- **유형**: UX 수정

## 작업 요약
서비스 상세 구성 영역의 실행 상태 헤더에서 `AI 검사/수정` 버튼을 제거했다.
상태 확인, 일괄 시작/재시작/중지 버튼은 유지했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

구성 탭에 있는 AI 검사/수정 버튼을 삭제해줘.

## 리뷰 요약

- 리뷰 ID: vefrcbbdewfnksgqcisqfqmaqjppjtgt
- 제목: 서비스 관리 상세
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 019eee59-e221-7e83-b61a-4d4a35de4441
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 없음
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개
```

## 변경 파일 목록
- `src/app/page.services/view.pug`: 서비스 상세 실행 상태 헤더의 `AI 검사/수정` 버튼 제거.
- `tests/api/test_services_preflight.py`: 서비스 상세 템플릿에 해당 버튼/클릭 바인딩이 남지 않는 계약 검증 추가.
- `devlog.md`, `devlog/2026-06-22/021-service-detail-remove-ai-repair-button.md`: 작업 이력 추가.

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_deploy_status_refresh_and_self_signed_ssl_test_path_are_wired tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_detail_operator_runtime_summary_is_wired`
- 성공: `wiz_project_build(clean=false)` normal build
- 참고: `test_service_create_supports_templates_and_draft_sources`는 기존 `selectedTemplateReadme()` 기대값 불일치로 실패했다.
