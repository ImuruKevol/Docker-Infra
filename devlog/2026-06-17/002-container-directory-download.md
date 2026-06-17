# 컨테이너 파일 트리 폴더 다운로드 추가

- **ID**: 002
- **날짜**: 2026-06-17
- **유형**: 기능 추가

## 작업 요약
서비스 관리의 컨테이너 파일 트리에서 폴더 항목도 다운로드할 수 있도록 추가했다.
폴더 다운로드는 컨테이너 경로를 `docker cp container:path -`로 tar 스트림화한 뒤 gzip/base64로 응답하며, 브라우저에서는 `.tar.gz` 파일로 저장한다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

## 사용자 요청
작업 시작

## 리뷰 요약
- 리뷰 ID: oarnztdwgxubwcxgshdouajggqimttqd
- 제목: 서비스 관리 - 컨테이너 파일 기능 추가
- 요청 링크: https://infra-dev.nanoha.kr/access

## 리뷰어 요청 내용
현재는 파일만 다운로드받을 수 있는데, 디렉토리도 다운로드받을 수 있게 기능을 추가해줘.
```

## 변경 파일 목록
- `src/app/component.file.tree/view.html`: 컨테이너 폴더에도 다운로드 버튼 노출, 다운로드 중 버튼 비활성화 적용.
- `src/app/component.file.tree/view.ts`: 다운로드 가능 항목 판정, 폴더 다운로드 title, item type 전달, 응답 content type 기반 Blob 생성 추가.
- `src/model/struct/file_tree.py`: 컨테이너 폴더 다운로드 요청을 `.tar.gz` 아카이브 응답으로 분기.
- `src/model/struct/nodes_runtime_files.py`: 컨테이너 폴더 tar.gz base64 다운로드 처리와 다운로드 캡처 한도 초과 오류 추가.
- `src/model/struct/local_command_catalog.py`: 로컬 마스터용 `docker.container.directory.download` 명령 등록.
- `src/model/struct/local_executor.py`: 특정 호출에서 stdout 캡처 한도를 조정하고 truncation 여부를 결과에 표시하도록 확장.
- `src/model/struct/ssh_executor.py`: SSH 실행도 특정 호출에서 stdout 캡처 한도를 조정하고 truncation 여부를 결과에 표시하도록 확장.
- `src/model/struct/nodes.py`: 노드 SSH 명령 호출에 capture limit 전달 옵션 추가.
- `devlog.md`: 작업 요약 행 추가.
- `devlog/2026-06-17/002-container-directory-download.md`: 작업 상세 기록 추가.

## 검증 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/local_executor.py src/model/struct/ssh_executor.py src/model/struct/nodes.py src/model/struct/local_command_catalog.py src/model/struct/nodes_runtime_files.py src/model/struct/file_tree.py` 성공.
- `wiz_project_build(clean=false)` 성공.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키 포함 `https://infra-dev.nanoha.kr/access` 요청 결과 HTTP 200 확인.

## 남은 리스크
- 실제 운영 로그인 세션과 실행 중인 컨테이너 파일 트리에서 폴더 다운로드를 직접 클릭해 `.tar.gz` 압축 해제까지 확인하지는 못했다.
- 단일 응답으로 base64를 전달하는 기존 다운로드 구조를 유지하므로, 매우 큰 폴더는 서버 캡처 한도 초과 시 413 오류로 거절된다.
