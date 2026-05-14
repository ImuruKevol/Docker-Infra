# 189. Docker prune 추정 정확도 개선과 위험 정리 버튼 추가

## 사용자 원본 요청

- 리뷰 ID: `qvjwkcalhekhezqcodxqcylioxtawtei`
- 제목: 이미지 관리 UI/UX 개선
- 요청 내용: 용량 계산이 너무 어긋나 있으므로 docker 명령어를 최대한 활용해서 제대로 계산한다. `docker image prune -a`, `docker system prune -a` 명령어를 연결한 버튼을 추가한다. 둘 다 강력한 경고 메시지가 필요하며, system prune은 정지한 컨테이너, 사용하지 않는 커스텀 네트워크, 사용하지 않는 볼륨 등이 전부 삭제된다는 강력한 경고와 확인 체크박스를 추가해 체크해야 실행되도록 한다.

## 변경 파일

- `config/docker_infra.py`
- `src/app/page.images/view.pug`
- `src/app/page.images/view.ts`
- `src/app/page.images/api.py`
- `src/model/struct/images_local.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/local_command_scripts.py`
- `devlog.md`
- `devlog/2026-05-14/189-docker-prune-estimate-and-danger-actions.md`

## 변경 내용

- 선택 삭제 예상 확보 용량 계산에서 임의 레이어 크기 배분 fallback을 제거하고, `docker system df -v --format '{{json .}}'`가 제공하는 Docker unique size만 기준으로 표시하도록 변경했다.
- `docker system df --format '{{json .}}'` 기반 prune 예상 확보 용량 계산 스크립트를 추가했다.
- 로컬/원격 노드에 대해 `docker image prune -a -f`, `docker system prune -a --volumes -f` 실행 경로를 추가하고 작업 로그를 남기도록 했다.
- local executor 기본 allowlist에 `docker.image.prune`, `docker.system.prune`을 추가했다.
- 이미지 화면 우측 헤더에 `image prune -a`, `system prune -a` 버튼을 추가했다.
- image prune은 강한 경고 확인 모달을 거치도록 했고, system prune은 정지 컨테이너/미사용 네트워크/미사용 볼륨/빌드 캐시 삭제 경고와 확인 체크박스를 둔 별도 모달에서 체크해야 실행되도록 했다.

## 확인 결과

- `python3 -m py_compile project/main/config/docker_infra.py project/main/src/model/struct/images_local.py project/main/src/model/struct/local_command_catalog.py project/main/src/model/struct/local_command_scripts.py project/main/src/app/page.images/api.py` 성공.
- `DOCKER_IMAGE_STORAGE_SCRIPT`, `DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT`, `DOCKER_PRUNE_ESTIMATE_SCRIPT` 내장 Python 코드 compile 검증 성공.
- 비파괴 Docker 스크립트 smoke test 성공: 선택 삭제 빈 입력 추정, image prune 추정, system prune 추정 모두 exit 0.
- `wiz_project_build(clean=false)` 성공.

## 남은 리스크

- 선택 이미지 묶음 삭제의 실제 확보량은 Docker가 dry-run을 제공하지 않아 `docker system df -v`의 unique size 기준으로만 산정한다. 같은 선택 묶음 내부에서만 공유되는 레이어가 있으면 Docker CLI가 별도 그룹 reclaim 값을 제공하지 않으므로 실제와 차이가 날 수 있다.
- destructive prune 명령 자체는 안전상 실행하지 않았고, 비파괴 추정과 빌드 검증까지만 수행했다.
