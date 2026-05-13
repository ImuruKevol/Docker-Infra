# 매크로 첨부 파일 DB 스키마 수동 적용

- **ID**: 150
- **날짜**: 2026-05-12
- **유형**: 설정 변경

## 작업 요약
`/macros` 화면에서 `shell_macro_files` relation 누락 오류가 발생해, 기존 checksum mismatch로 전체 migration runner가 막힌 상태를 확인했다.
요청에 따라 `013_shell_macro_files.sql` 내용을 현재 DB에 직접 적용하고 `schema_migrations`에 013 적용 기록을 반영했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

에러가 떴어. DB에 실제 스키마 적용이 필요하면 적용도 해줘.
relation "shell_macro_files" does not exist LINE 16: FROM shell_macro_files mf ^

## 리뷰 요약

- 리뷰 ID: fdbwtzahvpcbkpgpxbajrhdbscykwudy
- 제목: 매크로 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/macros
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 019e1c4d-f255-7d41-8350-051399e563c8
- 스크린샷 컨텍스트: 1번 첨부됨
- 에이전트 작업 지시서 컨텍스트: 없음
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 세션 처리

저장된 Codex 세션을 resume해 이전 대화 맥락을 우선 사용하세요. 이전 Codex 히스토리는 이 요청에 포함되지 않습니다.
```

## 변경 파일 목록
- `devlog.md`
- `devlog/2026-05-12/150-macro-file-schema-apply.md`

## DB 적용 내용
- `src/model/db/migrations/013_shell_macro_files.sql` 실행
- `schema_migrations`에 `013 / shell_macro_files` checksum 기록 upsert

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python scripts/docker_infra_migrate.py status`에서 013 `applied: true`, `checksum_matches: true` 확인
- 직접 조회로 `to_regclass('shell_macro_files') = shell_macro_files` 확인
- 매크로 목록 lateral query가 `shell_macro_files`를 참조해 정상 실행되는 것 확인

## 남은 리스크
기존 migration 001, 011의 checksum mismatch는 남아 있고, 012 migration은 여전히 미적용 상태다. 전체 migration runner는 이 이슈가 정리되기 전까지 계속 중단될 수 있다.
