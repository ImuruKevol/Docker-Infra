# 192. 이미지 tar 업로드와 서버 로컬 import 기능 추가

- **ID**: 192
- **날짜**: 2026-05-14
- **유형**: 기능 추가

## 작업 요약
이미지 관리 화면의 서버 로컬 저장소에 Docker image archive tar 업로드 기능을 추가했다.
업로드 중에는 진행률 바를 표시하고, 업로드 완료 후 대상 서버에서 `docker load`를 실행해 로컬 이미지 저장소로 import한다.

## 원문 요청사항
```text
작업을 진행해줘. 업로드 시 업로드 progress 바는 필수야.

이미지 관리 화면에서 컨테이너 이미지 파일(tar)을 업로드해서 해당 서버의 로컬 레지스트리에 import하는 기능을 추가해줘.
```

## 변경 파일 목록
- `config/docker_infra.py`: 로컬 master에서 `docker.image.load` 실행을 허용하도록 기본 allowlist에 추가.
- `src/model/struct/local_command_catalog.py`: `docker.image.load` local command 정의 추가.
- `src/model/struct/images_local.py`: 업로드 파일 검증, 임시 저장, 원격 노드 scp 전송, `docker load` 실행, import 결과 기록과 임시 파일 정리를 추가.
- `src/app/page.images/api.py`: multipart 업로드용 `upload_local` API 추가.
- `src/app/page.images/view.ts`: tar 선택, upload progress 갱신, import 완료 후 로컬 이미지 목록 갱신 로직 추가.
- `src/app/page.images/view.pug`: 이미지 tar 업로드 버튼과 업로드 progress bar UI 추가.
- `devlog.md`, `devlog/2026-05-14/192-local-image-tar-upload-import.md`: 작업 이력 기록.

## 확인 결과
- 성공: `python3 -m py_compile project/main/config/docker_infra.py project/main/src/model/struct/local_command_catalog.py project/main/src/model/struct/images_local.py project/main/src/app/page.images/api.py`
- 성공: `git -C project/main diff --check -- config/docker_infra.py src/model/struct/local_command_catalog.py src/model/struct/images_local.py src/app/page.images/api.py src/app/page.images/view.ts src/app/page.images/view.pug`
- 성공: `wiz_project_build(clean=true)`

## 남은 리스크
- 실제 대용량 tar 업로드와 원격 노드 `docker load` 실서버 smoke test는 수행하지 않았다.
- progress bar는 브라우저에서 WIZ 서버로 업로드되는 구간의 진행률이며, 업로드 완료 후 Docker import 구간은 별도 단계 문구로 표시한다.
