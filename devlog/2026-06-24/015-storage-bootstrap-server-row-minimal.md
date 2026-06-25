# 015 Storage bootstrap 서버 행을 이름/IP/OSD 버튼만 표시하도록 압축

## 요청

- Review ID: `zyqsvvysbltycxwkhsghunmhrnxytqqu`
- 제목: 스토리지 화면 개선

```text
Dockerized Ceph cluster bootstrap 카드에서 각 서버들이 차지하는 공간이 너무 많아. 불필요하게 너무 많은 공간을 차지하고 있어. 각 서버들은 서버 이름, IP, OSD 슬롯 만들기 버튼 이렇게만 표시하면 돼.
```

## 변경 파일

- `src/app/page.storage/view.pug`
  - bootstrap 카드의 서버 행을 서버 이름, IP, OSD 슬롯 만들기 버튼 3열로 축소했다.
  - 서버 상태 배지, 보조 설명 줄, 대기 버튼 분기를 제거했다.
  - 후보가 아닌 서버도 같은 버튼을 비활성화해 행 구조를 고정했다.
- `src/app/page.storage/view.ts`
  - 더 이상 사용하지 않는 서버 모드 라벨/클래스 helper를 제거했다.
- `tests/api/test_storage_models.py`
  - compact 3열 서버 행과 불필요한 helper 미사용 계약을 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models` 통과
- WIZ 프로젝트 빌드 통과: `wiz_project_build(projectName="main", clean=false)`
- devmode 쿠키를 포함한 접근 확인:
  - `https://infra-dev.nanoha.kr/access` HTTP 200
  - `https://infra-dev.nanoha.kr/storage` HTTP 200

## 남은 리스크

- 실제 인증 세션에서 긴 서버 이름/IP 조합의 시각적 줄임 처리는 브라우저로 직접 확인하지 못했다.
