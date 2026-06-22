# 이미지 관리 독립 서버 목록 로드와 Harbor 헤더 액션 정리

- **ID**: 003
- **날짜**: 2026-06-22
- **유형**: 버그 수정/UX

## 원문 요청
```text
서버 로컬 저장소
- 독립 서버의 이미지 목록이 여전히 불러와지지 않고 있어. lenovo, ktw-gpu 서버의 웹 터미널은 잘 작동하니까 다시 실제로 확인해줘. 관리자 패스워드 제공됨.

백업 저장소
- 헤더의 저장소, 이미지, Pull, 계정 카드 4개는 삭제해줘. 그 자리에  프로젝트 생성 버튼과 프로젝트 삭제 버튼을 위치시켜줘.
```

## 변경 파일
- `src/model/struct/images_shared.py`
  - Docker image 목록의 `Containers` 값이 `N/A`인 경우 500 오류가 나지 않도록 정수 파싱을 보강.
- `src/app/page.images/view.pug`
  - 선택 프로젝트 헤더의 저장소/이미지/Pull/계정 카드 4개 제거.
  - 해당 위치에 프로젝트 생성/프로젝트 삭제 버튼 배치.
  - 프로젝트 미선택 상태에서도 프로젝트 생성 버튼을 표시.
- `tests/api/test_images_templates_catalog.py`
  - `Containers: "N/A"` 파싱 회귀 방지 테스트 추가.
- `devlog.md`
- `devlog/2026-06-22/003-images-independent-server-and-harbor-actions.md`

## 확인한 원인
- lenovo, ktw-gpu의 `docker image ls --format '{{json .}}'` 응답 중 `Containers` 필드가 숫자가 아닌 `N/A`로 내려와 `int("N/A")` 변환에서 500이 발생했다.

## 검증 결과
- 실제 로그인 세션으로 `/wiz/api/page.images/local_detail` 호출 확인.
- lenovo: HTTP 200, `docker_available=true`, 이미지 22개 로드 확인.
- ktw-gpu: HTTP 200, `docker_available=true`, 이미지 10개 로드 확인.
- `python -m unittest tests.api.test_images_templates_catalog.ImagesStaticContractTest` 성공.
- `python -m py_compile src/model/struct/images_shared.py src/model/struct/images.py src/model/struct/images_harbor.py src/model/struct/images_local.py` 성공.
- `git diff --check` 성공.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `season-wiz-project=main; season-wiz-devmode=true` 쿠키 포함 `/images` 200 응답 확인.
