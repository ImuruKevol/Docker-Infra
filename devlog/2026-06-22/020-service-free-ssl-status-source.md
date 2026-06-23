# 무료 SSL 인증서 상태 표시 데이터 소스 통일

- **ID**: 020
- **날짜**: 2026-06-22
- **유형**: 버그 수정

## 작업 요약
서비스 상세의 무료 SSL 인증서 상태가 경량 상세 extras 경로와 런타임 상세 경로에서 서로 다른 데이터 소스를 사용해 흔들리던 문제를 수정했다.
경량 extras도 실제 certbot 인증서 상태를 조회하도록 맞추고, 조회 실패 시에만 기존 placeholder 목록으로 fallback하도록 변경했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

무료 SSL 인증서 부분이 어떨 때는 발급 대기로 나오고, 어떨 때는 인증서 발급 완료인가로 나오고 그런ㄴ데 도대체 왜 자꾸 달라지는거야?

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
- `src/model/struct/services_detail_fast.py`: 경량 상세 extras에서 무료 SSL 인증서 정보를 실제 `service_certificates` 결과로 내려주도록 변경.
- `tests/api/test_services_preflight.py`: 경량 상세 extras가 실제 인증서 조회와 fallback 계약을 유지하는지 정적 계약 검증 추가.
- `devlog.md`, `devlog/2026-06-22/020-service-free-ssl-status-source.md`: 작업 이력 추가.

## 검증 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_detail_splits_slow_extras_from_initial_overview tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_certbot_issue_waits_for_runtime_and_exposes_renewal_ops`
- 성공: `wiz_project_build(clean=false)` normal build
