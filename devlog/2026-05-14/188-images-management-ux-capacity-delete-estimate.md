# 188. 이미지 관리 UI/UX 개선

## 사용자 원본 요청

- 리뷰 ID: `qvjwkcalhekhezqcodxqcylioxtawtei`
- 제목: 이미지 관리 UI/UX 개선
- 요청 내용: 서비스 백업 시스템이 꺼져 있으면 Harbor 토글 버튼을 숨기고, 서버 로컬 저장소 오른쪽 컨텐츠 영역에 서버별 총 용량과 남은 용량을 잘 보이게 표시한다. 생성일 정보는 제거하고, 사용 중인 이미지는 삭제 버튼과 체크를 비활성화한다. 여러 이미지를 선택 삭제할 때 가능하면 실제 레이어 구조를 확인해 삭제 시 확보되는 용량을 계산해 표시한다.

## 변경 파일

- `src/app/page.images/view.pug`
- `src/app/page.images/view.ts`
- `src/app/page.images/api.py`
- `src/model/struct/images_local.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/local_command_scripts.py`
- `devlog.md`
- `devlog/2026-05-14/188-images-management-ux-capacity-delete-estimate.md`

## 변경 내용

- 백업 시스템이 비활성화된 상태에서는 Harbor 탭 버튼이 렌더링되지 않도록 처리하고, 초기 탭 선택도 로컬 저장소로 유지되도록 조정했다.
- 서버 로컬 이미지 상세 응답에 Docker 저장소 디스크 총 용량, 사용량, 남은 용량, 사용률, 경로 정보를 포함하고, 우측 컨텐츠 상단에 용량 카드와 사용률 바를 추가했다.
- 로컬 이미지 목록에서 생성일/생성 시점 표시와 생성일 정렬 옵션을 제거하고 용량 중심 컬럼으로 정리했다.
- 사용 중인 로컬 이미지는 체크박스와 삭제 버튼을 비활성화하고, 백엔드에서도 사용 중 이미지 삭제 요청을 차단하도록 보강했다.
- `local_delete_estimate` API와 로컬/원격 Docker 추정 명령을 추가해 선택 삭제 전 Docker image 목록, 컨테이너 사용 상태, image inspect 레이어 구조, 가능 시 `docker system df -v` unique size를 기반으로 예상 확보 용량을 계산해 확인 모달과 툴바에 표시하도록 했다.

## 확인 결과

- `python3 -m py_compile project/main/src/model/struct/images_local.py project/main/src/model/struct/local_command_catalog.py project/main/src/model/struct/local_command_scripts.py project/main/src/app/page.images/api.py` 성공.
- `DOCKER_IMAGE_STORAGE_SCRIPT`, `DOCKER_IMAGE_DELETE_ESTIMATE_SCRIPT` 내장 Python 코드 compile 검증 성공.
- `wiz_project_build(clean=false)` 성공.

## 남은 리스크

- Docker가 `docker system df -v --format`의 unique size를 제공하지 않는 환경에서는 image inspect 레이어 구조와 이미지 크기 기반 추정값으로 대체되므로 실제 확보 용량과 차이가 날 수 있다.
- 실제 서버 Docker 상태를 사용하는 UI/삭제 플로우는 빌드 검증까지 수행했고, 운영 데이터에 대한 실삭제 테스트는 수행하지 않았다.
