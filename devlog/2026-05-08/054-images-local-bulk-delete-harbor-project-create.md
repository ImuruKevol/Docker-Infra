# 054. 이미지 관리 로컬 일괄 삭제, Harbor 프로젝트 생성, 저장소별 태그 상세/삭제 흐름 보강

- 일시: 2026-05-08
- 사용자 요청:
  - "로컬 저장소 이미지 목록에서 Digest / ID 컬럼을 삭제해줘. 그리고 여기도 체크박스 컬럼을 추가해서 일괄 삭제 기능을 추가해줘.
harbor 프로젝트 선택 후 이미지들을 리스팅하는데 선택 삭제 버튼은 만들어놓고 정작 체크박스 컬럼을 안만들었어. 각 이미지별 삭제 버튼도 없고.
그리고 각 이미지를 클릭하면 클릭 상태는 되는 것 같은데 그 아래에 태그 목록을 불러오지 못하고 있어.

그리고 harbor project를 새로 생성할 수 있도록도 해줘."

## 처리 내용

1. 로컬 저장소 이미지 테이블에서 `Digest / ID` 컬럼을 제거했다.
2. 로컬 저장소 이미지 테이블에 체크박스 선택 열과 `선택 삭제` 액션을 추가했다.
3. 로컬 이미지 삭제 API는 `image_ref` 단건뿐 아니라 `items=[{image_ref}]` 다건 삭제도 받을 수 있게 확장했다.
4. Harbor 프로젝트 상세 조회는 전체 태그 일괄 조회 대신 `저장소 목록 조회`와 `저장소별 태그 조회`로 분리했다.
5. Harbor 저장소 행을 클릭하면 해당 저장소의 태그 목록을 별도 API로 가져오도록 수정했다.
6. Harbor 태그 표에는 체크박스 열과 개별 삭제 버튼을 유지하고, 다중 선택 삭제가 실제로 현재 저장소 태그 목록 기준으로 동작하도록 정리했다.
7. Harbor 프로젝트 생성 API와 생성 모달을 추가했다.
8. Harbor 프로젝트 삭제 후 프로젝트 목록/선택 상태/태그 상태가 같이 정리되도록 후처리를 보강했다.
9. 이미지 관리 live 테스트에 Harbor 프로젝트 생성/상세/삭제와 저장소별 태그 조회 smoke를 추가했다.

## 변경 파일

- 이미지 관리 UI/API
  - `src/app/page.images/api.py`
  - `src/app/page.images/view.ts`
  - `src/app/page.images/view.pug`
- 이미지 관리 모델
  - `src/model/struct/images.py`
  - `src/model/struct/images_harbor.py`
- 테스트/기록
  - `tests/api/test_images_templates_catalog.py`
  - `devlog.md`

## 검증

- `wiz_project_build(projectName="main", clean=false)` 통과
- `systemctl restart wiz.docker-infra` 후 health 확인
- `DOCKER_INFRA_BASE_URL='http://127.0.0.1:3001' DOCKER_INFRA_TEST_PASSWORD='____' python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_images_templates_catalog.ImagesTemplatesLiveFlowTest` 통과
- live API smoke
  - Harbor 프로젝트 생성 `200`
  - 생성 직후 Harbor 프로젝트 상세 조회 `200`
  - Harbor 프로젝트 삭제 `200`
- `git diff --check` 통과
