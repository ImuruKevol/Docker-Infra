# 055. Harbor 이미지 목록/태그 목록 분리와 저장소 선택·삭제 동작 수정

- 일시: 2026-05-08
- 사용자 요청:
  - "왜 자꾸 못알아먹었는지 알겠어. Harbor쪽에서 프로젝트 클릭 후 나오는 'Harbor 이미지 버전' 목록에 체크박스 컬럼이 없어. 그 이미지 버전을 클릭해도 아래에 태그 목록이 불러와지질 않고. 위에 있는 표에는 이미지 수가 정상적으로 표시가 되는데, 정작 그 아래에 이미지 수에 따른 목록이 보이질 않아"

## 처리 내용

1. Harbor 프로젝트 상세 화면을 `이미지(repository) 목록`과 `태그 목록` 두 단계로 다시 분리했다.
2. 프로젝트 상세 상단의 선택 삭제 버튼은 태그가 아니라 `이미지(repository) 목록` 기준으로 동작하도록 수정했다.
3. 이미지 목록 표에 체크박스 열과 개별 삭제 버튼을 추가했다.
4. Harbor 저장소 삭제 API를 추가해 이미지(repository) 단건/다건 삭제가 가능하도록 보강했다.
5. 저장소 클릭 시 아래 태그 목록을 다시 읽어오는 흐름을 유지하되, 저장소명을 Harbor artifact API가 실제 기대하는 짧은 이름으로 정규화했다.
6. 기존에는 `keycloud/test-xxxx` 전체 경로를 그대로 넘겨 태그 조회 결과가 0건이 되었는데, 이를 `test-xxxx` 형식으로 보정해 실제 태그가 내려오도록 수정했다.
7. 태그 목록 섹션은 별도 헤더로 분리하고, 선택한 저장소의 태그를 명확히 보이도록 정리했다.

## 변경 파일

- `src/app/page.images/api.py`
- `src/app/page.images/view.ts`
- `src/app/page.images/view.pug`
- `src/model/struct/images.py`
- `src/model/struct/images_harbor.py`
- `tests/api/test_images_templates_catalog.py`
- `devlog.md`

## 검증

- `wiz_project_build(projectName="main", clean=false)` 통과
- `systemctl restart wiz.docker-infra` 후 health 확인
- live API 확인
  - `/wiz/api/page.images/harbor_detail` -> `repositories=19`
  - 첫 저장소 `test-7811a2`
  - `/wiz/api/page.images/harbor_tags` -> `200`, `tags=1`
- `DOCKER_INFRA_BASE_URL='http://127.0.0.1:3001' DOCKER_INFRA_TEST_PASSWORD='____' python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_images_templates_catalog.ImagesTemplatesLiveFlowTest` 통과
- `git diff --check` 통과
