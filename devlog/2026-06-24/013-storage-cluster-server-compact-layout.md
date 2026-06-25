# 013 Storage 클러스터 서버 카드 통합과 Operation log 탭 위치 조정

## 요청

- Review ID: `zyqsvvysbltycxwkhsghunmhrnxytqqu`
- 제목: 스토리지 화면 개선

```text
- Operation log는 탭 위치가 맨 끝으로 가야해.
- Dockerized Ceph cluster bootstrap 카드와 Swarm 스토리지 서버 카드를 적절히 통합해서 맨 위에 클러스터로 묶여있는 서버를 컴팩트하게 보여주고, 해당 서버에 OSD 슬롯을 바로 구성할 수 있게끔 레이아웃을 변경해줘.
```

## 변경 파일

- `src/app/page.storage/view.ts`
  - `Operation log` 탭을 탭 배열의 마지막 위치로 이동했다.
- `src/app/page.storage/view.pug`
  - `Dockerized Ceph cluster bootstrap` 카드와 `Swarm 스토리지 서버` 카드를 상단 카드 하나로 통합했다.
  - 상단 카드에 Swarm 서버 수, OSD 구성 가능 수, 최근 operation 상태와 서버별 OSD 슬롯 만들기 버튼을 함께 표시했다.
  - 하단의 중복 Swarm 서버 카드를 제거하고 Ceph daemon 요약 영역을 단일 열로 정리했다.
- `tests/api/test_storage_models.py`
  - 통합 서버 목록 영역과 Operation log 탭 위치 계약을 정적 테스트에 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models` 통과
- WIZ 프로젝트 빌드 통과: `wiz_project_build(projectName="main", clean=false)`
- devmode 쿠키를 포함한 접근 확인:
  - `https://infra-dev.nanoha.kr/access` HTTP 200
  - `https://infra-dev.nanoha.kr/storage` HTTP 200

## 남은 리스크

- 실제 인증 세션에서 OSD 슬롯 버튼 클릭 후 모달 동작까지 브라우저로 직접 확인하지는 않았다.
