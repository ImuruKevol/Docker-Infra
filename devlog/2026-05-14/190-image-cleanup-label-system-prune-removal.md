# 190. 이미지 정리 버튼 문구 개선과 system prune 제거

## 사용자 원본 요청

- 리뷰 ID: `qvjwkcalhekhezqcodxqcylioxtawtei`
- 제목: 이미지 관리 UI/UX 개선
- 요청 내용: 버튼 이름에 명령어를 그대로 넣지 말고 사용자가 확실히 알 수 있는 단어를 사용한다. `system prune -a` 기능은 너무 위험하므로 제거한다. `registry.nanoha.kr/kwon3286/docker-infra` 이미지 표시 용량은 24.5GB인데 `docker image prune -a`는 977MB만 표시되는 점이 맞는지 확인하고 Docker 명령어를 최대한 활용해 계산을 바로잡는다.

## 변경 파일

- `config/docker_infra.py`
- `src/app/page.images/view.pug`
- `src/app/page.images/view.ts`
- `src/model/struct/images_local.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/local_command_scripts.py`
- `devlog.md`
- `devlog/2026-05-14/190-image-cleanup-label-system-prune-removal.md`

## 변경 내용

- 이미지 화면의 `image prune -a` 버튼명을 `미사용 이미지 정리`로 변경하고, 확인 모달의 액션명도 사용자 친화 문구로 바꿨다.
- `system prune` 버튼, 전용 모달, 프론트 상태/메서드, 백엔드 실행 분기, local executor allowlist, command catalog 항목을 제거했다.
- 선택 이미지 삭제 예상 확보 용량 표시에 `표시 용량`과 `공유·유지 레이어 제외` 값을 함께 보여주도록 보강했다.
- Docker 29의 `docker system df -v --format '{{json .}}'`가 `Images` 배열을 담은 단일 JSON으로 반환되는 형식을 파싱하도록 수정했다.
- `docker image prune -a` 예상값은 Docker prune 기준 reclaimable 값과 전체 이미지 표시 용량을 함께 보여주도록 했다.

## 확인 결과

- `python3 -m py_compile config/docker_infra.py src/model/struct/images_local.py src/model/struct/local_command_catalog.py src/model/struct/local_command_scripts.py src/app/page.images/api.py` 성공.
- `DOCKER_IMAGE_STORAGE_SCRIPT`, `DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT`, `DOCKER_PRUNE_ESTIMATE_SCRIPT` 내장 Python 코드 compile 검증 성공.
- 비파괴 Docker smoke test 성공: `registry.nanoha.kr/kwon3286/docker-infra` 선택 삭제 예상은 Docker `system df -v` 기준 약 24.4GB, `docker image prune -a` 기준 전체 정리 예상은 Docker `system df` 기준 약 977MB로 구분 확인.
- `wiz_project_build(clean=false)` 성공.

## 남은 리스크

- `docker image prune -a`는 Docker 엔진이 제공하는 prune reclaimable 기준을 그대로 따르므로, 명시적 이미지 삭제 예상값과 다를 수 있다.
- 실제 삭제/정리 명령은 안전상 실행하지 않았고, 비파괴 추정과 빌드 검증까지만 수행했다.
