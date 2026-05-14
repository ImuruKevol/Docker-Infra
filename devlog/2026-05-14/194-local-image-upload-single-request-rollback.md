# 194. 이미지 tar chunk 업로드 롤백

- **ID**: 194
- **날짜**: 2026-05-14
- **유형**: 롤백

## 작업 요약
nginx `client_max_body_size`가 `0`으로 조정되어 대용량 업로드 제한이 해제된 전제에 맞춰 이미지 tar chunk 순차 업로드를 제거했다.
이미지 tar 업로드는 다시 단일 multipart 요청으로 전송하고, 기존 업로드 progress callback으로 진행률 바를 표시한다.

## 원문 요청사항
```text
nginx 설정에서 client_max_body_size를 0으로 줘서 무제한으로 풀었어. 청크 순차 업로드로 했던걸 롤백해줘.
```

## 변경 파일 목록
- `src/app/page.images/view.ts`: chunk 분할 업로드 상수와 helper를 제거하고 단일 파일 업로드 흐름으로 복구.
- `src/app/page.images/api.py`: chunk 요청 분기 제거, `import_local_image` 직접 호출로 복구.
- `src/model/struct/images_local.py`: chunk 업로드 세션, chunk 저장/재조립, chunk import API helper 제거.
- `devlog.md`, `devlog/2026-05-14/194-local-image-upload-single-request-rollback.md`: 작업 이력 기록.

## 확인 결과
- 성공: `python3 -m py_compile project/main/config/docker_infra.py project/main/src/model/struct/local_command_catalog.py project/main/src/model/struct/images_local.py project/main/src/app/page.images/api.py`
- 성공: `git -C project/main diff --check -- config/docker_infra.py src/model/struct/local_command_catalog.py src/model/struct/images_local.py src/app/page.images/api.py src/app/page.images/view.ts src/app/page.images/view.pug devlog.md`
- 성공: `wiz_project_build(clean=false)`

## 남은 리스크
- 실제 대용량 tar 단일 업로드 smoke test는 수행하지 않았다.
- nginx 무제한 설정은 프로젝트 코드 밖의 런타임 설정이라 코드 검증 대상에는 포함하지 않았다.
