# Ceph 마스터 bootstrap 실패 표시와 MON 실행 경로 보정

- **ID**: 022
- **날짜**: 2026-06-24
- **유형**: 버그 수정

## 작업 요약
마스터 노드 설치 및 구성 버튼이 실패해도 화면에서 성공처럼 새로고침만 되는 문제를 보정했다.
bootstrap action wrapper는 operation status가 `failed`이면 API code를 실패로 반환하고, Storage UI는 실패 operation을 받으면 Operation log 탭으로 전환해 오류 메시지와 로그를 보여준다.
master-only bootstrap은 인증 준비가 끝나지 않은 MGR/MDS를 즉시 띄우지 않고 MON service부터 생성하도록 조정했고, Ceph host bind 디렉터리를 container 내부 `ceph` 사용자 소유로 정리해 MON daemon이 권한 문제로 즉시 종료될 가능성을 줄였다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

마스터 노드 설치 및 구성 버튼을 누르니까 뭐 아무것도 없이 그냥 잠시 후 새로고침만 되고 있어.
실제 동작을 하는거야? 안하는 것 같은데? 서버 터미널에서 docker ps 명령어로 확인해도 ceph 관련 컨테이너는 뜨지 않았어.

## 리뷰 요약

- 리뷰 ID: ejosmmvibdlmlnlspihmlavbexhuwhoi
- 제목: Swarm 서버 OSD 슬롯 구성 마법사 구현
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 019ef783-f68e-7d60-98bd-b8bbe05c36ad
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 없음
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개
```

## 변경 파일 목록
- `src/app/page.storage/api.py`: operation status가 `failed`인 action 응답은 API code 409로 반환.
- `src/app/page.storage/view.ts`: bootstrap 응답 처리 공통화, 실패 시 `actionError` 표시와 Operation log 탭 전환 추가.
- `src/model/struct/storage_ceph_bootstrap.py`: master-only plan은 MON service만 생성하도록 조정.
- `src/model/struct/local_command_catalog.py`: Ceph runtime ensure 후 `/etc/ceph`, `/var/lib/ceph` bind 경로를 container `ceph` 사용자 소유로 정리.
- `tests/api/test_storage_models.py`: 실패 표시, master-only MON 우선 생성, 권한 정리 계약 추가.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.storage/api.py src/model/struct/storage_ceph_bootstrap.py src/model/struct/local_command_catalog.py src/model/struct/storage_ceph_runtime.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_migration_schema tests.api.test_storage_models` 통과.
- `wiz_project_build(clean=False)` 성공.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `http://127.0.0.1:3001/storage` HTTP 200 확인.
- 같은 쿠키로 `/wiz/api/page.storage/load` 호출 시 HTTP wrapper 200, 내부 `code: 401` 확인. 인증 세션이 없어 실제 버튼 실행은 검증하지 못했다.

## 남은 리스크
- master-only 단계는 우선 MON container를 올리는 경로다. MGR/MDS auth 생성과 daemon 배치는 MON 기동 후 별도 단계로 추가 검증/구현이 필요하다.
- `docker ps`에는 Swarm task container가 실제 노드에서 running일 때만 보인다. 실패 시 Operation log와 `docker service ps`로 원인을 확인해야 한다.
- 로그인 세션이 없어 실제 운영 버튼 클릭과 Docker service/task 생성은 직접 검증하지 못했다.
