# 191. 로컬 이미지 정리 확인 모달 대상 목록 표시

## 사용자 원본 요청

- 리뷰 ID: `qvjwkcalhekhezqcodxqcylioxtawtei`
- 제목: 이미지 관리 UI/UX 개선
- 요청 내용: 미사용 이미지 정리와 선택 삭제 시 확인 모달에 이미지 목록을 리스트 태그로 추가한다.

## 변경 파일

- `src/app/page.images/view.ts`
- `src/app/page.images/view.pug`
- `devlog.md`
- `devlog/2026-05-14/191-local-image-confirm-list.md`

## 변경 내용

- 미사용 이미지 정리와 선택 삭제 전용 확인 모달 상태를 추가했다.
- 확인 모달에 대상 이미지 개수와 `<ul><li>` 목록을 표시하도록 템플릿을 추가했다.
- 목록 항목에 이미지 이름, 용량, 짧은 이미지 ID, 최근 사용 정보를 함께 표시하도록 했다.
- 선택 삭제는 선택된 이미지 행을 기준으로 목록을 만들고, 미사용 이미지 정리는 현재 서버의 미사용 이미지 전체를 목록으로 보여주도록 했다.

## 확인 결과

- `python3 -m py_compile src/app/page.images/api.py src/model/struct/images_local.py src/model/struct/local_command_catalog.py src/model/struct/local_command_scripts.py config/docker_infra.py` 성공.
- `git diff --check` 성공.
- `wiz_project_build(clean=false)` 성공.

## 남은 리스크

- 미사용 이미지가 매우 많으면 확인 모달 목록이 길어질 수 있어, 현재는 스크롤 영역으로 제한했다.
