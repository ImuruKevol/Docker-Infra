# 이미지 관리 좌우 레이아웃과 Harbor 프로젝트 삭제 보강

- **ID**: 001
- **날짜**: 2026-06-22
- **유형**: UX/버그 수정

## 원문 요청
```text
서버 로컬 저장소, 백업 저장소의 Layout이 위에 서버/프로젝트 선택 후 아래에서 세부 내용 확인으로 되어있는데, 이미지 관리에서는 왼쪽에 서버/프로젝트 선택 후 오른쪽에서 세부 내용 확인 및 관리로 수정이 되어야 함.
백업 저장소에서 harbor project 선택 후 "프로젝트 삭제"버튼의 위치를 세부 내용 확인 부분의 헤더 영역으로 이동할 것.
백업 저장소에서 프로젝트 삭제 기능이 동작하지 않는데, 저장소에 이미지가 존재하면 삭제가 되지 않고 있음. 이미지가 존재해도 먼저 이미지들을 삭제 후 프로젝트를 삭제하게 하여 기능을 동작시킬 것.
서버 로컬 저장소에서 독립 서버로 등록된 서버들은 이미지 목록이 불러와지지 않고 있음.
```

## 변경 파일
- `src/app/page.images/view.pug`
  - 백업 저장소와 서버 로컬 저장소를 좌측 선택 목록, 우측 상세/관리 패널의 2단 레이아웃으로 변경.
  - Harbor 프로젝트 삭제 버튼을 저장소 목록 헤더에서 선택 프로젝트 상세 헤더로 이동.
  - 서버 목록 배지에 클러스터/독립 서버 구분을 표시.
- `src/model/struct/images.py`
  - 이미지가 남아 있는 Harbor 프로젝트 삭제 시 저장소별 artifact와 repository를 먼저 삭제한 뒤 프로젝트를 삭제하도록 변경.
  - 이미지 관리 서버 목록 응답에 `role`, `swarm_node_id`를 포함.
- `src/model/struct/images_harbor.py`
  - Harbor 프로젝트, 저장소, artifact 목록 조회가 페이지를 끝까지 순회하도록 보강.
- `src/model/struct/images_local.py`
  - 독립/원격 서버 이미지 목록 및 사용 정보 조회에서 stdout 20KB 절단을 해제하고 조회 timeout을 늘림.
- `tests/api/test_images_templates_catalog.py`
  - Harbor 프로젝트 삭제 전 artifact/repository 삭제 순서가 유지되도록 정적 계약 검증을 보강.
- `devlog.md`
- `devlog/2026-06-22/001-images-layout-harbor-delete-local-load.md`

## 검증 결과
- `python -m py_compile src/model/struct/images.py src/model/struct/images_harbor.py src/model/struct/images_local.py` 성공.
- `python -m unittest tests.api.test_images_templates_catalog.ImagesStaticContractTest` 성공.
- `git diff --check` 성공.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `curl -I`에 `season-wiz-project=main; season-wiz-devmode=true` 쿠키를 포함해 `/images` 200 응답 확인.
- 동일 쿠키로 `/wiz/api/page.images/load` 호출 시 인증 미로그인 상태라 401이 반환되어 실제 데이터 API는 로컬 세션에서 끝까지 검증하지 못함.
