# 193. 이미지 tar 업로드 413 차단 회피

- **ID**: 193
- **날짜**: 2026-05-14
- **유형**: 버그 수정

## 작업 요약
이미지 tar 업로드가 nginx 요청 본문 크기 제한에 걸려 `413 Request Entity Too Large`로 실패하는 문제를 확인했다.
단일 대용량 multipart 업로드 대신 768 KiB 단위 chunk 업로드로 전환하고, 서버에서 chunk를 합친 뒤 기존 `docker load` import 흐름을 실행하도록 보강했다.

## 원문 요청사항
```text
실제 업로드를 시도해보니 이미지 tar를 import할 수 없습니다. 라는 에러가 떴어.
```

## 변경 파일 목록
- `src/app/page.images/view.ts`: 이미지 tar를 chunk 단위로 순차 업로드하고 전체 진행률을 누적 계산하도록 변경. 413 응답 메시지도 별도 처리.
- `src/app/page.images/api.py`: 기존 `upload_local` API에서 chunk 업로드 요청을 분기 처리하도록 보강.
- `src/model/struct/images_local.py`: 업로드 세션 검증, chunk 임시 저장, 전체 tar 재조립, 크기 검증, 기존 import 흐름 재사용 로직 추가.
- `devlog.md`, `devlog/2026-05-14/193-local-image-upload-chunked.md`: 작업 이력 기록.

## 확인 결과
- 확인: nginx error log에서 `client intended to send too large body: 54358336 bytes`와 `POST /wiz/api/page.images/upload_local` 413 응답 확인.
- 성공: `python3 -m py_compile project/main/config/docker_infra.py project/main/src/model/struct/local_command_catalog.py project/main/src/model/struct/images_local.py project/main/src/app/page.images/api.py`
- 성공: `git -C project/main diff --check -- config/docker_infra.py src/model/struct/local_command_catalog.py src/model/struct/images_local.py src/app/page.images/api.py src/app/page.images/view.ts src/app/page.images/view.pug devlog.md`
- 성공: `wiz_project_build(clean=false)`

## 남은 리스크
- 실제 대용량 tar 재업로드 smoke test는 수행하지 않았다.
- 브라우저가 업로드 중단되면 완료되지 않은 chunk 임시 파일이 남을 수 있다.
