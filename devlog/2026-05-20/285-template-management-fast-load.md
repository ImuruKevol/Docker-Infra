# 템플릿 관리 화면 목록 API 경량화와 상세 지연 로딩 적용

- **ID**: 285
- **날짜**: 2026-05-20
- **유형**: 성능 개선

## 작업 요약
템플릿 관리 화면의 최초 `load` API가 모든 템플릿의 schema/default 값을 읽지 않도록 목록 전용 `load_summaries` 경로로 전환했다.
첫 템플릿 상세와 AI 보조 메타데이터는 목록 렌더 이후 비동기로 불러오도록 분리해 초기 화면 표시 경로를 줄였다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 진행해줘.

## 리뷰 요약

- 리뷰 ID: bwmqrwsbmyqifogdemwubicbweorzgdk
- 제목: 템플릿 화면 최적화

## 리뷰어 요청 내용

템플릿 관리 화면에서 로드 속도가 너무 느려. 적당한 단위로 API를 분할하고, API 최적화 작업을 진행해줘.
```

## 변경 파일 목록
- `src/app/page.templates/api.py`
  - 템플릿 관리 `load` API를 전체 상세 로드에서 목록 요약 전용 `load_summaries` 호출로 변경했다.
- `src/app/page.templates/view.ts`
  - 초기 목록 렌더 후 첫 템플릿 상세를 비동기로 선택하도록 분리했다.
  - AI contract/model option 조회를 초기 로딩 완료 후 병렬 보조 로딩으로 이동했다.
- `tests/api/test_services_preflight.py`
  - 템플릿 관리 목록 API 경량화와 상세 지연 로딩 계약을 정적 테스트에 반영했다.
- `devlog.md`
- `devlog/2026-05-20/285-template-management-fast-load.md`

## 확인
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.templates/api.py src/model/struct/templates.py src/app/page.services.create/api.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest tests.api.test_images_templates_catalog.ImagesStaticContractTest`
- `wiz_project_build(projectName="main", clean=false)` 성공
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣고 `https://infra-dev.nanoha.kr/templates` HTTP 200 확인
- 같은 쿠키로 `https://infra-dev.nanoha.kr/services/create` HTTP 200 확인
- 같은 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.templates/load` 호출 시 로그인 세션이 없어 응답 본문 `code=401` 확인

## 남은 리스크
- 인증 세션이 없어 실제 로그인 후 `/templates`에서 첫 목록 렌더 시간과 상세 지연 로딩 체감은 브라우저로 직접 확인하지 못했다.
