# 매크로 첨부 파일 저장과 실행 전 서버 전송 기능 추가

- **ID**: 149
- **날짜**: 2026-05-12
- **유형**: 기능 추가

## 작업 요약
매크로별 첨부 파일을 저장하는 `shell_macro_files` 마이그레이션과 저장/조회/삭제 연동을 추가했다.
전역 매크로 화면과 서버 전용 매크로 모달에서 파일을 추가·유지·삭제할 수 있게 했고, 매크로 실행 시 첨부 파일을 임시 작업 디렉터리로 복사한 뒤 스크립트를 실행하도록 runner를 확장했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업해줘.

## 리뷰 요약

- 리뷰 ID: fdbwtzahvpcbkpgpxbajrhdbscykwudy
- 제목: 매크로 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/macros
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 신규
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 포함됨
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 에이전트 작업 지시서

# 에이전트 작업 지시서

## 리뷰 정보

- 리뷰 ID: fdbwtzahvpcbkpgpxbajrhdbscykwudy
- 제목: 매크로 기능 추가
- 상태: open
- 우선순위: normal
- 분류: ux
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/macros
- 화면: 1920x900
- 캡처 방식: reviewops-sdk-dom-snapshot
- 스크린샷 첨부: yes
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

매크로마다 파일을 업로드할 수 있게 해서 각 서버별로 매크로를 실행시킬 때 업로드한 파일이 있으면 해당 파일들을 전송한 후 스크립트가 실행될 수 있도록 기능 추가가 필요함.

# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업을 진행해줘.

## 리뷰 요약

- 리뷰 ID: fdbwtzahvpcbkpgpxbajrhdbscykwudy
- 제목: 매크로 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/macros
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 019e1c4d-f255-7d41-8350-051399e563c8
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 포함됨
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 세션 처리

저장된 Codex 세션을 resume해 이전 대화 맥락을 우선 사용하세요. 이전 Codex 히스토리는 이 요청에 포함되지 않습니다.

## 에이전트 작업 지시서

# 에이전트 작업 지시서

## 리뷰 정보

- 리뷰 ID: fdbwtzahvpcbkpgpxbajrhdbscykwudy
- 제목: 매크로 기능 추가
- 상태: in_progress
- 우선순위: normal
- 분류: ux
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/macros
- 화면: 1920x900
- 캡처 방식: reviewops-sdk-dom-snapshot
- 스크린샷 첨부: yes
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

매크로마다 파일을 업로드할 수 있게 해서 각 서버별로 매크로를 실행시킬 때 업로드한 파일이 있으면 해당 파일들을 전송한 후 스크립트가 실행될 수 있도록 기능 추가가 필요함.
```

## 변경 파일 목록
- `src/model/db/migrations/013_shell_macro_files.sql`
- `src/model/db/migrations/013_shell_macro_files.down.sql`
- `src/model/struct/macros.py`
- `src/model/struct/macros_shared.py`
- `src/model/struct/macros_store.py`
- `src/model/struct/macros_runner.py`
- `src/app/page.macros/api.py`
- `src/app/page.macros/view.ts`
- `src/app/page.macros/view.pug`
- `src/app/page.servers/api.py`
- `src/app/page.servers/view.ts`
- `src/app/page.servers/view.pug`
- `tests/api/test_migration_schema.py`
- `tests/api/test_server_macros.py`
- `devlog.md`
- `devlog/2026-05-12/149-macro-file-attachments.md`

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile ...` 성공
- `wiz_project_build(clean=false)` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_server_macros.ServerMacrosStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest` 성공
- `/opt/conda/envs/docker-infra/bin/python scripts/docker_infra_migrate.py up`은 기존 적용 migration checksum mismatch로 실패했다.

## 남은 리스크
현재 DB의 `schema_migrations`에서 기존 001, 011 checksum 불일치가 확인되어 새 013 migration은 로컬 DB에 적용되지 않았다. 운영/개발 DB 반영 전 기존 migration checksum 상태를 먼저 정리해야 한다.
