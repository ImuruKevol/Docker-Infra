# 서비스 삭제 시 Cloudflare DNS 레코드 정리 추가

- **ID**: 139
- **날짜**: 2026-05-12
- **유형**: 버그 수정

## 작업 요약
서비스 삭제 흐름에서 연결된 서비스 도메인의 Cloudflare DNS 레코드를 제거하도록 보강했다.
Cloudflare 삭제 실패 시 서비스 삭제 operation을 실패 처리해 orphan DNS 레코드가 남은 상태로 DB만 삭제되지 않도록 했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

버그를 수정해줘

## 리뷰 요약

- 리뷰 ID: yifqmpklnlscfhnpybdmxpegtwoycxic
- 제목: 서비스 삭제 시 버그

## 리뷰어 요청 내용

서비스 삭제 시 도메인이 적용되어 있다면 CloudFlare에 등록된 해당 도메인도 삭제가 되어야 하는데 삭제되지 않고 남아있는 버그가 있음.
```

## 변경 파일 목록
- `src/model/struct/domains.py`: 서비스 도메인 기준 Cloudflare DNS 레코드 삭제 메서드 추가, 서비스 DNS 등록 결과에 record/zone 식별자 포함.
- `src/model/struct/services_delete.py`: 서비스 삭제 시 nginx 설정 제거 후 Cloudflare DNS 레코드 삭제 호출 및 operation 결과 기록 추가.
- `tests/api/test_services_preflight.py`: 서비스 삭제와 Cloudflare DNS 삭제 계약 정적 테스트 추가.
- `devlog.md`, `devlog/2026-05-12/139-service-delete-cloudflare-dns-cleanup.md`: 작업 이력 추가.

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/domains.py src/model/struct/services_delete.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest`
- `wiz_project_build(clean=false)` 성공

## 남은 리스크
- 실제 Cloudflare API 삭제는 운영 토큰/존 설정이 필요해 로컬에서 실호출 검증하지 못했다.
- Cloudflare token이 제거되었거나 zone 설정이 없으면 삭제는 skip되며, 기존 동작처럼 수동 정리가 필요하다.
