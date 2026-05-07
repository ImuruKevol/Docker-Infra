# 053. 이미지 관리 초기 로딩 분리·Harbor 삭제/태그 표시 보강, 템플릿 릴리즈 UI·저장 경로·기본 seed 확장

- 일시: 2026-05-08
- 사용자 요청:
  - "이미지 관리에서는 이미지 용량별 정렬, 이미지 생성 날짜 정렬, 마지막 사용 날짜 정렬, 사용/미사용 중인 이미지 필터링 등 편의 기능이 필요해.
그리고 초반에 너무 많은 정보를 한번에 불러와서 초반 로딩 시간이 너무 길어. 적당히 분리해서 화면 자체는 아무리 늦어도 1초 내로 화면이 뜨도록 최적화해줘.
그리고 harbor API를 이용해서 가져오는건 프로젝트 목록과 태그는 가져오는 듯 한데, 프로젝트별 포함된 이미지 목록은 화면에 표시되지 않고 있어.

템플릿 관리에서는 ID, 분류는 필요 없어. 이름과 설명, 대표 이미지면 돼. 근데 대표 이미지라고 하니까 너무 헷갈려. 이미지 이름과 버전이라고 명시해야 알아보기 편할 것 같아.
템플릿 목록에서 \"사용 중\" 뱃지에서 \"중\" 부분이 다음줄로 넘어가는 등 UI가 사소하게 어긋나고 있으니 수정해줘.
버전 이력은 모나코 에디터 오른쪽에 다단을 하나 더 만들어서 표시해줘. 이 때 이력을 클릭해서 해당 버전에 대한 내용을 불러올 수 있어야 해. 근데 지금은 저장 시마다 계속 버전이 생기는 형태이니, 이걸 조금 개선해서 사용자가 명시적으로 버전 만들기나 릴리즈같은 느낌으로 버튼을 클릭해야 버전을 만들도록 하면 될 것 같아."

## 처리 내용

1. 이미지 관리 초기 `load` API에서 Harbor 원격 조회를 제거하고, 노드 목록/캐시 요약만 내려주도록 경량화했다.
2. Harbor 프로젝트 목록은 `harbor_overview` API로 분리하고, Harbor 탭에 들어간 뒤에만 불러오도록 변경했다.
3. 이미지 관리 화면은 overview를 받은 즉시 렌더링하고, 선택 서버 로컬 상세는 background로 따로 가져오도록 바꿨다.
4. 로컬 이미지 상세에 `사용 여부`, `연결 컨테이너 수`, `실행 컨테이너 수`, `마지막 사용 시각`, `size_bytes`를 추가했다.
5. 로컬 이미지 화면에 `사용 중/미사용` 필터와 `최근 사용/용량/생성일` 정렬 옵션을 추가했다.
6. Harbor 프로젝트 상세에 포함 이미지 저장소 목록을 명시적인 표 형태로 보여주고, 태그별 용량을 표시하도록 수정했다.
7. Harbor 태그는 체크박스로 다중 선택해 한 번에 삭제할 수 있게 했고, 프로젝트 전체 삭제도 추가했다.
8. 템플릿 관리 화면에서 사용자 입력 항목을 `이름`, `설명`, `이미지 이름`, `이미지 버전` 중심으로 단순화했다.
9. 템플릿 저장과 버전 생성을 분리했다.
   - `save_template`: 현재 편집본만 저장
   - `release_template`: 저장 후 명시적으로 버전 snapshot 생성
10. 템플릿 화면 오른쪽에 버전 이력 컬럼과 버전 내용 미리보기 컬럼을 추가하고, 선택한 버전의 파일 내용을 읽어오도록 `version_detail` API를 추가했다.
11. 템플릿 저장 루트를 프로젝트 내부 임시 경로가 아니라 WIZ root의 `data/templates`로 고정하고, 기존 템플릿 경로도 이 위치로 이관되도록 보정했다.
12. 기본 seed 템플릿에 `GitLab CE`, `Harbor Registry`를 추가하고, 기존 카탈로그가 있어도 누락된 seed는 자동 보충되도록 바꿨다.

## 변경 파일

- 이미지 관리
  - `src/app/page.images/api.py`
  - `src/app/page.images/view.ts`
  - `src/app/page.images/view.pug`
  - `src/model/struct/images.py`
  - `src/model/struct/images_shared.py`
  - `src/model/struct/local_command_catalog.py`
- 템플릿 관리
  - `src/app/page.templates/api.py`
  - `src/app/page.templates/view.ts`
  - `src/app/page.templates/view.pug`
  - `src/model/struct/templates.py`
  - `src/model/struct/templates_store.py`
  - `src/model/struct/templates_seed.py`
- 테스트/기록
  - `tests/api/test_images_templates_catalog.py`
  - `devlog.md`

## 검증

- `wiz_project_build(projectName="main", clean=false)` 통과
- `systemctl restart wiz.docker-infra` 후 `active` 확인
- `DOCKER_INFRA_BASE_URL='http://127.0.0.1:3001' DOCKER_INFRA_TEST_PASSWORD='____' python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesLiveFlowTest` 통과
- Playwright headless smoke
  - `/images` H1 렌더 기준 `559ms`, page error 없음
  - `/templates` H1 렌더 기준 `632ms`, page error 없음
- 인증 세션 기준 `/wiz/api/page.images/load` 3회 측정
  - `258.7ms`
  - `294.7ms`
  - `193.2ms`
- live API 확인
  - `/wiz/api/page.templates/load` -> `template_root=/root/docker-infra/data/templates`
  - 기본 템플릿 이름 목록에 `GitLab CE`, `Harbor Registry` 포함 확인
